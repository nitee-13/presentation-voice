import asyncio
import json
import logging
import os
import re

from dotenv import load_dotenv
from livekit.agents import AgentSession, AgentServer, JobContext, cli
from livekit.agents.voice import Agent
from livekit.plugins import deepgram, google

from claude_router import (
    route_slide, summarize_conversation, generate_filler, warm_filler_cache,
    POPUP_TOOLS, DEVI_INTRO, check_start_intent, generate_pre_start_response,
    warm_start_cache,
)
from slides import SLIDES, SYSTEM_PROMPT

load_dotenv()

logger = logging.getLogger("presentation-agent")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")


# How long to wait after the user's last utterance before processing (seconds)
DEBOUNCE_DELAY = 1.0

# Filler words / backchannel sounds that should NOT trigger a response
FILLER_WORDS = {
    "um", "umm", "ummm", "uh", "uhh", "uhhh", "hmm", "hm", "hmmmm",
    "ah", "ahh", "oh", "ohh", "er", "err", "like", "so",
    "yeah", "yep", "yup", "mhm", "mhmm", "mm", "mmm", "mm-hmm",
    "okay", "ok", "uh-huh", "uh huh", "right",
}


def is_filler_only(text: str) -> bool:
    """Check if the text is just filler words / backchannel sounds."""
    words = text.lower().replace(".", "").replace(",", "").replace("?", "").replace("!", "").split()
    return all(w in FILLER_WORDS for w in words)


def split_into_chunks(text: str, sentences_per_chunk: int = 3) -> list[str]:
    """Split narration into chunks of N sentences for TTS batching.

    Balances mid-slide pause/resume granularity with TTS efficiency.
    """
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    sentences = [s for s in sentences if s.strip()]
    chunks = []
    for i in range(0, len(sentences), sentences_per_chunk):
        chunk = " ".join(sentences[i:i + sentences_per_chunk])
        chunks.append(chunk)
    return chunks


RATING_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}


def parse_rating(text: str) -> int | None:
    """Extract a 1-5 rating from spoken text."""
    match = re.search(r'\b([1-5])\b', text)
    if match:
        return int(match.group(1))
    lower = text.lower()
    for word, num in RATING_WORDS.items():
        if word in lower:
            return num
    return None


def rating_label(n: int) -> str:
    """Human-friendly rating label."""
    return f"{n} star{'s' if n != 1 else ''}"


LANGUAGE_TRIGGERS = {
    "spanish": "Spanish", "español": "Spanish",
    "french": "French", "français": "French",
    "german": "German", "deutsch": "German",
    "portuguese": "Portuguese", "português": "Portuguese",
    "italian": "Italian", "italiano": "Italian",
    "japanese": "Japanese", "日本語": "Japanese",
    "chinese": "Chinese", "中文": "Chinese",
    "korean": "Korean", "한국어": "Korean",
    "russian": "Russian", "русский": "Russian",
    "english": "English",
}


def detect_language_switch(text: str) -> str | None:
    """Detect if the user wants to switch language. Returns language name or None."""
    lower = text.lower()
    for trigger in ["present in", "switch to", "speak in", "change to", "respond in", "use"]:
        if trigger in lower:
            rest = lower.split(trigger, 1)[1].strip().rstrip(".")
            for key, lang in LANGUAGE_TRIGGERS.items():
                if key in rest:
                    return lang
    return None


class PresentationAgent(Agent):
    """Two-pointer architecture:

    Pointer 1 — Presentation cursor (_cursor / _sentence_index)
        Where auto-narration is in the natural slide order.
        Only advances when a slide is fully narrated.

    Pointer 2 — Visual pointer (current_slide)
        Which slide is displayed on the user's screen.
        Jumps freely for Q&A navigation.
    """

    def __init__(self) -> None:
        super().__init__(instructions="You are an AI presentation assistant.")

        # --- Pointer 2: visual (what's on screen) ---
        self.current_slide = 0

        # --- Pointer 1: presentation cursor (auto-narration position) ---
        self._cursor = 0                      # slide index in natural order
        self._sentence_index = 0              # sentence within that slide
        self.slides_completed: set[int] = set()  # fully narrated slides

        # --- State ---
        self.history: list[dict] = []
        self.is_presenting = False
        self.waiting_for_start = True
        self.paused = False
        self.language: str | None = None

        # --- Feedback ---
        self.feedback_mode: str | None = None  # None | "rating" | "comment" | "confirm"
        self.feedback_rating: int = 0
        self.feedback_comment: str = ""

        # --- Debounce ---
        self._pending_parts: list[str] = []
        self._debounce_task: asyncio.Task | None = None
        self._is_processing = False

        # --- Events ---
        self._resume_event = asyncio.Event()

    # ------------------------------------------------------------------
    # Data channel helpers
    # ------------------------------------------------------------------

    async def send_slide(self, index: int) -> None:
        """Move the visual pointer — update frontend display."""
        self.current_slide = index
        await self.session.room_io.room.local_participant.publish_data(
            json.dumps({"slideIndex": index}),
            topic="slide_change",
        )

    async def publish_popup(self, payload: dict) -> None:
        """Send a UI popup event to the frontend."""
        await self.session.room_io.room.local_participant.publish_data(
            json.dumps(payload),
            topic="ui_popup",
        )

    async def publish_feedback(self, payload: dict) -> None:
        """Send a feedback update to the frontend."""
        await self.session.room_io.room.local_participant.publish_data(
            json.dumps(payload),
            topic="feedback_update",
        )

    # ------------------------------------------------------------------
    # Tool execution
    # ------------------------------------------------------------------

    async def execute_tool_calls(self, tool_calls: list[dict]) -> None:
        """Execute tool calls from the direct Claude API response."""
        for tc in tool_calls:
            name = tc["name"]
            inp = tc["input"]

            if name == "advance_to_slide":
                slide_index = inp["slide_index"]
                if 0 <= slide_index < len(SLIDES):
                    # During narration: backward advance → force peek
                    if self.is_presenting and slide_index < self._cursor:
                        logger.info("advance_to_slide(%d) → forced peek (backward during narration, cursor stays at %d)",
                                    slide_index, self._cursor)
                        await self.send_slide(slide_index)
                        self.paused = True
                    else:
                        logger.info("advance_to_slide: visual %d → %d, cursor %d → %d",
                                    self.current_slide, slide_index, self._cursor, slide_index)
                        await self.send_slide(slide_index)
                        self._cursor = slide_index
                        self._sentence_index = 0

            elif name == "peek_at_slide":
                slide_index = inp["slide_index"]
                if 0 <= slide_index < len(SLIDES):
                    if self.is_presenting:
                        logger.info("peek_at_slide: visual %d → %d  [cursor stays at %d, sentence %d] — pausing narration",
                                    self.current_slide, slide_index, self._cursor, self._sentence_index)
                        await self.send_slide(slide_index)
                        self.paused = True
                    else:
                        # Narration done — no two-pointer, just navigate
                        logger.info("peek_at_slide(%d) → direct nav (narration complete)",
                                    slide_index)
                        await self.send_slide(slide_index)

            elif name == "pause_presentation":
                logger.info("pause_presentation [cursor at slide %d, sentence %d]",
                            self._cursor, self._sentence_index)
                self.paused = True

            elif name == "resume_presentation":
                logger.info("resume_presentation [cursor at slide %d, sentence %d]",
                            self._cursor, self._sentence_index)
                self.paused = False
                self._resume_event.set()

            elif name == "show_key_facts":
                logger.info("show_key_facts: %s", inp.get("title"))
                await self.publish_popup({
                    "type": "key_facts",
                    "title": inp["title"],
                    "facts": inp["facts"],
                    "ttl": 10,
                })

            elif name == "show_comparison_table":
                logger.info("show_comparison_table: %s", inp.get("title"))
                await self.publish_popup({
                    "type": "comparison_table",
                    "title": inp["title"],
                    "columns": inp["columns"],
                    "rows": inp["rows"],
                    "ttl": 12,
                })

            elif name == "show_timeline":
                logger.info("show_timeline: %s", inp.get("title"))
                await self.publish_popup({
                    "type": "timeline",
                    "title": inp["title"],
                    "events": inp["events"],
                    "ttl": 12,
                })

            elif name == "show_citations":
                logger.info("show_citations: %s", inp.get("title"))
                await self.publish_popup({
                    "type": "citations",
                    "title": inp["title"],
                    "citations": inp["citations"],
                    "ttl": 10,
                })

            elif name == "end_presentation":
                logger.info("end_presentation — stopping narration")
                self.is_presenting = False
                self.paused = False
                self._resume_event.set()  # unblock narration loop if waiting

            else:
                logger.warning("Unknown tool call: %s", name)

    # ------------------------------------------------------------------
    # Sentence-level slide narration
    # ------------------------------------------------------------------

    async def narrate_slide(self, index: int) -> bool:
        """Narrate a slide sentence by sentence, tracking progress.

        Returns True if the slide was fully narrated, False if cursor moved away.
        """
        if index < 0 or index >= len(SLIDES):
            return True

        slide = SLIDES[index]
        sentences = split_into_chunks(slide["narration"])

        if not sentences:
            return True

        # Sync visual pointer to the cursor slide
        if self.current_slide != index:
            await self.send_slide(index)

        logger.info("Narrating slide %d: %s (sentence %d/%d)",
                     index, slide["title"], self._sentence_index, len(sentences))

        while self._sentence_index < len(sentences):
            # If presentation ended, stop immediately
            if not self.is_presenting:
                logger.info("Presentation ended — stopping narration")
                return False

            # If cursor moved (advance_to_slide called), stop narrating this slide
            if self._cursor != index:
                logger.info("Cursor moved away from slide %d → %d, stopping narration",
                            index, self._cursor)
                return False

            # If paused, wait until resume
            if self.paused:
                logger.info("Paused at slide %d, sentence %d/%d",
                            index, self._sentence_index, len(sentences))
                self._resume_event.clear()
                await self._resume_event.wait()
                # After resume, check if cursor moved while paused
                if self._cursor != index:
                    return False
                # Sync visual back to cursor
                if self.current_slide != index:
                    await self.send_slide(index)
                logger.info("Resumed at slide %d, sentence %d/%d",
                            index, self._sentence_index, len(sentences))

            # If user spoke (pending input) or processing Q&A, wait for it to resolve
            if self._pending_parts or self._is_processing:
                while self._pending_parts or self._is_processing:
                    await asyncio.sleep(0.2)
                # After user input resolved, check state
                if self._cursor != index:
                    return False
                if self.paused:
                    continue
                if self.current_slide != index:
                    await self.send_slide(index)

            sentence = sentences[self._sentence_index]
            speech = await self.session.say(sentence, allow_interruptions=True)
            await speech.wait_for_playout()

            # Only advance sentence if we weren't interrupted
            if not self._is_processing and not self._pending_parts and not self.paused and self._cursor == index:
                self._sentence_index += 1

        # Slide fully narrated
        self._sentence_index = 0
        self.slides_completed.add(index)
        logger.info("Slide %d fully narrated (completed: %s)", index, self.slides_completed)
        return True

    # ------------------------------------------------------------------
    # Presentation loop (drives pointer 1 — the cursor)
    # ------------------------------------------------------------------

    async def run_presentation(self) -> None:
        """Auto-narrate slides in order, skipping completed ones.

        The loop reads self._cursor each iteration. advance_to_slide changes
        _cursor directly, so the loop naturally picks up the new position.
        """
        self.is_presenting = True

        while self._cursor < len(SLIDES):
            # Skip already-completed slides
            if self._cursor in self.slides_completed:
                logger.info("Skipping slide %d (already completed)", self._cursor)
                self._cursor += 1
                continue

            # Remember which slide we're about to narrate
            target = self._cursor

            completed = await self.narrate_slide(target)

            if completed:
                # Wait for any pending user input before auto-advancing
                while self._pending_parts or self._is_processing:
                    await asyncio.sleep(0.2)
                # If user paused, navigated, or moved cursor — don't auto-advance
                if self.paused or self._cursor != target:
                    continue
                await asyncio.sleep(1.5)
                self._cursor += 1
            # If not completed: cursor was moved by advance_to_slide,
            # loop re-reads self._cursor at the top

        self.is_presenting = False
        logger.info("Presentation complete — all slides narrated")

    async def on_enter(self) -> None:
        """Speak intro and wait for user to signal start."""
        logger.info("Agent entered — speaking intro")
        speech = await self.session.say(DEVI_INTRO, allow_interruptions=True)
        await speech.wait_for_playout()


# ---------------------------------------------------------------------------
# Transcript processing (debounce → Claude direct API → execute tools → TTS)
# ---------------------------------------------------------------------------

async def process_full_transcript(agent: PresentationAgent, session: AgentSession) -> None:
    """Process the accumulated transcript after debounce delay."""
    full_transcript = " ".join(agent._pending_parts).strip()
    agent._pending_parts = []
    agent._is_processing = True

    if not full_transcript:
        agent._is_processing = False
        return

    if is_filler_only(full_transcript):
        logger.info("Ignoring filler-only transcript: '%s'", full_transcript)
        agent._is_processing = False
        return

    # --- Intro phase: waiting for user to start ---
    if agent.waiting_for_start:
        logger.info("Intro phase — checking start intent: '%s'", full_transcript)
        try:
            wants_start = await check_start_intent(full_transcript)
        except Exception as e:
            logger.error("Start intent check failed: %s", e)
            wants_start = False

        if wants_start:
            logger.info("User wants to start — launching presentation")
            agent.waiting_for_start = False
            await session.say("Let's get started!", allow_interruptions=True)
            asyncio.ensure_future(agent.run_presentation())
        else:
            try:
                reply = await generate_pre_start_response(full_transcript)
                speech = await session.say(reply, allow_interruptions=True)
                await speech.wait_for_playout()
            except Exception as e:
                logger.error("Pre-start response failed: %s", e)
                await session.say(
                    "That's great! Just let me know when you'd like me to start the presentation.",
                    allow_interruptions=True,
                )

        agent._is_processing = False
        return

    # --- Feedback phase ---
    if agent.feedback_mode:
        logger.info("Feedback phase (%s): '%s'", agent.feedback_mode, full_transcript)

        if agent.feedback_mode == "rating":
            rating = parse_rating(full_transcript)
            if rating:
                agent.feedback_rating = rating
                await agent.publish_feedback({"rating": rating, "phase": "comment"})
                agent.feedback_mode = "comment"
                speech = await session.say(
                    f"{'Wonderful' if rating >= 4 else 'Noted'}, {rating} stars! "
                    "Any thoughts or feedback you'd like to add? Or just say 'no' to wrap up.",
                    allow_interruptions=True,
                )
                await speech.wait_for_playout()
            else:
                await session.say(
                    "Could you give me a rating from 1 to 5 stars?",
                    allow_interruptions=True,
                )

        elif agent.feedback_mode == "comment":
            lower = full_transcript.lower().strip()
            no_comment = any(kw in lower for kw in [
                "no", "nope", "nothing", "that's it", "that's all",
                "i'm good", "all good", "skip", "none",
            ])

            if no_comment:
                await agent.publish_feedback({"phase": "done"})
                agent.feedback_mode = None
                speech = await session.say(
                    "No worries! Thanks for the rating. It was great presenting to you. Take care!",
                    allow_interruptions=True,
                )
                await speech.wait_for_playout()
            else:
                agent.feedback_comment = full_transcript
                await agent.publish_feedback({"comment": full_transcript, "phase": "confirm"})
                agent.feedback_mode = "confirm"
                speech = await session.say(
                    f"Got it! Just to confirm — {rating_label(agent.feedback_rating)} "
                    f"and your feedback is: \"{full_transcript}\". Shall I submit that?",
                    allow_interruptions=True,
                )
                await speech.wait_for_playout()

        elif agent.feedback_mode == "confirm":
            lower = full_transcript.lower().strip()
            confirmed = any(kw in lower for kw in [
                "yes", "yep", "yeah", "sure", "confirm", "submit",
                "go ahead", "that's right", "correct", "do it",
            ])

            if confirmed:
                logger.info("Feedback submitted: rating=%d, comment='%s'",
                            agent.feedback_rating, agent.feedback_comment)
                await agent.publish_feedback({"phase": "done"})
                agent.feedback_mode = None
                speech = await session.say(
                    "Submitted! Thank you so much. It was a pleasure presenting to you. Goodbye!",
                    allow_interruptions=True,
                )
                await speech.wait_for_playout()
            else:
                await agent.publish_feedback({"phase": "comment"})
                agent.feedback_mode = "comment"
                agent.feedback_comment = ""
                speech = await session.say(
                    "No problem! Go ahead and share your feedback again.",
                    allow_interruptions=True,
                )
                await speech.wait_for_playout()

        agent._is_processing = False
        return

    logger.info("Processing: '%s' (visual: slide %d | cursor: slide %d, sentence %d)",
                full_transcript, agent.current_slide, agent._cursor, agent._sentence_index)

    # Language switch
    new_lang = detect_language_switch(full_transcript)
    if new_lang:
        agent.language = None if new_lang == "English" else new_lang
        confirm = f"Switching to {new_lang}!" if new_lang != "English" else "Switching back to English!"
        logger.info("Language switch: %s", new_lang)
        await session.say(confirm, allow_interruptions=True)
        agent._is_processing = False
        return

    # Summarize command
    lower = full_transcript.lower().strip()
    is_summarize = any(kw in lower for kw in [
        "summarize", "summarise", "recap", "summary",
        "what have we discussed", "what did we cover",
    ])

    if is_summarize and agent.history:
        logger.info("Summarize command detected")
        try:
            summary = await summarize_conversation(agent.history)
            speech = await session.say(summary, allow_interruptions=True)
            await speech.wait_for_playout()
        except Exception as e:
            logger.error("Summarize failed: %s", e, exc_info=True)
            await session.say("Sorry, I had trouble summarizing. Could you try again?")
        agent._is_processing = False
        return

    # Route via direct Claude API with tools
    try:
        result = await route_slide(
            transcript=full_transcript,
            current_slide=agent.current_slide,
            cursor=agent._cursor,
            paused=agent.paused,
            history=agent.history,
            language=agent.language,
        )
    except Exception as e:
        logger.error("Claude routing failed: %s", e, exc_info=True)
        await session.say("Sorry, I had trouble processing that. Could you repeat your question?")
        agent._is_processing = False
        return

    tool_calls = result.get("tool_calls", [])
    response = result.get("response", "")

    # Categorize tool calls by timing
    popup_calls = [tc for tc in tool_calls if tc["name"] in POPUP_TOOLS]
    pause_calls = [tc for tc in tool_calls if tc["name"] == "pause_presentation"]
    after_speech_calls = [tc for tc in tool_calls if tc["name"] in (
        "advance_to_slide", "peek_at_slide", "resume_presentation",
        "end_presentation",
    )]

    # Execute pause immediately (before anything else)
    if pause_calls:
        await agent.execute_tool_calls(pause_calls)

    # If popup tools present → filler → popup → main response
    if popup_calls:
        popup_type = popup_calls[0]["name"].removeprefix("show_")
        try:
            filler = await generate_filler(full_transcript, popup_type)
            if filler:
                filler_speech = await session.say(filler, allow_interruptions=True)
                await filler_speech.wait_for_playout()
        except Exception as e:
            logger.warning("Filler generation failed: %s", e)

        # Show popups (appears while user heard the filler)
        await agent.execute_tool_calls(popup_calls)

    # Speak the main response
    if response:
        speech = await session.say(response, allow_interruptions=True)
        await speech.wait_for_playout()

    # Execute navigation + resume AFTER speech
    if after_speech_calls:
        await agent.execute_tool_calls(after_speech_calls)

    # Store conversation turn
    slide = SLIDES[agent.current_slide]
    entry = {
        "user": full_transcript,
        "assistant": response,
        "slide_index": agent.current_slide,
        "slide_title": slide["title"],
    }
    agent.history.append(entry)

    # Send Q&A entry to frontend history panel
    await agent.session.room_io.room.local_participant.publish_data(
        json.dumps({"user": entry["user"], "assistant": entry["assistant"]}),
        topic="qa_entry",
    )

    # Keep last 10 turns for context
    if len(agent.history) > 10:
        agent.history = agent.history[-10:]

    agent._is_processing = False


async def debounce_and_process(agent: PresentationAgent, session: AgentSession) -> None:
    """Wait for the user to stop speaking, then process everything at once."""
    await asyncio.sleep(DEBOUNCE_DELAY)
    await process_full_transcript(agent, session)


def on_user_transcript(ev, agent: PresentationAgent, session: AgentSession) -> None:
    """Accumulate transcript parts and reset debounce timer on each one."""
    if not ev.is_final:
        return

    text = ev.transcript.strip()
    if not text:
        return

    logger.info("STT fragment: '%s'", text)
    agent._pending_parts.append(text)

    if agent._debounce_task and not agent._debounce_task.done():
        agent._debounce_task.cancel()

    agent._debounce_task = asyncio.ensure_future(
        debounce_and_process(agent, session)
    )


# ---------------------------------------------------------------------------
# LiveKit session setup
# ---------------------------------------------------------------------------

async def _start_feedback(agent: PresentationAgent, session: AgentSession) -> None:
    """Initiate the voice feedback flow."""
    await agent.publish_feedback({"phase": "rating"})
    speech = await session.say(
        "Oh, before you escape! I promise this isn't one of those never-ending surveys. "
        "Just a quick rating, 1 to 5 stars — and if you'd rather not, "
        "just hit that button again and I won't hold it against you. "
        "So, how many stars am I getting?",
        allow_interruptions=True,
    )
    await speech.wait_for_playout()


server = AgentServer()


@server.rtc_session
async def handle_session(ctx: JobContext) -> None:
    await ctx.connect()

    # Prime Haiku caches so first calls are fast
    await asyncio.gather(warm_filler_cache(), warm_start_cache())

    # Load Google credentials from env var (JSON string) or fall back to file
    google_creds = None
    creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
    if creds_json:
        google_creds = json.loads(creds_json)

    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        tts=google.TTS(
            voice_name="en-US-Chirp3-HD-Achernar",
            **({"credentials_info": google_creds} if google_creds else {}),
        ),
    )

    agent = PresentationAgent()

    @session.on("user_input_transcribed")
    def on_transcribed(ev):
        on_user_transcript(ev, agent, session)

    @ctx.room.on("data_received")
    def on_data(data_packet):
        try:
            if data_packet.topic == "user_slide_nav":
                payload = json.loads(data_packet.data.decode())
                slide_index = payload.get("slideIndex")
                if isinstance(slide_index, int) and 0 <= slide_index < len(SLIDES):
                    logger.info("User keyboard nav: visual %d → %d  [cursor stays at %d]",
                                agent.current_slide, slide_index, agent._cursor)
                    agent.current_slide = slide_index

            elif data_packet.topic == "feedback_control":
                payload = json.loads(data_packet.data.decode())
                if payload.get("action") == "start_feedback":
                    logger.info("Feedback mode started")
                    agent.is_presenting = False
                    agent.paused = False
                    agent._resume_event.set()
                    agent.feedback_mode = "rating"
                    asyncio.ensure_future(_start_feedback(agent, session))
        except Exception as e:
            logger.error("Failed to parse data_received: %s", e)

    await session.start(
        agent=agent,
        room=ctx.room,
    )


if __name__ == "__main__":
    cli.run_app(server)

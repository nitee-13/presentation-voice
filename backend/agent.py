import asyncio
import json
import logging
import re

from dotenv import load_dotenv
from livekit.agents import AgentSession, AgentServer, JobContext, inference, cli
from livekit.agents.voice import Agent

from claude_router import route_slide, summarize_conversation
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


def split_into_sentences(text: str) -> list[str]:
    """Split narration text into sentences for granular tracking."""
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    return [s for s in sentences if s.strip()]


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
        self.paused = False
        self.language: str | None = None

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
                    logger.info("advance_to_slide: visual %d → %d, cursor %d → %d",
                                self.current_slide, slide_index, self._cursor, slide_index)
                    # Move BOTH pointers — permanent navigation
                    await self.send_slide(slide_index)
                    self._cursor = slide_index
                    self._sentence_index = 0

            elif name == "peek_at_slide":
                slide_index = inp["slide_index"]
                if 0 <= slide_index < len(SLIDES):
                    logger.info("peek_at_slide (visual only): %d → %d  [cursor stays at %d, sentence %d]",
                                self.current_slide, slide_index, self._cursor, self._sentence_index)
                    # Only move visual pointer — cursor untouched
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

            elif name == "show_concept_cloud":
                logger.info("show_concept_cloud: %s", inp.get("title"))
                await self.publish_popup({
                    "type": "concept_cloud",
                    "title": inp["title"],
                    "concepts": inp["concepts"],
                    "ttl": 10,
                })

            elif name == "show_citations":
                logger.info("show_citations: %s", inp.get("title"))
                await self.publish_popup({
                    "type": "citations",
                    "title": inp["title"],
                    "citations": inp["citations"],
                    "ttl": 10,
                })

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
        sentences = split_into_sentences(slide["narration"])

        if not sentences:
            return True

        # Sync visual pointer to the cursor slide
        if self.current_slide != index:
            await self.send_slide(index)

        logger.info("Narrating slide %d: %s (sentence %d/%d)",
                     index, slide["title"], self._sentence_index, len(sentences))

        while self._sentence_index < len(sentences):
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

            # If processing a Q&A, wait for it to finish
            if self._is_processing:
                while self._is_processing:
                    await asyncio.sleep(0.2)
                # After Q&A, check if cursor moved (advance_to_slide)
                if self._cursor != index:
                    return False
                # If paused (by pause_presentation), loop back to pause check
                if self.paused:
                    continue
                # Sync visual back to cursor slide (peek_at_slide may have changed it)
                if self.current_slide != index:
                    await self.send_slide(index)

            sentence = sentences[self._sentence_index]
            speech = await self.session.say(sentence, allow_interruptions=True)
            await speech.wait_for_playout()

            # Only advance sentence if we weren't interrupted
            if not self._is_processing and not self.paused and self._cursor == index:
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
                await asyncio.sleep(1.5)
                # Only advance cursor if it wasn't moved by advance_to_slide
                if self._cursor == target:
                    self._cursor += 1
            # If not completed: cursor was moved by advance_to_slide,
            # loop re-reads self._cursor at the top

        self.is_presenting = False
        logger.info("Presentation complete — all slides narrated")

    async def on_enter(self) -> None:
        """Start the full presentation when agent enters."""
        logger.info("Agent entered — starting full presentation")
        asyncio.ensure_future(self.run_presentation())


# ---------------------------------------------------------------------------
# Transcript processing (debounce → Claude direct API → execute tools → TTS)
# ---------------------------------------------------------------------------

async def process_full_transcript(agent: PresentationAgent, session: AgentSession) -> None:
    """Process the accumulated transcript after debounce delay."""
    full_transcript = " ".join(agent._pending_parts).strip()
    agent._pending_parts = []

    if not full_transcript:
        agent._is_processing = False
        return

    if is_filler_only(full_transcript):
        logger.info("Ignoring filler-only transcript: '%s'", full_transcript)
        agent._is_processing = False
        return

    agent._is_processing = True
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

    # Split: popups fire immediately, control actions after speech
    CONTROL_TOOLS = ("advance_to_slide", "peek_at_slide", "pause_presentation", "resume_presentation")
    popup_calls = [tc for tc in tool_calls if tc["name"] not in CONTROL_TOOLS]
    control_calls = [tc for tc in tool_calls if tc["name"] in CONTROL_TOOLS]

    # Execute popup tool calls immediately
    if popup_calls:
        await agent.execute_tool_calls(popup_calls)

    # Speak the response
    if response:
        speech = await session.say(response, allow_interruptions=True)
        await speech.wait_for_playout()

    # Execute control tool calls after speech
    if control_calls:
        await agent.execute_tool_calls(control_calls)

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

server = AgentServer()


@server.rtc_session
async def handle_session(ctx: JobContext) -> None:
    await ctx.connect()

    session = AgentSession(
        stt=inference.STT(model="deepgram/nova-3"),
        tts=inference.TTS(model="cartesia/sonic-3"),
    )

    agent = PresentationAgent()

    @session.on("user_input_transcribed")
    def on_transcribed(ev):
        on_user_transcript(ev, agent, session)

    await session.start(
        agent=agent,
        room=ctx.room,
    )


if __name__ == "__main__":
    cli.run_app(server)

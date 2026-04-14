import asyncio
import json
import logging

from dotenv import load_dotenv
from livekit.agents import AgentSession, AgentServer, JobContext, inference, cli
from livekit.agents.voice import Agent

from claude_router import route_slide
from slides import SLIDES

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


class PresentationAgent(Agent):
    def __init__(self) -> None:
        super().__init__(instructions="You are an AI presentation assistant.")
        self.current_slide = 0
        self.history: list[dict] = []
        self.is_presenting = False
        self.interrupted = False
        # Debounce state
        self._pending_parts: list[str] = []
        self._debounce_task: asyncio.Task | None = None
        self._is_processing = False

    async def send_slide(self, index: int) -> None:
        """Send slide change event to the frontend."""
        self.current_slide = index
        await self.session.room_io.room.local_participant.publish_data(
            json.dumps({"slideIndex": index}),
            topic="slide_change",
        )

    async def present_slide(self, index: int) -> None:
        """Narrate a single slide."""
        if index < 0 or index >= len(SLIDES):
            return

        slide = SLIDES[index]
        logger.info("Presenting slide %d: %s", index, slide["title"])

        await self.send_slide(index)
        speech = await self.session.say(slide["narration"], allow_interruptions=True)
        await speech.wait_for_playout()

    async def run_presentation(self) -> None:
        """Auto-narrate through all slides sequentially."""
        self.is_presenting = True

        for i in range(len(SLIDES)):
            if self.interrupted:
                # Wait until the question is handled before resuming
                self.interrupted = False
                # After answering, continue from wherever current_slide is
                i = self.current_slide

            await self.present_slide(i)

            # Small pause between slides
            await asyncio.sleep(1.5)

        self.is_presenting = False
        logger.info("Presentation complete")

    async def on_enter(self) -> None:
        """Start the full presentation when agent enters."""
        logger.info("Agent entered — starting full presentation")
        # Run presentation in background so the agent can handle events
        asyncio.ensure_future(self.run_presentation())


async def process_full_transcript(agent: PresentationAgent, session: AgentSession) -> None:
    """Process the accumulated transcript after debounce delay."""
    # Grab all accumulated parts and reset
    full_transcript = " ".join(agent._pending_parts).strip()
    agent._pending_parts = []

    if not full_transcript:
        agent._is_processing = False
        return

    # Ignore filler-only utterances — just stay quiet
    if is_filler_only(full_transcript):
        logger.info("Ignoring filler-only transcript: '%s'", full_transcript)
        agent._is_processing = False
        return

    agent._is_processing = True
    logger.info("Processing (debounced): '%s' (slide: %d)", full_transcript, agent.current_slide)

    # Mark as interrupted so presentation loop knows
    agent.interrupted = True

    try:
        result = await route_slide(
            transcript=full_transcript,
            current_slide=agent.current_slide,
            history=agent.history,
        )
    except Exception as e:
        logger.error("Claude routing failed: %s", e, exc_info=True)
        await session.say(
            "Sorry, I had trouble processing that. Could you repeat your question?"
        )
        agent._is_processing = False
        return

    # Keep the last 5 conversation turns
    agent.history.append({
        "user": full_transcript,
        "assistant": result.get("response", ""),
    })
    if len(agent.history) > 5:
        agent.history = agent.history[-5:]

    # Handle slide navigation
    should_change = result.get("shouldChangeSlide", False)
    new_index = result.get("slideIndex", agent.current_slide)

    if should_change and 0 <= new_index <= 5:
        logger.info("Changing slide: %d → %d", agent.current_slide, new_index)
        await agent.send_slide(new_index)

    # Speak the response
    response = result.get("response", "")
    if response:
        speech = await session.say(response)
        await speech.wait_for_playout()

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

    # Accumulate this part
    agent._pending_parts.append(text)

    # Cancel previous debounce timer (user is still talking)
    if agent._debounce_task and not agent._debounce_task.done():
        agent._debounce_task.cancel()

    # Start a new timer — only fires if user stays silent for DEBOUNCE_DELAY
    agent._debounce_task = asyncio.ensure_future(
        debounce_and_process(agent, session)
    )


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

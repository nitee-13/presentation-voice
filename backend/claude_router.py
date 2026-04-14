import json
import logging

from anthropic import AsyncAnthropic

from slides import SYSTEM_PROMPT

logger = logging.getLogger("presentation-agent.router")
anthropic_client = AsyncAnthropic()


async def route_slide(
    transcript: str,
    current_slide: int,
    history: list,
    language: str | None = None,
) -> dict:
    """Call Claude to decide which slide to show and what to say."""

    history_str = ""
    if history:
        history_str = "\n\nRecent conversation (with slide context):\n"
        for entry in history:
            slide_ctx = ""
            if "slide_index" in entry:
                slide_ctx = f" [on slide {entry['slide_index'] + 1}: \"{entry['slide_title']}\"]"
            history_str += f"  User{slide_ctx}: {entry['user']}\n"
            history_str += f"  Assistant: {entry['assistant']}\n"

    lang_str = ""
    if language:
        lang_str = f"\n\nIMPORTANT: Respond in {language}. Your entire spoken response MUST be in {language}."

    user_message = (
        f"Current slide index: {current_slide}\n"
        f"User said: \"{transcript}\""
        f"{history_str}"
        f"{lang_str}"
    )

    message = await anthropic_client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=300,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    response_text = message.content[0].text.strip()
    logger.info("Claude raw response: %s", response_text)

    try:
        result = json.loads(response_text)
    except json.JSONDecodeError:
        logger.warning("Failed to parse Claude JSON, using raw text as response")
        result = {
            "slideIndex": current_slide,
            "response": response_text,
            "shouldChangeSlide": False,
        }

    logger.info("Route result: slide=%d, change=%s", result.get("slideIndex", current_slide), result.get("shouldChangeSlide", False))
    return result


async def summarize_conversation(history: list[dict]) -> str:
    """Call Claude to produce a spoken recap of all Q&A so far."""

    turns = ""
    for entry in history:
        turns += f"  User: {entry['user']}\n"
        turns += f"  AI: {entry['assistant']}\n"

    message = await anthropic_client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=400,
        system=(
            "You are an AI presenter. The user has asked you to summarize "
            "everything discussed so far during the presentation Q&A. "
            "Give a concise, natural spoken recap (3-5 sentences). "
            "Start with a conversational opener like 'Sure, here's a quick recap.' "
            "Keep it voice-friendly — no bullet points or markdown."
        ),
        messages=[{"role": "user", "content": f"Here is the conversation so far:\n{turns}\n\nPlease summarize."}],
    )

    return message.content[0].text.strip()

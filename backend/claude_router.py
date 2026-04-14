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
) -> dict:
    """Call Claude to decide which slide to show and what to say."""

    history_str = ""
    if history:
        history_str = "\n\nRecent conversation:\n"
        for entry in history:
            history_str += f"  User: {entry['user']}\n"
            history_str += f"  Assistant: {entry['assistant']}\n"

    user_message = (
        f"Current slide index: {current_slide}\n"
        f"User said: \"{transcript}\""
        f"{history_str}"
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

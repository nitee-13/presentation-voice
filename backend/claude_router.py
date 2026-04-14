import json
import logging

from anthropic import AsyncAnthropic
from pydantic import BaseModel, Field, field_validator

from slides import SYSTEM_PROMPT

logger = logging.getLogger("presentation-agent.router")
anthropic_client = AsyncAnthropic()


class SlideRouteResponse(BaseModel):
    """Validated response from Claude for slide routing."""
    slideIndex: int = Field(ge=0, le=5, description="Target slide index (0-5)")
    response: str = Field(min_length=1, description="Spoken response text")
    shouldChangeSlide: bool = Field(default=False, description="Whether to navigate to a different slide")

    @field_validator("slideIndex")
    @classmethod
    def clamp_slide_index(cls, v: int) -> int:
        return max(0, min(5, v))

    @field_validator("response")
    @classmethod
    def clean_response(cls, v: str) -> str:
        # Strip markdown artifacts that Claude sometimes adds
        return v.strip().strip("`").strip('"')


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
        parsed = SlideRouteResponse.model_validate_json(response_text)
    except Exception as e:
        logger.warning("Pydantic validation failed (%s), falling back to defaults", e)
        parsed = SlideRouteResponse(
            slideIndex=current_slide,
            response=response_text,
            shouldChangeSlide=False,
        )

    result = parsed.model_dump()
    logger.info("Route result: slide=%d, change=%s", result["slideIndex"], result["shouldChangeSlide"])
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

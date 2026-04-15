import json
import logging

from anthropic import AsyncAnthropic

from slides import SLIDES, SYSTEM_PROMPT

logger = logging.getLogger("presentation-agent.router")
anthropic_client = AsyncAnthropic()

_MAX_SLIDE_INDEX = len(SLIDES) - 1

# ---------------------------------------------------------------------------
# Tool definitions for direct Anthropic API calls
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "name": "advance_to_slide",
        "description": (
            "Advance the presentation to a specific slide permanently. Use this for "
            "forward progression: 'next slide', 'skip to slide 5', 'move on'. "
            "The presentation will continue auto-narrating from this slide onward."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "slide_index": {
                    "type": "integer",
                    "description": "0-based slide index to advance to.",
                },
            },
            "required": ["slide_index"],
            "additionalProperties": False,
        },
    },
    {
        "name": "peek_at_slide",
        "description": (
            "Temporarily show a different slide to explain or reference it, without "
            "changing the presentation position. Use this for detours: 'go back to slide 3 "
            "and explain', 'show me the ethics slide again', 'what was on slide 2'. "
            "After the explanation, the presentation resumes from where it was."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "slide_index": {
                    "type": "integer",
                    "description": "0-based slide index to temporarily display.",
                },
            },
            "required": ["slide_index"],
            "additionalProperties": False,
        },
    },
    {
        "name": "show_key_facts",
        "description": (
            "Display a key facts popup on the user's screen. Use this to highlight "
            "important facts, bullet points, or takeaways related to the current topic."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Popup title."},
                "facts": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of fact strings.",
                },
            },
            "required": ["title", "facts"],
            "additionalProperties": False,
        },
    },
    {
        "name": "show_comparison_table",
        "description": (
            "Display a comparison table popup. Use this when comparing concepts, "
            "technologies, approaches, or any side-by-side information."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Table title."},
                "columns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Column header names.",
                },
                "rows": {
                    "type": "array",
                    "items": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "description": "Row data as list of lists.",
                },
            },
            "required": ["title", "columns", "rows"],
            "additionalProperties": False,
        },
    },
    {
        "name": "show_timeline",
        "description": (
            "Display a timeline visualization popup. Use this for historical "
            "progressions or roadmaps."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Timeline title."},
                "events": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "year": {"type": "string"},
                            "label": {"type": "string"},
                        },
                        "required": ["year", "label"],
                        "additionalProperties": False,
                    },
                    "description": "List of timeline events.",
                },
            },
            "required": ["title", "events"],
            "additionalProperties": False,
        },
    },
    {
        "name": "show_concept_cloud",
        "description": (
            "Display a concept cloud (word cloud) popup. Use this to visualize "
            "related terms, keywords, or ideas around a topic."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Cloud title."},
                "concepts": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of concept strings.",
                },
            },
            "required": ["title", "concepts"],
            "additionalProperties": False,
        },
    },
    {
        "name": "show_citations",
        "description": (
            "Display source citations popup. Use this when referencing research papers, "
            "articles, or other authoritative sources."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Citations title."},
                "citations": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of citation strings.",
                },
            },
            "required": ["title", "citations"],
            "additionalProperties": False,
        },
    },
    {
        "name": "pause_presentation",
        "description": (
            "Pause the auto-narration of the presentation. Call this when the user "
            "wants to stop, take a break, read the slide, think, or otherwise pause. "
            "Examples: 'hold on', 'wait', 'let me read this', 'pause', 'stop for now', "
            "'take your time', 'give me a moment'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
    },
    {
        "name": "resume_presentation",
        "description": (
            "Resume the auto-narration from where it left off. Call this when the user "
            "wants to continue the presentation after a pause or Q&A. "
            "Examples: 'continue', 'go on', 'keep going', 'resume', 'carry on', "
            "'okay next', 'I'm ready'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
    },
]


async def route_slide(
    transcript: str,
    current_slide: int,
    history: list,
    language: str | None = None,
) -> dict:
    """Call Claude with tools to decide navigation, popups, and what to say.

    Returns:
        {
            "response": str,           # spoken text
            "tool_calls": list[dict],   # tool_use blocks to execute
        }
    """

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
        max_tokens=500,
        system=SYSTEM_PROMPT,
        tools=TOOLS,
        messages=[{"role": "user", "content": user_message}],
    )

    # Extract text and tool_use blocks from response
    response_text = ""
    tool_calls = []

    for block in message.content:
        if block.type == "text":
            response_text += block.text
        elif block.type == "tool_use":
            tool_calls.append({
                "name": block.name,
                "input": block.input,
            })

    response_text = response_text.strip()
    logger.info(
        "Route result: response=%s, tools=%s",
        response_text[:80] if response_text else "(none)",
        [tc["name"] for tc in tool_calls],
    )

    return {
        "response": response_text,
        "tool_calls": tool_calls,
    }


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

SLIDES = [
    {
        "index": 0,
        "title": "The Future of AI (Introduction)",
        "content": (
            "Generative AI revolution. LLMs accessible to everyone. "
            "$1T+ market by 2030. AI transforming every industry."
        ),
        "narration": (
            "Welcome to The Future of AI! I'll be your presenter today. "
            "We are living through the generative AI revolution. "
            "Large language models are now accessible to everyone, from students to CEOs. "
            "The AI market is projected to exceed one trillion dollars by 2030. "
            "Every single industry is being transformed, from healthcare to finance to entertainment. "
            "Let's dive into how this technology actually works."
        ),
        "keywords": [
            "generative AI", "introduction", "overview", "what is AI",
            "revolution", "market",
        ],
    },
    {
        "index": 1,
        "title": "Large Language Models",
        "content": (
            "Trained on trillions of tokens. Transformer architecture. "
            "Emergent reasoning. Code generation. "
            "GPT-4, Claude, and Gemini leading the field."
        ),
        "narration": (
            "So how do these AI systems actually work? "
            "Large language models are trained on trillions of tokens of text from across the internet. "
            "They use something called the transformer architecture, which allows them to understand context and relationships in language. "
            "What's fascinating is that these models develop emergent reasoning abilities, "
            "meaning they can solve problems they were never explicitly trained on. "
            "Today, GPT-4, Claude, and Gemini are leading the field, each pushing the boundaries of what's possible."
        ),
        "keywords": [
            "LLM", "language model", "transformer", "GPT", "Claude",
            "Gemini", "training", "tokens", "how it works",
        ],
    },
    {
        "index": 2,
        "title": "Real-World Applications",
        "content": (
            "Healthcare diagnosis and drug discovery. "
            "Personalized education at scale. "
            "Creative tools for writing, art, and music. "
            "Enterprise automation."
        ),
        "narration": (
            "Now let's look at where AI is making a real impact today. "
            "In healthcare, AI is helping doctors diagnose diseases earlier and accelerating drug discovery. "
            "In education, we're seeing personalized learning at scale for the first time ever. "
            "Creative professionals are using AI tools for writing, generating art, and even composing music. "
            "And across the enterprise, AI is automating repetitive tasks and powering smarter decision-making. "
            "These aren't future possibilities. They're happening right now."
        ),
        "keywords": [
            "applications", "healthcare", "medicine", "education",
            "creative", "industry", "use cases", "real world",
        ],
    },
    {
        "index": 3,
        "title": "Ethical Considerations",
        "content": (
            "Bias in training data and outputs. "
            "Misinformation and deepfakes. "
            "Alignment problem — keeping AI goals human-aligned. "
            "Regulation."
        ),
        "narration": (
            "Of course, with great power comes great responsibility. "
            "AI models can inherit biases from their training data, leading to unfair or discriminatory outputs. "
            "Misinformation and deepfakes are a growing concern as AI-generated content becomes harder to detect. "
            "There's also the alignment problem — how do we ensure AI systems stay aligned with human values and goals? "
            "Governments around the world are now working on regulation frameworks. "
            "Getting the ethics right is just as important as getting the technology right."
        ),
        "keywords": [
            "ethics", "bias", "misinformation", "deepfake", "alignment",
            "safety", "risks", "dangers", "regulation",
        ],
    },
    {
        "index": 4,
        "title": "The Road Ahead",
        "content": (
            "AGI debate and active pursuit. "
            "Multimodal AI — vision, audio, robotics. "
            "Autonomous AI agents. "
            "What the next decade looks like."
        ),
        "narration": (
            "So what's coming next? "
            "The biggest question in AI right now is whether we'll achieve artificial general intelligence, or AGI. "
            "We're also seeing the rise of multimodal AI — systems that can see, hear, and interact with the physical world through robotics. "
            "Autonomous AI agents that can plan, reason, and take actions on your behalf are already emerging. "
            "The next decade will fundamentally reshape how we work, create, and live. "
            "It's an exciting and uncertain time."
        ),
        "keywords": [
            "future", "AGI", "multimodal", "agents", "autonomous",
            "robots", "next decade", "road ahead",
        ],
    },
    {
        "index": 5,
        "title": "Key Takeaways",
        "content": (
            "AI is a tool — human judgment still essential. "
            "Upskilling in AI literacy is non-negotiable. "
            "Human + AI collaboration wins."
        ),
        "narration": (
            "Let me wrap up with the key takeaways. "
            "First, AI is a tool, not a replacement. Human judgment, creativity, and empathy remain essential. "
            "Second, upskilling in AI literacy is no longer optional — it's a must for everyone. "
            "And finally, the future belongs to human plus AI collaboration. "
            "The teams and individuals who learn to work with AI will have an enormous advantage. "
            "Thank you for listening! Feel free to ask me any questions about what we've covered."
        ),
        "keywords": [
            "summary", "conclusion", "takeaways", "key points",
            "collaboration", "human", "upskill",
        ],
    },
]


def _build_system_prompt() -> str:
    slide_descriptions = ""
    for s in SLIDES:
        human_num = s['index'] + 1
        slide_descriptions += (
            f"  Slide {human_num} (index {s['index']}): \"{s['title']}\"\n"
            f"    Content: {s['content']}\n"
            f"    Keywords: {', '.join(s['keywords'])}\n\n"
        )

    return f"""You are an AI presenter delivering a talk called "The Future of AI".
You control a 6-slide presentation deck. Here are all the slides:

{slide_descriptions}
You will receive:
- The current slide index (0-5, where 0 = slide 1, 5 = slide 6)
- The user's spoken transcript
- Recent conversation history for context

IMPORTANT: Slides are numbered 1-6 for the user, but use index 0-5 in your JSON response.
- "first slide" or "slide 1" = index 0
- "second slide" or "slide 2" = index 1
- "last slide" or "slide 6" = index 5

Your job:
1. Determine which slide best matches the user's question or command.
2. Provide a short, spoken-language response (2-3 sentences max, voice-friendly).
3. Handle navigation commands like "next slide", "go back", "previous", "go to slide 3", etc.
4. Use conversation history to understand contextual references (e.g. "tell me more about that").

Return ONLY valid JSON in this exact format — no markdown, no extra text:
{{"slideIndex": <number 0-5>, "response": "<your spoken response>", "shouldChangeSlide": <true or false>}}

Guidelines:
- Keep responses concise and natural, as they will be read aloud.
- Use conversational openers like "Great question!", "Sure thing!", "Absolutely!" when appropriate.
- If the user says "next", increment the slide index by 1 (cap at 5).
- If the user says "back" or "previous", decrement by 1 (minimum 0).
- If the question matches a different slide's content, navigate there and set shouldChangeSlide to true.
- If the question is about the current slide, keep the same index and set shouldChangeSlide to false.
- When referring to slides by number in your response, use human numbering (1-6), not index (0-5).
"""


SYSTEM_PROMPT = _build_system_prompt()

# AI Voice Presentation App — Full Project Plan

> Everything discussed, decisions made, and how to build it.

---

## What We're Building

A voice-powered AI presentation app where:

- The AI narrates 6 slides on **"The Future of AI"**
- The user can **speak at any time** to ask questions
- The AI **automatically jumps to the right slide** based on the question
- The user can **barge in** mid-sentence and the AI stops instantly
- The AI says **filler words** ("let me think...") while processing
- Both a **frontend** (React) and **backend** (LiveKit Agent + FastAPI token server) are implemented
- The AI **auto-narrates** the first slide when a user joins

---

## Tech Stack — Final Decisions

| Layer | Technology | Why |
|---|---|---|
| Frontend | React | Component-based, easy LiveKit SDK integration |
| Token Server | Python FastAPI | Lightweight, async — generates JWT tokens for frontend |
| Agent Worker | LiveKit Agents (Python) | Standalone worker process — handles voice pipeline + Claude |
| Voice infrastructure | LiveKit Cloud | Free tier (1,000 min/month), handles STT + TTS + barge-in |
| STT | Deepgram Nova-3 | Via LiveKit Inference — no separate Deepgram key needed |
| TTS | Cartesia Sonic-3 | Via LiveKit Inference — no separate Cartesia key needed |
| LLM / AI brain | Claude API (Anthropic) | Slide routing + spoken responses |
| Transport | WebRTC (via LiveKit) | Low-latency, browser-native |

---

## API Keys You Need

| Key | Where to get it | Cost |
|---|---|---|
| `LIVEKIT_API_KEY` | cloud.livekit.io — sign up free | Free (1,000 min/month) |
| `LIVEKIT_API_SECRET` | Same dashboard | Free |
| `LIVEKIT_URL` | Your LiveKit Cloud project URL | Free |
| `ANTHROPIC_API_KEY` | console.anthropic.com | Pay-per-token (pennies for a demo) |

**That's it. No Deepgram account. No ElevenLabs account. No Cartesia account.**

LiveKit Inference acts as a unified gateway — STT, TTS, and WebRTC all go through your single LiveKit key.

---

## Why We Chose LiveKit Over Vapi

| Feature | Vapi | LiveKit |
|---|---|---|
| Free tier | $10 one-time credit only | 1,000 min/month, no credit card |
| Open source | No | Yes — self-hostable |
| STT | Needs separate key or bundled | Via LiveKit Inference (1 key) |
| TTS | Needs separate key or bundled | Via LiveKit Inference (1 key) |
| Barge-in / VAD | Built-in, automatic | Built-in, automatic |
| Echo cancellation | Proprietary model | Built-in AEC + background voice filter |
| Claude support | BYO key as plugin | BYO key directly in agent worker |
| Browser/WebRTC | WebSocket-based | Native WebRTC — perfect for web apps |
| Filler words | Automatic proprietary model | `session.say()` + system prompt engineering |

---

## How STT and TTS Work

### STT (Speech → Text)

LiveKit streams the mic audio through **Deepgram Nova-3** inside its own infrastructure. You never call Deepgram directly.

```
mic audio (WebRTC) → LiveKit Room → Deepgram Nova-3 → transcript text
```

### TTS (Text → Speech)

Your backend sends a text string to **Cartesia Sonic-3** via LiveKit. The audio streams back to the browser in real time.

```
response text → Cartesia Sonic-3 → audio stream → LiveKit Room → browser speaker
```

### One key for both:

```python
session = AgentSession(
    stt=inference.STT(model="deepgram/nova-3"),      # just LiveKit key
    tts=inference.TTS(model="cartesia/sonic-3"),      # just LiveKit key
    # LLM handled via custom Agent class (Claude API called directly)
)
```

---

## How Barge-In Works

LiveKit runs the microphone continuously in the background, even while the AI is speaking.

### Three layers of protection:

**Layer 1 — Acoustic Echo Cancellation (AEC)**
Signal processing that mathematically subtracts the speaker output from the mic input before any AI sees it. The AI's own voice never reaches the transcription model.

**Layer 2 — Background voice filter**
LiveKit's proprietary model isolates the primary speaker and blocks TVs, echoes, and background voices.

**Layer 3 — Adaptive Interruption Handling (v1.5+)**
An audio-based ML model that distinguishes genuine barge-ins from conversational backchanneling ("mm-hmm", "yeah", "okay"). Enabled by default. When a false interruption is detected, the agent resumes playback from where it left off — no re-generation needed.

### What we build (the state machine):

```
AI speaking + mic running in background
         ↓
user makes sound → LiveKit VAD detects voice
         ↓
adaptive model: is this a real interruption or "mm-hmm"?
         ↓ (real interruption)
TTS cancelled instantly → new transcript captured
         ↓
send to Claude → new response → TTS plays
         ↓
back to listening
```

---

## How Slide Routing Works

We use **Claude as the router** — not vector embeddings. For 6 slides, LLM routing is faster, more accurate, and needs zero extra infrastructure.

### Why not vector search?

Vector search shines with hundreds of documents. For 6 slides, sending all slide descriptions to Claude in a single prompt is cheaper, faster, and semantically smarter.

### The routing prompt:

Each slide has a **rich knowledge chunk** — not just a title, but full content, talking points, and keywords. Claude reads the user's question, compares it to all 6 chunks, and returns a JSON object:

```json
{
  "slideIndex": 3,
  "response": "Great question — the ethical risks of AI include bias in training data...",
  "shouldChangeSlide": true
}
```

### The system prompt structure:

```
You are an AI presenter for a talk titled "The Future of AI".
You control a 6-slide deck.

Slides:
0: Introduction — what generative AI is, the revolution underway, market size
1: Large Language Models — transformers, training data, GPT/Claude/Gemini
2: Real-World Applications — healthcare, education, creative industries
3: Ethical Considerations — bias, misinformation, alignment, safety
4: The Road Ahead — AGI, multimodal AI, autonomous agents
5: Key Takeaways — summary, human+AI collaboration

Current slide: {current_slide_index}

Recent conversation:
{conversation_history}

User said: "{transcript}"

Return ONLY valid JSON:
{"slideIndex": 0, "response": "...", "shouldChangeSlide": false}

Rules:
- Keep response under 2-3 sentences (voice-friendly)
- If user says "next" → slideIndex = current + 1
- If user says "back" → slideIndex = current - 1
- shouldChangeSlide = true only if moving to a different slide
- Use conversation history to understand references like "tell me more about that"
```

**Note:** We maintain a rolling window of the last 5 exchanges so Claude can understand contextual references like "tell me more" or "go back to that topic".

---

## Filler Words

LiveKit does NOT have Vapi's automatic filler model. We implement it in two ways:

### Method 1 — Immediate `session.say()` injection

```python
async def on_user_turn_completed(self, turn_ctx: llm.ChatContext, new_message: llm.ChatMessage):
    transcript = new_message.text_content

    # Speak filler immediately (non-interruptible so it finishes before response)
    filler = await self.session.say("Hmm, let me think about that...", allow_interruptions=False)
    await filler.wait_for_playout()

    # Claude processes
    response = await call_claude(transcript, self.current_slide, self.history)

    # Then speak the real answer
    await self.session.say(response["response"])
```

### Method 2 — System prompt engineering

Tell Claude to include natural filler words in its responses:

```
Use natural spoken language. Start responses with "So...", "Great question —",
"Hmm, yeah..." or similar conversational openers. Keep responses short (2-3 sentences).
```

---

## End-to-End Flow

### Initial Connection
```
1. Frontend fetches JWT token from FastAPI token server (POST /token)
        ↓
2. Frontend connects to LiveKit room using token via <LiveKitRoom>
        ↓
3. LiveKit Agent worker detects room join → agent's on_enter() fires
        ↓
4. Agent auto-narrates slide 0: session.say("Welcome to The Future of AI...")
        ↓
5. Agent sends slide index to frontend via send_text(topic="slide_change")
```

### Q&A Loop
```
1. User speaks
        ↓
2. Browser captures mic via WebRTC → streams to LiveKit room
        ↓
3. LiveKit pipes audio to Deepgram Nova-3 (STT)
        ↓
4. Transcript fires to agent worker via on_user_turn_completed()
        ↓
5. Agent immediately calls session.say("One moment...") [filler]
        ↓
6. Agent calls Claude API with:
   - transcript
   - current slide index
   - conversation history (last 5 exchanges)
   - all 6 slide knowledge chunks
        ↓
7. Claude returns JSON: { slideIndex, response, shouldChangeSlide }
        ↓
8. Agent sends response text to Cartesia Sonic-3 (TTS) via LiveKit
        ↓
9. LiveKit streams audio back to browser
        ↓
10. Two things happen simultaneously:
    → Browser plays AI voice through speakers
    → Frontend receives slideIndex via send_text and jumps to that slide

--- BARGE-IN (can happen at step 9 or 10) ---

User starts talking → LiveKit adaptive model detects real interruption
        ↓
TTS cancelled instantly
        ↓
Loop restarts from step 1
```

---

## File Structure

```
ai-voice-presentation/
├── frontend/
│   ├── src/
│   │   ├── App.jsx              # Main React component + LiveKitRoom provider
│   │   ├── PresentationRoom.jsx # Room content (slides, controls, audio)
│   │   ├── SlideViewer.jsx      # Renders current slide
│   │   ├── VoiceControls.jsx    # Mic button, status indicator
│   │   └── slides.js            # Slide content for rendering
│   ├── package.json
│   └── .env                     # VITE_LIVEKIT_URL, VITE_TOKEN_SERVER_URL
│
├── backend/
│   ├── agent.py                 # LiveKit agent worker (standalone process)
│   ├── server.py                # FastAPI token server (separate process)
│   ├── slides.py                # Slide data and knowledge chunks
│   ├── claude_router.py         # Claude API call for slide routing
│   ├── requirements.txt
│   └── .env                     # LIVEKIT_* keys + ANTHROPIC_API_KEY
│
└── README.md
```

**Important architecture note:** `agent.py` and `server.py` are **separate processes**:
- `agent.py` — LiveKit Agent worker, runs via `python agent.py dev`
- `server.py` — FastAPI HTTP server, runs via `uvicorn server:app`

---

## The 6 Slides — Content + Knowledge Chunks

### Slide 0 — The Future of AI (Introduction)
**Talking points:** Generative AI revolution, LLMs accessible to everyone, $1T+ market by 2030, AI transforming every industry
**Keywords:** generative AI, introduction, overview, what is AI, revolution, market

### Slide 1 — Large Language Models
**Talking points:** Trained on trillions of tokens, transformer architecture, emergent reasoning, code generation, GPT-4/Claude/Gemini leading the field
**Keywords:** LLM, language model, transformer, GPT, Claude, Gemini, training, tokens, how it works

### Slide 2 — Real-World Applications
**Talking points:** Healthcare diagnosis and drug discovery, personalized education at scale, creative tools for writing/art/music, enterprise automation
**Keywords:** applications, healthcare, medicine, education, creative, industry, use cases, real world

### Slide 3 — Ethical Considerations
**Talking points:** Bias in training data and outputs, misinformation and deepfakes, alignment problem, keeping AI goals human-aligned, regulation
**Keywords:** ethics, bias, misinformation, deepfake, alignment, safety, risks, dangers, regulation

### Slide 4 — The Road Ahead
**Talking points:** AGI debate and active pursuit, multimodal AI (vision, audio, robotics), autonomous AI agents, what the next decade looks like
**Keywords:** future, AGI, multimodal, agents, autonomous, robots, next decade, road ahead

### Slide 5 — Key Takeaways
**Talking points:** AI is a tool — human judgment still essential, upskilling in AI literacy non-negotiable, human+AI collaboration wins
**Keywords:** summary, conclusion, takeaways, key points, collaboration, human, upskill

---

## Backend Code Outline

### Token Server (`backend/server.py`)

```python
# backend/server.py — FastAPI token server (separate process from agent)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from livekit import api
import os

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.post("/token")
async def get_token(request: dict):
    token = api.AccessToken(
        os.getenv("LIVEKIT_API_KEY"),
        os.getenv("LIVEKIT_API_SECRET"),
    ).with_identity(
        request.get("identity", "user")
    ).with_grants(
        api.VideoGrants(room_join=True, room="presentation")
    )
    return {"token": token.to_jwt()}
```

### Agent Worker (`backend/agent.py`)

```python
# backend/agent.py — LiveKit agent worker (standalone process)

from livekit.agents import AgentSession, AgentServer, inference, llm
from livekit.agents.voice import Agent
from anthropic import AsyncAnthropic
import json

anthropic_client = AsyncAnthropic()

class PresentationAgent(Agent):
    def __init__(self):
        super().__init__()
        self.current_slide = 0
        self.history = []  # Rolling conversation history

    async def on_enter(self):
        """Called when agent becomes active — auto-narrate first slide."""
        await self.session.say(
            "Welcome to The Future of AI. Let's start with an overview of the "
            "generative AI revolution and why it matters.",
            allow_interruptions=True,
        )
        await self.session.room.local_participant.send_text(
            json.dumps({"slideIndex": 0}),
            topic="slide_change",
        )

    async def on_user_turn_completed(self, turn_ctx: llm.ChatContext, new_message: llm.ChatMessage):
        transcript = new_message.text_content

        # 1. Filler while thinking
        filler = await self.session.say("Hmm, one moment...", allow_interruptions=True)

        # 2. Call Claude for routing + response
        try:
            result = await route_slide(transcript, self.current_slide, self.history)
        except Exception:
            await self.session.say("Sorry, I had trouble processing that. Could you repeat?")
            return

        # 3. Update conversation history (keep last 5 exchanges)
        self.history.append({"user": transcript, "assistant": result["response"]})
        if len(self.history) > 5:
            self.history.pop(0)

        # 4. Update slide (send to frontend via text stream)
        if result.get("shouldChangeSlide"):
            self.current_slide = result["slideIndex"]
            await self.session.room.local_participant.send_text(
                json.dumps({"slideIndex": self.current_slide}),
                topic="slide_change",
            )

        # 5. Speak the response
        await self.session.say(result["response"])


async def route_slide(transcript: str, current_slide: int, history: list) -> dict:
    history_str = "\n".join(
        f"User: {h['user']}\nAI: {h['assistant']}" for h in history
    ) or "(no prior conversation)"

    response = await anthropic_client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=300,
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": f"Current slide: {current_slide}\n\nRecent conversation:\n{history_str}\n\nUser said: {transcript}"
        }],
    )

    # Parse with fallback for malformed JSON
    try:
        return json.loads(response.content[0].text)
    except json.JSONDecodeError:
        return {"slideIndex": current_slide, "response": response.content[0].text, "shouldChangeSlide": False}


# --- LiveKit Agent entrypoint ---
server = AgentServer()

@server.rtc_session(agent_name="presentation-agent")
async def presentation_session(ctx):
    session = AgentSession(
        stt=inference.STT(model="deepgram/nova-3"),
        tts=inference.TTS(model="cartesia/sonic-3"),
    )
    await session.start(room=ctx.room, agent=PresentationAgent())

if __name__ == "__main__":
    from livekit.agents import cli
    cli.run_app(server)
```

---

## Frontend Code Outline

### App Root (`frontend/src/App.jsx`)

```jsx
// frontend/src/App.jsx — Handles token fetch + LiveKitRoom provider

import { LiveKitRoom, RoomAudioRenderer } from '@livekit/components-react';
import { useState, useEffect } from 'react';
import PresentationRoom from './PresentationRoom';

const TOKEN_SERVER = import.meta.env.VITE_TOKEN_SERVER_URL || 'http://localhost:8000';
const LIVEKIT_URL = import.meta.env.VITE_LIVEKIT_URL;

export default function App() {
  const [token, setToken] = useState(null);

  useEffect(() => {
    fetch(`${TOKEN_SERVER}/token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ identity: `user-${Date.now()}` }),
    })
      .then(res => res.json())
      .then(data => setToken(data.token));
  }, []);

  if (!token) return <div className="loading">Connecting...</div>;

  return (
    <LiveKitRoom serverUrl={LIVEKIT_URL} token={token} connect={true}>
      <RoomAudioRenderer />  {/* Required — renders agent's voice */}
      <PresentationRoom />
    </LiveKitRoom>
  );
}
```

### Presentation Room (`frontend/src/PresentationRoom.jsx`)

```jsx
// frontend/src/PresentationRoom.jsx — Slide display + data channel listener

import { useDataChannel, useVoiceAssistant } from '@livekit/components-react';
import { useState } from 'react';
import { SLIDES } from './slides';
import SlideViewer from './SlideViewer';

export default function PresentationRoom() {
  const [currentSlide, setCurrentSlide] = useState(0);
  const { state: agentState } = useVoiceAssistant();

  // Listen for slide change events from agent
  useDataChannel('slide_change', (msg) => {
    const data = JSON.parse(new TextDecoder().decode(msg.payload));
    setCurrentSlide(data.slideIndex);
  });

  return (
    <div className="app">
      <SlideViewer slide={SLIDES[currentSlide]} index={currentSlide} total={SLIDES.length} />
      <SlideNav current={currentSlide} total={SLIDES.length} onChange={setCurrentSlide} />
      <StatusBar state={agentState} />  {/* shows: listening / thinking / speaking */}
    </div>
  );
}
```

---

## Backend Requirements

```txt
# backend/requirements.txt
fastapi
uvicorn
livekit-agents[inference]    # includes STT/TTS via LiveKit Inference (no plugin packages needed)
livekit-api                  # for JWT token generation in the token server
anthropic
python-dotenv
```

**Note:** `livekit-plugins-deepgram` and `livekit-plugins-cartesia` are NOT needed. Those are only required when using provider APIs directly with your own Deepgram/Cartesia keys. We use LiveKit Inference which routes through your LiveKit key.

---

## Frontend Requirements

```json
{
  "dependencies": {
    "@livekit/components-react": "^2.x",
    "@livekit/client-sdk-js": "^2.x",
    "react": "^18.x",
    "react-dom": "^18.x"
  }
}
```

---

## Environment Variables

### Backend `.env`

```env
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=your_livekit_api_key
LIVEKIT_API_SECRET=your_livekit_api_secret
ANTHROPIC_API_KEY=your_anthropic_key
```

### Frontend `.env`

```env
VITE_LIVEKIT_URL=wss://your-project.livekit.cloud
VITE_TOKEN_SERVER_URL=http://localhost:8000
```

---

## How to Run

You need **3 terminal windows** — the agent and token server are separate processes.

### Terminal 1 — Token Server (FastAPI)

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env  # fill in your keys
uvicorn server:app --reload --port 8000
```

### Terminal 2 — Agent Worker (LiveKit)

```bash
cd backend
python agent.py dev    # LiveKit dev mode — auto connects to LiveKit Cloud
```

### Terminal 3 — Frontend

```bash
cd frontend
npm install
cp .env.example .env  # fill in your LiveKit URL
npm run dev
```

---

## Key Technical Decisions — Summary

| Decision | Choice | Reason |
|---|---|---|
| Voice platform | LiveKit | Real free tier, open source, native WebRTC |
| Backend architecture | Agent worker + FastAPI token server | Agent is a standalone LiveKit worker; FastAPI only serves JWT tokens |
| STT provider | Deepgram Nova-3 | Best accuracy via LiveKit Inference, no extra key |
| TTS provider | Cartesia Sonic-3 | Low latency, natural voice, via LiveKit Inference |
| LLM | Claude (claude-sonnet-4-6) | Best semantic understanding for slide routing |
| Slide routing method | LLM routing (not vector search) | 6 slides = overkill for embeddings, LLM is faster and smarter |
| Agent→Frontend comms | `send_text(topic="slide_change")` | Higher-level API than raw `publish_data`, guaranteed delivery |
| Filler words | `session.say()` + prompt engineering | LiveKit doesn't auto-generate fillers like Vapi |
| Barge-in | LiveKit adaptive interruption (v1.5+) | Built-in ML model, no code needed, enabled by default |
| Echo cancellation | LiveKit AEC + background voice filter | 3-layer pipeline, handles laptop speakers reliably |
| Conversation context | Rolling 5-exchange history | Lets Claude understand "tell me more" / "go back to that" |
| Frontend | Vite + React | Single-page app, no routing/SSR needed — lightest path |

---

## What to Build First (Recommended Order)

1. Set up LiveKit Cloud account → get API keys
2. Set up Anthropic account → get Claude API key
3. Build `backend/slides.py` — the 6 slide knowledge chunks
4. Build `backend/claude_router.py` — the Claude routing call with error handling
5. Build `backend/agent.py` — LiveKit agent worker with AgentServer entrypoint
6. Build `backend/server.py` — FastAPI token server
7. Test agent alone using LiveKit Agents Playground (no frontend needed yet)
8. Build `frontend/src/slides.js` — slide content for rendering
9. Build `frontend/src/SlideViewer.jsx` — the slide UI
10. Build `frontend/src/App.jsx` — token fetch + LiveKitRoom provider
11. Build `frontend/src/PresentationRoom.jsx` — data channel listener + voice assistant
12. Connect all 3 processes and test end-to-end

---

*Plan compiled from full design session. Updated with verified LiveKit docs (2026-04-14). Ready to build.*
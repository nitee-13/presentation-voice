# AI Voice Presentation

A voice-powered AI presentation app where an AI agent narrates slides on "The Future of AI", answers audience questions in real-time, and automatically navigates to the right slide based on what the user asks.

## Features

- **AI narration** — Agent auto-presents 6 slides with natural speech
- **Voice Q&A** — Speak at any time to ask questions; the AI responds conversationally
- **Smart slide routing** — AI automatically jumps to the relevant slide based on your question
- **Barge-in support** — Interrupt the AI mid-sentence and it stops instantly
- **Filler words** — Natural "let me think..." responses while processing

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React (Vite) |
| Token Server | Python FastAPI |
| Agent Worker | LiveKit Agents (Python) |
| Voice (STT) | Deepgram Nova-3 via LiveKit Inference |
| Voice (TTS) | Cartesia Sonic-3 via LiveKit Inference |
| LLM | Claude (Anthropic API) |
| Transport | WebRTC via LiveKit |

## Architecture

```
Browser (React + Vite)
    │
    ├── fetches JWT token from ──→ FastAPI Token Server (:8000)
    │
    └── connects via WebRTC to ──→ LiveKit Cloud
                                       │
                                       └── LiveKit Agent Worker
                                             ├── STT: Deepgram Nova-3
                                             ├── TTS: Cartesia Sonic-3
                                             └── LLM: Claude API (slide routing + responses)
```

## Prerequisites

- Python 3.12 (conda env: `presentation-voice`)
- Node.js 18+
- [LiveKit Cloud account](https://cloud.livekit.io) (free tier: 1,000 min/month)
- [Anthropic API key](https://console.anthropic.com)

## Setup

### Backend

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env  # fill in your API keys
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env  # fill in your LiveKit URL
```

## Running

You need **3 terminal windows**:

```bash
# Terminal 1 — Token Server
cd backend
uvicorn server:app --reload --port 8000

# Terminal 2 — Agent Worker
cd backend
python agent.py dev

# Terminal 3 — Frontend
cd frontend
npm run dev
```

## Environment Variables

### Backend (`backend/.env`)

```
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=your_livekit_api_key
LIVEKIT_API_SECRET=your_livekit_api_secret
ANTHROPIC_API_KEY=your_anthropic_key
```

### Frontend (`frontend/.env`)

```
VITE_LIVEKIT_URL=wss://your-project.livekit.cloud
VITE_TOKEN_SERVER_URL=http://localhost:8000
```

## Project Structure

```
presentation-voice/
├── frontend/
│   ├── src/
│   │   ├── App.jsx              # LiveKitRoom provider + token fetch
│   │   ├── PresentationRoom.jsx # Slide display + data channel listener
│   │   ├── SlideViewer.jsx      # Renders current slide
│   │   ├── VoiceControls.jsx    # Mic button, status indicator
│   │   └── slides.js            # Slide content for rendering
│   └── ...
├── backend/
│   ├── agent.py                 # LiveKit agent worker (standalone process)
│   ├── server.py                # FastAPI token server (separate process)
│   ├── slides.py                # Slide data and knowledge chunks
│   └── claude_router.py         # Claude API call for slide routing
├── plan.md                      # Full project plan and design decisions
└── README.md
```

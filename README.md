# AI Voice Presentation

A voice-powered AI presentation app where an AI agent ("Devi") narrates slides on "Introduction to AI", answers audience questions in real-time, and automatically navigates to the relevant slide based on what the user asks.

## Demo

[![Watch the demo](https://img.youtube.com/vi/rAV0l_eUSgs/maxresdefault.jpg)](https://youtu.be/rAV0l_eUSgs)

## Features

- **AI narration** — Agent auto-narrates 11 slides with natural, chunked speech
- **Voice Q&A** — Speak at any time to ask questions; the AI responds conversationally
- **Smart slide routing** — AI automatically jumps to the relevant slide using Claude tool use
- **Two-pointer navigation** — Presentation cursor tracks narration position; visual pointer jumps freely for Q&A
- **Barge-in support** — Interrupt the AI mid-sentence and it stops instantly
- **Interactive popups** — Key facts, comparison tables, timelines, and citations displayed as overlays
- **Filler speech** — Natural "let me think..." responses when Claude takes longer than 5 seconds
- **Live captions** — Real-time transcription of agent speech with toggle
- **Multi-language** — Switch spoken language mid-presentation (Spanish, French, German, Japanese, etc.)
- **Voice feedback** — End-of-session star rating and comment collection via voice
- **Pause/resume** — Pause and resume auto-narration at any time

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 19 (Vite) |
| Token Server | Python FastAPI |
| Agent Worker | LiveKit Agents (Python) |
| Voice (STT) | Deepgram Nova-3 via LiveKit Inference |
| Voice (TTS) | Cartesia Sonic-3 via LiveKit Inference |
| LLM | Claude Sonnet (routing + responses) / Claude Haiku (start detection + fillers) |
| Transport | WebRTC via LiveKit |
| Deployment | Railway (backend) + Vercel (frontend) |

## Architecture

```
Browser (React + Vite)
    |
    |-- fetches JWT token from --> FastAPI Token Server (:8000)
    |
    +-- connects via WebRTC to --> LiveKit Cloud
                                       |
                                       +-- LiveKit Agent Worker
                                             |-- STT: Deepgram Nova-3
                                             |-- TTS: Cartesia Sonic-3
                                             +-- LLM: Claude API
                                                   |-- Sonnet: slide routing + tool use + responses
                                                   +-- Haiku: start intent detection + filler generation

Data Channels:
    slide_change      Agent --> Frontend    (slide navigation)
    ui_popup          Agent --> Frontend    (key facts, tables, timelines, citations)
    feedback_update   Agent --> Frontend    (feedback phase updates)
    user_slide_nav    Frontend --> Agent    (keyboard arrow navigation)
    feedback_control  Frontend --> Agent    (start feedback flow)
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

## How It Works

1. **Intro phase** — Devi introduces herself and waits for the user to say "start"
2. **Narration phase** — Slides are narrated in order, chunked into 3-sentence batches for natural pacing
3. **Q&A** — User can ask questions at any point; Claude routes to the relevant slide and responds
4. **Tool use** — Claude can invoke tools: `advance_to_slide`, `peek_at_slide`, `show_key_facts`, `show_comparison_table`, `show_timeline`, `show_citations`, `pause_presentation`, `resume_presentation`, `end_presentation`
5. **Feedback phase** — After ending, Devi collects a 1-5 star rating and optional comment via voice

## Project Structure

```
presentation-voice/
├── frontend/
│   ├── src/
│   │   ├── App.jsx              # LiveKitRoom provider + token fetch
│   │   ├── PresentationRoom.jsx # Slide display + data channels + keyboard nav
│   │   ├── SlideViewer.jsx      # Renders current slide with fade transitions
│   │   ├── VoiceControls.jsx    # Status indicator (listening/thinking/speaking)
│   │   ├── Captions.jsx         # Live transcription display
│   │   ├── QAPanel.jsx          # Q&A history panel
│   │   ├── Popup.jsx            # Modal for facts, tables, timelines, citations
│   │   ├── FeedbackOverlay.jsx  # End-of-session rating and feedback
│   │   ├── ErrorBoundary.jsx    # React error boundary
│   │   └── slides.js            # Frontend slide definitions (11 slides)
│   └── ...
├── backend/
│   ├── agent.py                 # LiveKit agent worker — narration, Q&A, feedback
│   ├── server.py                # FastAPI token server
│   ├── slides.py                # Slide data loading + system prompt generation
│   ├── claude_router.py         # Claude API — routing, tool use, prompt caching
│   └── preprocess.py            # PDF-to-slide extraction (pdfplumber + pdf2image)
├── data/
│   ├── slides_data.json         # Preprocessed slide metadata
│   ├── slides.pdf               # Source PDF
│   └── slides/                  # Extracted PNG images (slide_0.png - slide_10.png)
├── Dockerfile                   # Backend container for Railway
├── railway.json                 # Railway deployment config
├── plan.md                      # Technical design document
└── README.md
```

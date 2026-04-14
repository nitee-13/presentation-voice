import logging
import os
import uuid

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from livekit.api import AccessToken, VideoGrants
from pydantic import BaseModel

load_dotenv()

logger = logging.getLogger("presentation-token-server")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")

app = FastAPI(title="Presentation Voice - Token Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class TokenRequest(BaseModel):
    identity: str = "presenter"


@app.post("/token")
async def create_token(body: TokenRequest):
    """Generate a LiveKit JWT token for the frontend to join a room."""
    room_name = f"presentation-{uuid.uuid4().hex[:8]}"
    token = (
        AccessToken(
            api_key=os.getenv("LIVEKIT_API_KEY"),
            api_secret=os.getenv("LIVEKIT_API_SECRET"),
        )
        .with_identity(body.identity)
        .with_grants(VideoGrants(room_join=True, room=room_name))
    )
    jwt = token.to_jwt()
    logger.info("Token generated for identity: %s, room: %s", body.identity, room_name)
    return {"token": jwt}

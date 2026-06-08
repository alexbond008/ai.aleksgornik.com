"""
AI Aleks — FastAPI backend.

Endpoints:
  POST /auth/register   — Kit.com email gate, returns JWT
  GET  /auth/me         — validate token, return user info + remaining messages
  POST /chat            — streaming RAG chat (requires valid JWT)
  GET  /health          — liveness check
"""

import os
import uuid
from typing import AsyncGenerator, List, Optional

import anthropic
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, EmailStr

load_dotenv()

from backend.auth import create_token, decode_token, subscribe_to_kit
from backend.persona import SYSTEM_PROMPT
from backend.rag import build_rag_prompt, retrieve_context
from backend.rate_limit import check_and_increment, get_remaining

app = FastAPI(title="AI Aleks", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_anthropic_client: Optional[anthropic.AsyncAnthropic] = None


def get_anthropic_client() -> anthropic.AsyncAnthropic:
    global _anthropic_client
    if _anthropic_client is None:
        _anthropic_client = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    return _anthropic_client


# ---------------------------------------------------------------------------
# Auth models
# ---------------------------------------------------------------------------


class RegisterRequest(BaseModel):
    name: str
    email: EmailStr


class RegisterResponse(BaseModel):
    token: str
    remaining_messages: int


class MeResponse(BaseModel):
    user_id: str
    email: str
    remaining_messages: int


# ---------------------------------------------------------------------------
# Chat models
# ---------------------------------------------------------------------------


class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage]


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------


def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing or invalid token")
    token = authorization.split(" ", 1)[1]
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    return payload


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/auth/register", response_model=RegisterResponse)
async def register(body: RegisterRequest):
    kit_ok = await subscribe_to_kit(body.name, body.email)
    if not kit_ok:
        # Log failure but don't block access — Kit is best-effort for lead capture.
        # A hard failure here would break the entire onboarding flow.
        import logging
        logging.warning("Kit subscription failed for %s — granting access anyway", body.email)

    user_id = str(uuid.uuid5(uuid.NAMESPACE_URL, body.email.lower()))
    token = create_token(user_id, body.email)
    return RegisterResponse(token=token, remaining_messages=get_remaining(user_id))


@app.get("/auth/me", response_model=MeResponse)
def me(user: dict = Depends(get_current_user)):
    return MeResponse(
        user_id=user["sub"],
        email=user["email"],
        remaining_messages=get_remaining(user["sub"]),
    )


@app.post("/chat")
async def chat(body: ChatRequest, user: dict = Depends(get_current_user)):
    user_id = user["sub"]

    allowed, remaining = check_and_increment(user_id)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Daily message limit reached. Come back tomorrow!",
        )

    # Last user message drives retrieval
    last_user_msg = next(
        (m.content for m in reversed(body.messages) if m.role == "user"),
        "",
    )

    # Retrieve context and build augmented prompt
    chunks = retrieve_context(last_user_msg)

    # Build messages for Claude — replace the last user message with RAG-augmented version
    claude_messages = []
    for i, msg in enumerate(body.messages):
        is_last_user = (
            msg.role == "user"
            and i == max(j for j, m in enumerate(body.messages) if m.role == "user")
        )
        if is_last_user:
            claude_messages.append({
                "role": "user",
                "content": build_rag_prompt(msg.content, chunks),
            })
        else:
            claude_messages.append({"role": msg.role, "content": msg.content})

    client = get_anthropic_client()

    async def stream_response() -> AsyncGenerator[str, None]:
        yield f"data: {remaining}\n\n"  # send remaining count as first SSE event

        async with client.messages.stream(
            model="claude-opus-4-8",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=claude_messages,
            thinking={"type": "adaptive"},
        ) as stream:
            async for text in stream.text_stream:
                if text:
                    # SSE format: data: <chunk>\n\n
                    escaped = text.replace("\n", "\\n")
                    yield f"data: {escaped}\n\n"

        yield "data: [DONE]\n\n"

    return StreamingResponse(
        stream_response(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Remaining-Messages": str(remaining),
        },
    )

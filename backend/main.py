"""
AI Aleks — FastAPI backend.

Endpoints:
  POST /auth/register   — Kit.com email gate, returns JWT
  GET  /auth/me         — validate token, return user info + remaining messages
  POST /chat            — streaming RAG chat (requires valid JWT)
  GET  /health          — liveness check

LLM: Groq (llama-3.3-70b-versatile) for local dev / free tier.
     Swap GROQ_API_KEY → ANTHROPIC_API_KEY and update get_llm_client() for production.
"""

import os
import uuid
from typing import AsyncGenerator, List, Optional

from groq import AsyncGroq
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

_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://ai.aleksgornik.com",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_groq_client: Optional[AsyncGroq] = None


def get_groq_client() -> AsyncGroq:
    global _groq_client
    if _groq_client is None:
        _groq_client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))
    return _groq_client


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

    # Build message list for Groq (same OpenAI-compatible format)
    groq_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for i, msg in enumerate(body.messages):
        is_last_user = (
            msg.role == "user"
            and i == max(j for j, m in enumerate(body.messages) if m.role == "user")
        )
        if is_last_user:
            groq_messages.append({"role": "user", "content": build_rag_prompt(msg.content, chunks)})
        else:
            groq_messages.append({"role": msg.role, "content": msg.content})

    client = get_groq_client()

    async def stream_response() -> AsyncGenerator[str, None]:
        yield f"data: {remaining}\n\n"

        try:
            stream = await client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=groq_messages,
                stream=True,
                max_tokens=1024,
                temperature=0.7,
            )
            async for chunk in stream:
                text = chunk.choices[0].delta.content or ""
                if text:
                    escaped = text.replace("\n", "\\n")
                    yield f"data: {escaped}\n\n"
        except Exception as e:
            import logging
            logging.error("Groq streaming error: %s", e)
            yield "data: Sorry, I ran into an error. Please try again.\\n\n\n"

        yield "data: [DONE]\n\n"

    return StreamingResponse(
        stream_response(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Remaining-Messages": str(remaining),
        },
    )

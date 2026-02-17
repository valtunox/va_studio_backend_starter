"""
Public Chat Routes

Public-first chat API for anonymous and authenticated users.
No authentication required - sessions are tracked via session IDs.
Rate-limited to prevent abuse.

This is the core interaction point where users:
1. Chat with the AI assistant about their project needs
2. Get template recommendations
3. Submit template customization requests
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Request, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import settings
from app.core.redis import redis_client
from app.core.logger import logger
from app.auth.dependencies import get_optional_user
from app.orm.user import User

from .schemas import (
    MessageRequest,
    MessageResponse,
    SessionCreateResponse,
    SessionInfo,
    ChatMessage,
    ChatRole,
    ConversationHistory,
    TemplateRequestCreate,
    TemplateRequestResponse,
    TemplateRequestStatus,
)


router = APIRouter(prefix="/chat", tags=["Chat (Public)"])

SESSION_TTL = 60 * 60 * 24  # 24 hours
MAX_MESSAGES_PER_SESSION = 100
MAX_SESSIONS_PER_IP = 20
RATE_LIMIT_MESSAGES = 30
RATE_LIMIT_WINDOW = 60


# ── Helpers ────────────────────────────────────────────────

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _session_key(session_id: str) -> str:
    return f"chat:session:{session_id}"


def _messages_key(session_id: str) -> str:
    return f"chat:messages:{session_id}"


def _request_key(request_id: str) -> str:
    return f"chat:request:{request_id}"


async def _rate_limit_check(identifier: str) -> bool:
    """Check if the identifier is within rate limits. Returns True if allowed."""
    try:
        allowed, remaining = await redis_client.rate_limit_check(
            f"chat:{identifier}",
            RATE_LIMIT_MESSAGES,
            RATE_LIMIT_WINDOW,
        )
        return allowed
    except Exception:
        return True  # Fail open if Redis is down


async def _get_or_create_session(
    session_id: Optional[str],
    client_ip: str,
    template_context: Optional[str] = None,
) -> tuple[str, bool]:
    """
    Get existing session or create a new one.
    Returns (session_id, is_new).
    """
    if session_id:
        session_data = await redis_client.get_json(_session_key(session_id))
        if session_data:
            session_data["last_activity"] = _now().isoformat()
            await redis_client.set_json(_session_key(session_id), session_data, SESSION_TTL)
            return session_id, False

    new_id = str(uuid.uuid4())
    session_data = {
        "session_id": new_id,
        "client_ip": client_ip,
        "template_context": template_context,
        "message_count": 0,
        "created_at": _now().isoformat(),
        "last_activity": _now().isoformat(),
    }
    await redis_client.set_json(_session_key(new_id), session_data, SESSION_TTL)
    return new_id, True


def _build_ai_response(message: str, template_context: Optional[str] = None) -> dict:
    """
    Build AI response. This is the integration point for LLM providers.

    In production, replace this with actual LLM calls:
    - OpenAI GPT-4
    - Anthropic Claude
    - Local models via Ollama
    - Or your Golang AI service
    """
    msg_lower = message.lower()

    # Template recommendation logic
    template_suggestion = None
    if any(kw in msg_lower for kw in ["shop", "store", "ecommerce", "product", "sell"]):
        template_suggestion = "ecommerce"
        response = (
            "Based on your needs, I'd recommend our **E-Commerce Store** template. "
            "It comes with a product catalog, shopping cart, flash deals, wishlist, "
            "and a full checkout flow. Would you like to customize it for your brand?"
        )
    elif any(kw in msg_lower for kw in ["saas", "startup", "pricing", "landing", "app"]):
        template_suggestion = "saas"
        response = (
            "Our **SaaS Landing Page** template would be perfect! It includes "
            "pricing tiers with annual toggle, feature grid, FAQ accordion, "
            "testimonials, and conversion-optimized CTAs. Want me to set it up?"
        )
    elif any(kw in msg_lower for kw in ["portfolio", "personal", "resume", "developer", "freelance"]):
        template_suggestion = "portfolio"
        response = (
            "I'd suggest our **Developer Portfolio** template. It features a "
            "project gallery, skill bars, experience timeline, testimonials, "
            "and a contact form — all with a stunning dark theme."
        )
    elif any(kw in msg_lower for kw in ["blog", "write", "article", "content", "post"]):
        template_suggestion = "blog"
        response = (
            "The **Developer Blog** template is ideal for content creators. "
            "It has a magazine-style layout with featured posts, category filters, "
            "trending sidebar, and a newsletter signup."
        )
    elif any(kw in msg_lower for kw in ["crm", "customer", "sales", "lead", "contact", "pipeline"]):
        template_suggestion = "crm"
        response = (
            "Our **CRM Dashboard** template is built for sales teams. It includes "
            "a sales pipeline, contacts table, activity feed, task manager, "
            "and deal tracking — everything you need to manage customers."
        )
    elif any(kw in msg_lower for kw in ["erp", "enterprise", "inventory", "warehouse", "manufacturing"]):
        template_suggestion = "erp"
        response = (
            "The **ERP Suite** template is designed for enterprise operations. "
            "It has KPI dashboards, order management, inventory alerts, "
            "warehouse monitoring, and financial reporting."
        )
    elif any(kw in msg_lower for kw in ["social", "feed", "post", "community", "network"]):
        template_suggestion = "social"
        response = (
            "Our **Social Platform** template is perfect for building communities. "
            "It includes stories, a post feed, trending topics, messaging, "
            "and user suggestions — like a modern social network."
        )
    elif any(kw in msg_lower for kw in ["dashboard", "analytics", "chart", "report", "metric"]):
        template_suggestion = "dashboard"
        response = (
            "The **Analytics Dashboard** template is great for data visualization. "
            "It features sparkline charts, revenue breakdowns, device stats, "
            "top pages, and transaction tables."
        )
    elif any(kw in msg_lower for kw in ["hello", "hi", "hey", "start", "help"]):
        response = (
            "Welcome to VA Studio! I'm here to help you find the perfect template "
            "for your project. Tell me what you're building — an online store, "
            "a SaaS product, a portfolio, a blog, or something else?"
        )
    else:
        response = (
            f"Thanks for your message! I can help you choose from our 8 templates: "
            "E-Commerce, SaaS, Portfolio, Blog, CRM, ERP, Social, and Analytics Dashboard. "
            "What kind of project are you working on?"
        )

    return {
        "response": response,
        "template_suggestion": template_suggestion or template_context,
    }


# ── Routes ─────────────────────────────────────────────────

@router.post("/session", response_model=SessionCreateResponse)
async def create_session(request: Request) -> SessionCreateResponse:
    """
    Create a new anonymous chat session.

    Public endpoint - no authentication required.
    Sessions expire after 24 hours of inactivity.
    """
    client_ip = request.client.host if request.client else "unknown"
    session_id, _ = await _get_or_create_session(None, client_ip)
    now = _now()

    return SessionCreateResponse(
        session_id=session_id,
        created_at=now,
        expires_at=now + timedelta(seconds=SESSION_TTL),
    )


@router.post("/message", response_model=MessageResponse)
async def send_message(
    body: MessageRequest,
    request: Request,
    current_user: Optional[User] = Depends(get_optional_user),
) -> MessageResponse:
    """
    Send a message to the AI assistant.

    Public endpoint - works for both anonymous and authenticated users.
    Rate-limited to prevent abuse.
    """
    client_ip = request.client.host if request.client else "unknown"
    identifier = str(current_user.id) if current_user else client_ip

    # Rate limit check
    if not await _rate_limit_check(identifier):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many messages. Please wait a moment before trying again.",
        )

    # Get or create session
    session_id, is_new = await _get_or_create_session(
        body.session_id, client_ip, body.template_context
    )

    # Get session data
    session_data = await redis_client.get_json(_session_key(session_id))
    if not session_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found or expired",
        )

    # Check message limit
    if session_data.get("message_count", 0) >= MAX_MESSAGES_PER_SESSION:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Session message limit reached. Please start a new session.",
        )

    # Build AI response
    ai_result = _build_ai_response(body.message, body.template_context)
    now = _now()
    message_id = str(uuid.uuid4())

    # Store messages in session history
    messages = await redis_client.get_json(_messages_key(session_id)) or []
    messages.append({
        "id": str(uuid.uuid4()),
        "role": "user",
        "content": body.message,
        "created_at": now.isoformat(),
    })
    messages.append({
        "id": message_id,
        "role": "assistant",
        "content": ai_result["response"],
        "template_suggestion": ai_result.get("template_suggestion"),
        "created_at": now.isoformat(),
    })
    await redis_client.set_json(_messages_key(session_id), messages, SESSION_TTL)

    # Update session
    session_data["message_count"] = len(messages)
    session_data["last_activity"] = now.isoformat()
    if ai_result.get("template_suggestion"):
        session_data["template_context"] = ai_result["template_suggestion"]
    await redis_client.set_json(_session_key(session_id), session_data, SESSION_TTL)

    return MessageResponse(
        session_id=session_id,
        message_id=message_id,
        response=ai_result["response"],
        template_suggestion=ai_result.get("template_suggestion"),
        actions=None,
        created_at=now,
    )


@router.get("/session/{session_id}", response_model=SessionInfo)
async def get_session(session_id: str) -> SessionInfo:
    """
    Get information about a chat session.

    Public endpoint - session ID acts as the access token.
    """
    session_data = await redis_client.get_json(_session_key(session_id))
    if not session_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found or expired",
        )

    return SessionInfo(
        session_id=session_data["session_id"],
        message_count=session_data.get("message_count", 0),
        template_context=session_data.get("template_context"),
        created_at=datetime.fromisoformat(session_data["created_at"]),
        last_activity=datetime.fromisoformat(session_data["last_activity"]),
    )


@router.get("/session/{session_id}/history", response_model=ConversationHistory)
async def get_history(session_id: str) -> ConversationHistory:
    """
    Get full conversation history for a session.

    Public endpoint - session ID acts as the access token.
    """
    session_data = await redis_client.get_json(_session_key(session_id))
    if not session_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found or expired",
        )

    raw_messages = await redis_client.get_json(_messages_key(session_id)) or []
    messages = [
        ChatMessage(
            id=m["id"],
            role=ChatRole(m["role"]),
            content=m["content"],
            template_suggestion=m.get("template_suggestion"),
            created_at=datetime.fromisoformat(m["created_at"]),
        )
        for m in raw_messages
    ]

    return ConversationHistory(
        session_id=session_id,
        messages=messages,
        template_context=session_data.get("template_context"),
        message_count=len(messages),
    )


@router.post("/template-request", response_model=TemplateRequestResponse)
async def submit_template_request(
    body: TemplateRequestCreate,
    request: Request,
    current_user: Optional[User] = Depends(get_optional_user),
) -> TemplateRequestResponse:
    """
    Submit a template customization/generation request.

    Public endpoint - works for both anonymous and authenticated users.
    Authenticated users get priority processing.
    """
    request_id = str(uuid.uuid4())
    now = _now()

    request_data = {
        "request_id": request_id,
        "template_id": body.template_id,
        "session_id": body.session_id,
        "requirements": body.requirements,
        "brand_name": body.brand_name,
        "color_preference": body.color_preference,
        "additional_notes": body.additional_notes,
        "user_id": str(current_user.id) if current_user else None,
        "status": "queued",
        "progress": 0,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
    }

    await redis_client.set_json(_request_key(request_id), request_data, SESSION_TTL * 7)

    logger.info(f"Template request submitted: {request_id} for template {body.template_id}")

    return TemplateRequestResponse(
        request_id=request_id,
        template_id=body.template_id,
        status="queued",
        estimated_time="2-5 minutes",
        message=(
            f"Your {body.template_id} template request has been submitted! "
            "We'll process your customization and notify you when it's ready."
        ),
        created_at=now,
    )


@router.get("/template-request/{request_id}", response_model=TemplateRequestStatus)
async def get_template_request_status(request_id: str) -> TemplateRequestStatus:
    """
    Check the status of a template generation request.

    Public endpoint - request ID acts as the access token.
    """
    request_data = await redis_client.get_json(_request_key(request_id))
    if not request_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Request not found or expired",
        )

    return TemplateRequestStatus(
        request_id=request_data["request_id"],
        template_id=request_data["template_id"],
        status=request_data["status"],
        progress=request_data.get("progress", 0),
        result_url=request_data.get("result_url"),
        message=f"Request is {request_data['status']}",
        created_at=datetime.fromisoformat(request_data["created_at"]),
        updated_at=datetime.fromisoformat(request_data["updated_at"]),
    )

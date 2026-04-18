"""
Chat Schemas

Pydantic models for the public chat API.
Supports both anonymous and authenticated sessions.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum

from pydantic import BaseModel, Field


class ChatRole(str, Enum):
    """Message role in a conversation."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class MessageRequest(BaseModel):
    """Incoming chat message from the user."""
    message: str = Field(..., min_length=1, max_length=4000)
    session_id: Optional[str] = Field(None, description="Existing session ID to continue a conversation")
    template_context: Optional[str] = Field(None, description="Template ID the user is currently viewing")
    metadata: Optional[Dict[str, Any]] = None


class MessageResponse(BaseModel):
    """Chat response from the AI assistant."""
    session_id: str
    message_id: str
    response: str
    template_suggestion: Optional[str] = None
    actions: Optional[List[Dict[str, Any]]] = None
    created_at: datetime


class SessionCreateResponse(BaseModel):
    """Response when a new anonymous session is created."""
    session_id: str
    created_at: datetime
    expires_at: datetime


class SessionInfo(BaseModel):
    """Information about an existing chat session."""
    session_id: str
    message_count: int
    template_context: Optional[str] = None
    created_at: datetime
    last_activity: datetime


class ChatMessage(BaseModel):
    """A single message in conversation history."""
    id: str
    role: ChatRole
    content: str
    template_suggestion: Optional[str] = None
    created_at: datetime


class ConversationHistory(BaseModel):
    """Full conversation history for a session."""
    session_id: str
    messages: List[ChatMessage]
    template_context: Optional[str] = None
    message_count: int


class TemplateRequestCreate(BaseModel):
    """Request to generate/customize a template."""
    session_id: Optional[str] = None
    template_id: str
    requirements: str = Field(..., min_length=10, max_length=5000)
    brand_name: Optional[str] = None
    color_preference: Optional[str] = None
    additional_notes: Optional[str] = None


class TemplateRequestResponse(BaseModel):
    """Response after submitting a template request."""
    request_id: str
    template_id: str
    status: str
    estimated_time: Optional[str] = None
    message: str
    created_at: datetime


class TemplateRequestStatus(BaseModel):
    """Status of a template generation request."""
    request_id: str
    template_id: str
    status: str
    progress: int = 0
    result_url: Optional[str] = None
    message: str
    created_at: datetime
    updated_at: datetime

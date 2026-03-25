"""
OAuth Social Login Module - All-in-One
======================================

Complete OAuth2 social login system for InfinityAI FastAPI Platform.
Supports Google, GitHub, and Microsoft authentication.
Uses existing Django PostgreSQL tables (users, organizations, oauth_accounts).

Features:
- Backend-owned OAuth2 Authorization Code flow
- Google OAuth2 login
- GitHub OAuth login
- Microsoft OAuth login
- Account linking (existing users)
- Auto user creation with organization/workspace
- JWT token generation after OAuth success

Uses: app.core.db for PostgreSQL connection to Django tables.

Routes (prefix: /api/v1/auth/oauth):
    GET    /login/{provider}           - Initiate OAuth flow
    GET    /callback/{provider}        - Handle OAuth callback
    POST   /google                     - Google ID token login (legacy/mobile)
    GET    /github/repos               - List GitHub repositories
    GET    /github/repos/{owner}/{repo}/branches - List repo branches
"""

import os
import re
import uuid
import json
import secrets
import hashlib
import urllib.parse
from datetime import datetime, timedelta
from typing import Optional, List, Any, Dict, Tuple

import requests
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from fastapi.responses import RedirectResponse, JSONResponse
from pydantic import BaseModel, Field, EmailStr

# Database connection from core.db
from app.core.db import basic_postgres_connection

# Import auth utilities
from .auth import (
    create_tokens, hash_password, TokenResponse,
    auth_db, get_current_active_user
)
from app.core.logger import (
    get_logger,
    log_api_request,
    log_api_response,
    set_correlation_id,
    RequestTimer,
)

# ============================================================================
# CONFIGURATION
# ============================================================================

logger = get_logger(__name__)

# Environment URLs
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8741")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

GOOGLE_OAUTH_SECRET_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "data", "auth", "client_secret_google.json")
)


def _load_google_oauth_secrets(secret_path: str) -> Dict[str, Any]:
    try:
        with open(secret_path, "r", encoding="utf-8") as secret_file:
            raw = json.load(secret_file)
        return raw.get("web") or raw.get("installed") or raw
    except FileNotFoundError:
        logger.warning("Google OAuth secret file not found at %s", secret_path)
    except json.JSONDecodeError as exc:
        logger.warning("Google OAuth secret file invalid JSON: %s", exc)
    except Exception as exc:
        logger.warning("Google OAuth secret file load failed: %s", exc)
    return {}


google_oauth_secrets = _load_google_oauth_secrets(GOOGLE_OAUTH_SECRET_PATH)

# OAuth Provider Configuration
OAUTH_PROVIDERS = {
    "google": {
        "client_id": google_oauth_secrets.get("client_id") or os.getenv("GOOGLE_OAUTH2_CLIENT_ID", ""),
        "client_secret": google_oauth_secrets.get("client_secret") or os.getenv("GOOGLE_OAUTH2_CLIENT_SECRET", ""),
        "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "userinfo_url": "https://www.googleapis.com/oauth2/v3/userinfo",
        "scopes": ["openid", "email", "profile"],
        "callback_path": "/api/v1/auth/oauth/callback/google"
    },
    "github": {
        "client_id": os.getenv("GITHUB_CLIENT_ID", ""),
        "client_secret": os.getenv("GITHUB_CLIENT_SECRET", ""),
        "auth_url": "https://github.com/login/oauth/authorize",
        "token_url": "https://github.com/login/oauth/access_token",
        "userinfo_url": "https://api.github.com/user",
        "scopes": ["user:email", "read:user", "repo"],
        "callback_path": "/api/v1/auth/oauth/callback/github"
    },
    "microsoft": {
        "client_id": os.getenv("MICROSOFT_CLIENT_ID", ""),
        "client_secret": os.getenv("MICROSOFT_CLIENT_SECRET", ""),
        "auth_url": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        "token_url": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
        "userinfo_url": "https://graph.microsoft.com/v1.0/me",
        "scopes": ["openid", "email", "profile", "User.Read"],
        "callback_path": "/api/v1/auth/oauth/callback/microsoft"
    }
}

# Allowed redirect URLs after OAuth
OAUTH_ALLOWED_REDIRECTS = [
    "/dashboard",
    "/dashboard/",
    "/",
    "/settings",
    "/settings/",
    "/profile",
    "/profile/",
    "/workspace",
    "/workspace/"
]

# In-memory state store (use Redis in production)
_oauth_state_store: Dict[str, Dict[str, Any]] = {}


# ============================================================================
# PYDANTIC SCHEMAS
# ============================================================================

class GoogleTokenRequest(BaseModel):
    """Google ID token request (legacy/mobile flow)."""
    credential: str = Field(..., description="Google ID token")


class OAuthUserInfo(BaseModel):
    """Normalized OAuth user info."""
    provider: str
    provider_user_id: str
    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    username: Optional[str] = None
    avatar_url: Optional[str] = None
    raw_data: Dict[str, Any] = {}


class GitHubRepository(BaseModel):
    """GitHub repository info."""
    id: int
    name: str
    full_name: str
    description: Optional[str] = None
    html_url: str
    clone_url: str
    ssh_url: str
    private: bool
    language: Optional[str] = None
    default_branch: str = "main"
    updated_at: Optional[datetime] = None


class GitHubBranch(BaseModel):
    """GitHub branch info."""
    name: str
    protected: bool = False
    commit_sha: str


# ============================================================================
# OAUTH UTILITIES
# ============================================================================

def generate_oauth_state(next_url: str) -> str:
    """Generate a secure state parameter for CSRF protection."""
    state = secrets.token_urlsafe(32)
    _oauth_state_store[state] = {
        "next": next_url,
        "created_at": datetime.utcnow()
    }
    
    # Cleanup old states (older than 10 minutes)
    threshold = datetime.utcnow() - timedelta(minutes=10)
    expired = [s for s, d in _oauth_state_store.items() if d["created_at"] < threshold]
    for s in expired:
        _oauth_state_store.pop(s, None)
    
    return state


def validate_oauth_state(state: str) -> Optional[Dict[str, Any]]:
    """Validate and consume OAuth state parameter."""
    if not state or state not in _oauth_state_store:
        return None
    
    state_data = _oauth_state_store.pop(state)
    
    # Check expiry (10 minute window)
    if state_data["created_at"] < datetime.utcnow() - timedelta(minutes=10):
        return None
    
    return state_data


def validate_redirect_url(next_url: str) -> str:
    """Validate and sanitize redirect URL."""
    if not next_url:
        return "/dashboard"
    
    parsed = urllib.parse.urlparse(next_url)
    path = parsed.path
    
    if path in OAUTH_ALLOWED_REDIRECTS or path.rstrip("/") in [r.rstrip("/") for r in OAUTH_ALLOWED_REDIRECTS]:
        return next_url
    
    logger.warning(f"Invalid redirect URL rejected: {next_url}")
    return "/dashboard"


# ============================================================================
# OAUTH DATABASE MANAGER
# ============================================================================

class OAuthDatabaseManager:
    """Database manager for OAuth accounts."""
    
    def get_oauth_account(self, provider: str, provider_user_id: str) -> Optional[Dict[str, Any]]:
        """Get OAuth account by provider and provider_user_id."""
        try:
            conn = basic_postgres_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT oa.id, oa.user_id, oa.provider, oa.provider_user_id, 
                       oa.email, oa.access_token, oa.refresh_token, oa.raw_data,
                       u.email as user_email, u.username, u.is_active
                FROM oauth_accounts oa
                JOIN users_user u ON oa.user_id = u.id
                WHERE oa.provider = %s AND oa.provider_user_id = %s
            """, (provider, provider_user_id))
            row = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if row:
                return {
                    "id": str(row[0]), "user_id": row[1], "provider": row[2],
                    "provider_user_id": row[3], "email": row[4],
                    "access_token": row[5], "refresh_token": row[6],
                    "raw_data": row[7], "user_email": row[8],
                    "username": row[9], "is_active": row[10]
                }
            return None
        except Exception as e:
            logger.error(f"Error getting OAuth account: {e}")
            return None
    
    def create_oauth_account(
        self, 
        user_id: int, 
        provider: str, 
        provider_user_id: str,
        email: Optional[str] = None,
        access_token: Optional[str] = None,
        refresh_token: Optional[str] = None,
        raw_data: Optional[Dict] = None
    ) -> Optional[Dict[str, Any]]:
        """Create a new OAuth account linked to a user."""
        try:
            conn = basic_postgres_connection()
            cursor = conn.cursor()
            
            account_id = str(uuid.uuid4())
            cursor.execute("""
                INSERT INTO oauth_accounts (
                    id, user_id, provider, provider_user_id, email,
                    access_token, refresh_token, raw_data, created_at, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                RETURNING id, created_at
            """, (
                account_id, user_id, provider, provider_user_id, email,
                access_token, refresh_token, json.dumps(raw_data or {})
            ))
            row = cursor.fetchone()
            conn.commit()
            cursor.close()
            conn.close()
            
            return {"id": str(row[0]), "created_at": row[1]}
        except Exception as e:
            logger.error(f"Error creating OAuth account: {e}")
            return None
    
    def update_oauth_tokens(
        self, 
        provider: str, 
        provider_user_id: str,
        access_token: str,
        refresh_token: Optional[str] = None,
        raw_data: Optional[Dict] = None
    ) -> bool:
        """Update OAuth tokens for an existing account."""
        try:
            conn = basic_postgres_connection()
            cursor = conn.cursor()
            
            updates = ["access_token = %s", "updated_at = NOW()"]
            values = [access_token]
            
            if refresh_token:
                updates.append("refresh_token = %s")
                values.append(refresh_token)
            if raw_data:
                updates.append("raw_data = %s")
                values.append(json.dumps(raw_data))
            
            values.extend([provider, provider_user_id])
            
            cursor.execute(f"""
                UPDATE oauth_accounts
                SET {', '.join(updates)}
                WHERE provider = %s AND provider_user_id = %s
            """, tuple(values))
            
            affected = cursor.rowcount
            conn.commit()
            cursor.close()
            conn.close()
            return affected > 0
        except Exception as e:
            logger.error(f"Error updating OAuth tokens: {e}")
            return False
    
    def create_user_from_oauth(self, user_info: OAuthUserInfo) -> Optional[Dict[str, Any]]:
        """Create a new user from OAuth info."""
        try:
            conn = basic_postgres_connection()
            cursor = conn.cursor()
            
            # Generate unique username
            base_username = user_info.username or user_info.email.split("@")[0] if user_info.email else "user"
            username = self._ensure_unique_username(cursor, base_username)
            
            # Create organization
            org_id = str(uuid.uuid4())
            tenant_sub_id = f"tenant_subscription_{str(uuid.uuid4())[:12]}"
            cursor.execute("""
                INSERT INTO users_organization (id, name, tenant_subscription_id, created_at, updated_at)
                VALUES (%s, %s, %s, NOW(), NOW())
                RETURNING id
            """, (org_id, username, tenant_sub_id))
            org_result = cursor.fetchone()
            organization_id = org_result[0]
            
            # Create user (no password for OAuth users)
            cursor.execute("""
                INSERT INTO users_user (
                    email, username, password, first_name, last_name,
                    is_verified, is_active, is_staff, is_superuser,
                    date_joined, organization_id, kyc_completed, deployed_where
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), %s, %s, %s)
                RETURNING id, email, username, date_joined
            """, (
                user_info.email, username, "",  # Empty password for OAuth
                user_info.first_name or "", user_info.last_name or "",
                True,  # OAuth users are verified
                True, False, False, organization_id, True, "AMERICA-1"
            ))
            user_row = cursor.fetchone()
            user_id = user_row[0]
            
            # Update social field based on provider
            social_field = f"social_{user_info.provider}"
            if social_field in ["social_google", "social_github", "social_microsoft"]:
                cursor.execute(f"""
                    UPDATE users_user SET {social_field} = %s WHERE id = %s
                """, (user_info.provider_user_id, user_id))
            
            # Create workspace
            workspace_id = str(uuid.uuid4())
            session_id = str(uuid.uuid4())
            workspace_config = {
                "environment": "development",
                "region": "us-east-1",
                "created_by": user_info.email,
                "workspace_type": "standard",
                "oauth_provider": user_info.provider
            }
            cursor.execute("""
                INSERT INTO infrastructure_workspace (
                    id, name, user_id, organization_id, is_active, is_default_workspace,
                    session_id, configuration, created_at, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
            """, (
                workspace_id, username, user_id, organization_id,
                True, True, session_id, str(workspace_config).replace("'", '"')
            ))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            return {
                "id": user_id,
                "email": user_row[1],
                "username": user_row[2],
                "date_joined": user_row[3],
                "organization_id": organization_id
            }
        except Exception as e:
            logger.error(f"Error creating user from OAuth: {e}")
            return None
    
    def _ensure_unique_username(self, cursor, base: str) -> str:
        """Ensure username is unique."""
        # Clean username
        clean = re.sub(r'[^a-zA-Z0-9_]', '', base)[:20]
        if len(clean) < 4:
            clean = f"user_{secrets.token_hex(4)}"
        
        username = clean
        counter = 0
        
        while True:
            cursor.execute("SELECT id FROM users_user WHERE username = %s", (username,))
            if not cursor.fetchone():
                return username
            counter += 1
            username = f"{clean}_{counter}"
            if counter > 100:
                return f"user_{secrets.token_hex(8)}"
    
    def link_oauth_to_existing_user(
        self,
        user_id: int,
        provider: str,
        provider_user_id: str,
        email: Optional[str] = None,
        access_token: Optional[str] = None,
        refresh_token: Optional[str] = None,
        raw_data: Optional[Dict] = None
    ) -> bool:
        """Link OAuth account to existing user."""
        try:
            # Create OAuth account
            result = self.create_oauth_account(
                user_id, provider, provider_user_id,
                email, access_token, refresh_token, raw_data
            )
            if not result:
                return False
            
            # Update user's social field
            conn = basic_postgres_connection()
            cursor = conn.cursor()
            social_field = f"social_{provider}"
            if social_field in ["social_google", "social_github", "social_microsoft"]:
                cursor.execute(f"""
                    UPDATE users_user SET {social_field} = %s WHERE id = %s
                """, (provider_user_id, user_id))
            conn.commit()
            cursor.close()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Error linking OAuth: {e}")
            return False
    
    def get_user_github_token(self, user_id: int) -> Optional[str]:
        """Get user's GitHub access token."""
        try:
            conn = basic_postgres_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT access_token FROM oauth_accounts
                WHERE user_id = %s AND provider = 'github'
            """, (user_id,))
            row = cursor.fetchone()
            cursor.close()
            conn.close()
            return row[0] if row else None
        except Exception as e:
            logger.error(f"Error getting GitHub token: {e}")
            return None


# Global OAuth database manager
oauth_db = OAuthDatabaseManager()


# ============================================================================
# OAUTH SERVICE
# ============================================================================

class OAuthService:
    """OAuth service for handling social login flows."""
    
    def exchange_code_for_tokens(
        self, 
        provider: str, 
        code: str
    ) -> Optional[Dict[str, Any]]:
        """Exchange authorization code for tokens."""
        config = OAUTH_PROVIDERS.get(provider)
        if not config:
            return None
        
        callback_url = f"{BACKEND_URL}{config['callback_path']}"
        
        data = {
            "client_id": config["client_id"],
            "client_secret": config["client_secret"],
            "code": code,
            "redirect_uri": callback_url,
        }
        
        headers = {}
        if provider == "google":
            data["grant_type"] = "authorization_code"
        elif provider == "github":
            headers["Accept"] = "application/json"
        elif provider == "microsoft":
            data["grant_type"] = "authorization_code"
        
        try:
            response = requests.post(
                config["token_url"],
                data=data,
                headers=headers,
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Token exchange failed for {provider}: {e}")
            return None
    
    def fetch_user_info(
        self, 
        provider: str, 
        tokens: Dict[str, Any]
    ) -> Optional[OAuthUserInfo]:
        """Fetch user info from OAuth provider."""
        config = OAUTH_PROVIDERS.get(provider)
        if not config:
            return None
        
        access_token = tokens.get("access_token")
        if not access_token:
            return None
        
        headers = {"Authorization": f"Bearer {access_token}"}
        if provider == "github":
            headers = {"Authorization": f"token {access_token}"}
        
        try:
            response = requests.get(
                config["userinfo_url"],
                headers=headers,
                timeout=30
            )
            response.raise_for_status()
            user_data = response.json()
            
            # For GitHub, fetch email separately if needed
            email = None
            if provider == "github" and not user_data.get("email"):
                email = self._fetch_github_email(access_token)
            
            return self._normalize_user_info(provider, user_data, email)
        except Exception as e:
            logger.error(f"Failed to fetch user info from {provider}: {e}")
            return None
    
    def _fetch_github_email(self, access_token: str) -> Optional[str]:
        """Fetch primary email from GitHub."""
        try:
            response = requests.get(
                "https://api.github.com/user/emails",
                headers={"Authorization": f"token {access_token}"},
                timeout=30
            )
            response.raise_for_status()
            emails = response.json()
            
            # Primary verified email
            for e in emails:
                if e.get("primary") and e.get("verified"):
                    return e.get("email")
            # Any verified email
            for e in emails:
                if e.get("verified"):
                    return e.get("email")
            return None
        except Exception as e:
            logger.error(f"Failed to fetch GitHub email: {e}")
            return None
    
    def _normalize_user_info(
        self, 
        provider: str, 
        data: Dict, 
        email_override: Optional[str] = None
    ) -> OAuthUserInfo:
        """Normalize user info from different providers."""
        if provider == "google":
            return OAuthUserInfo(
                provider=provider,
                provider_user_id=data.get("sub", ""),
                email=data.get("email"),
                first_name=data.get("given_name"),
                last_name=data.get("family_name"),
                avatar_url=data.get("picture"),
                raw_data=data
            )
        elif provider == "github":
            name_parts = (data.get("name") or "").split(" ", 1)
            return OAuthUserInfo(
                provider=provider,
                provider_user_id=str(data.get("id", "")),
                email=email_override or data.get("email"),
                first_name=name_parts[0] if name_parts else None,
                last_name=name_parts[1] if len(name_parts) > 1 else None,
                username=data.get("login"),
                avatar_url=data.get("avatar_url"),
                raw_data=data
            )
        elif provider == "microsoft":
            return OAuthUserInfo(
                provider=provider,
                provider_user_id=data.get("id", ""),
                email=data.get("mail") or data.get("userPrincipalName"),
                first_name=data.get("givenName"),
                last_name=data.get("surname"),
                raw_data=data
            )
        return OAuthUserInfo(provider=provider, provider_user_id="", raw_data=data)
    
    def get_or_create_user(
        self, 
        user_info: OAuthUserInfo, 
        tokens: Dict[str, Any]
    ) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """Find existing user or create new one from OAuth info."""
        # Check if OAuth account exists
        oauth_account = oauth_db.get_oauth_account(
            user_info.provider, 
            user_info.provider_user_id
        )
        
        if oauth_account:
            # Update tokens
            oauth_db.update_oauth_tokens(
                user_info.provider,
                user_info.provider_user_id,
                tokens.get("access_token", ""),
                tokens.get("refresh_token"),
                user_info.raw_data
            )
            # Get user
            user = auth_db.get_user_by_id(oauth_account["user_id"])
            return user, oauth_account
        
        # Check if user with this email exists
        if user_info.email:
            existing_user = auth_db.get_user_by_email(user_info.email)
            if existing_user:
                # Link OAuth to existing user
                oauth_db.link_oauth_to_existing_user(
                    existing_user["id"],
                    user_info.provider,
                    user_info.provider_user_id,
                    user_info.email,
                    tokens.get("access_token"),
                    tokens.get("refresh_token"),
                    user_info.raw_data
                )
                return existing_user, None
        
        # Create new user
        if not user_info.email:
            logger.error(f"Cannot create user without email from {user_info.provider}")
            return None, None
        
        new_user = oauth_db.create_user_from_oauth(user_info)
        if new_user:
            # Create OAuth account link
            oauth_db.create_oauth_account(
                new_user["id"],
                user_info.provider,
                user_info.provider_user_id,
                user_info.email,
                tokens.get("access_token"),
                tokens.get("refresh_token"),
                user_info.raw_data
            )
            return new_user, None
        
        return None, None


# Global OAuth service
oauth_service = OAuthService()


# ============================================================================
# FASTAPI ROUTER & ROUTES
# ============================================================================

router = APIRouter(prefix="/api/v1/auth/oauth", tags=["OAuth"])


@router.get("/login/{provider}")
async def oauth_login(provider: str, request: Request, next: str = Query("/dashboard")):
    """
    Initiate OAuth login flow.
    
    Redirects to provider's authorization page.
    
    Providers: google, github, microsoft
    """
    path = f"/api/v1/auth/oauth/login/{provider}"
    cid = set_correlation_id(request.headers.get("X-Correlation-ID") if request else None)
    log_api_request(
        logger, "GET", path,
        query_params={"next": next},
        headers=dict(request.headers) if request else None,
        correlation_id=cid,
    )
    with RequestTimer() as timer:
        if provider not in OAUTH_PROVIDERS:
            log_api_response(logger, "GET", path, 400, duration_ms=timer.duration_ms)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid provider: {provider}. Supported: google, github, microsoft"
            )

        config = OAUTH_PROVIDERS[provider]

        if not config["client_id"]:
            log_api_response(logger, "GET", path, 503, duration_ms=timer.duration_ms)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"{provider.capitalize()} OAuth is not configured"
            )

        next_url = validate_redirect_url(next)
        state = generate_oauth_state(next_url)
        callback_url = f"{BACKEND_URL}{config['callback_path']}"

        if provider == "google":
            params = {
                "client_id": config["client_id"],
                "redirect_uri": callback_url,
                "response_type": "code",
                "scope": " ".join(config["scopes"]),
                "state": state,
                "access_type": "offline",
                "prompt": "select_account"
            }
        elif provider == "github":
            params = {
                "client_id": config["client_id"],
                "redirect_uri": callback_url,
                "scope": " ".join(config["scopes"]),
                "state": state,
                "allow_signup": "true"
            }
        elif provider == "microsoft":
            params = {
                "client_id": config["client_id"],
                "redirect_uri": callback_url,
                "response_type": "code",
                "scope": " ".join(config["scopes"]),
                "state": state,
                "response_mode": "query"
            }
        else:
            log_api_response(logger, "GET", path, 400, duration_ms=timer.duration_ms)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Provider {provider} not configured"
            )

        auth_url = f"{config['auth_url']}?{urllib.parse.urlencode(params)}"
        logger.info(f"Redirecting to {provider} OAuth")
        log_api_response(logger, "GET", path, 200, duration_ms=timer.duration_ms)
        return RedirectResponse(auth_url)


@router.get("/callback/{provider}")
async def oauth_callback(
    provider: str,
    request: Request,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    error_description: Optional[str] = None
):
    """
    Handle OAuth callback from provider.
    
    Exchanges code for tokens, creates/finds user, issues JWT tokens.
    Redirects to frontend with tokens.
    """
    path = f"/api/v1/auth/oauth/callback/{provider}"
    cid = set_correlation_id(request.headers.get("X-Correlation-ID") if request else None)
    log_api_request(
        logger, "GET", path,
        query_params={"code": "***" if code else None, "state": state or None, "error": error or None},
        headers=dict(request.headers) if request else None,
        correlation_id=cid,
    )
    with RequestTimer() as timer:
        if provider not in OAUTH_PROVIDERS:
            log_api_response(logger, "GET", path, 400, duration_ms=timer.duration_ms)
            return _redirect_with_error("Invalid provider")

        if error:
            logger.warning(f"OAuth error from {provider}: {error_description or error}")
            log_api_response(logger, "GET", path, 400, duration_ms=timer.duration_ms)
            return _redirect_with_error(error_description or error)

        if not code:
            log_api_response(logger, "GET", path, 400, duration_ms=timer.duration_ms)
            return _redirect_with_error("No authorization code received")

        state_data = validate_oauth_state(state)
        if not state_data:
            log_api_response(logger, "GET", path, 400, duration_ms=timer.duration_ms)
            return _redirect_with_error("Invalid or expired state. Please try again.")

        next_url = state_data.get("next", "/dashboard")

        try:
            tokens = oauth_service.exchange_code_for_tokens(provider, code)
            if not tokens:
                log_api_response(logger, "GET", path, 502, duration_ms=timer.duration_ms)
                return _redirect_with_error("Failed to exchange authorization code")

            user_info = oauth_service.fetch_user_info(provider, tokens)
            if not user_info:
                log_api_response(logger, "GET", path, 502, duration_ms=timer.duration_ms)
                return _redirect_with_error("Failed to fetch user information")

            user, oauth_account = oauth_service.get_or_create_user(user_info, tokens)
            if not user:
                log_api_response(logger, "GET", path, 502, duration_ms=timer.duration_ms)
                return _redirect_with_error("Failed to create or find user account")

            token_resp = create_tokens(user["id"], user["email"])
            logger.info(f"OAuth login successful for {user['email']} via {provider}")

            params = urllib.parse.urlencode({
                "access": token_resp.access,
                "refresh": token_resp.refresh,
                "next": next_url
            })
            redirect_url = f"{FRONTEND_URL}/auth/oauth/callback/?{params}"
            log_api_response(logger, "GET", path, 200, duration_ms=timer.duration_ms)
            response = RedirectResponse(redirect_url, status_code=302)
            response.set_cookie("oauth_access", token_resp.access, max_age=120, httponly=False, samesite="lax", path="/")
            response.set_cookie("oauth_refresh", token_resp.refresh, max_age=120, httponly=False, samesite="lax", path="/")
            return response

        except Exception as e:
            logger.error(f"OAuth callback error: {e}", exc_info=True)
            log_api_response(logger, "GET", path, 500, body={"error": str(e)}, duration_ms=timer.duration_ms)
            return _redirect_with_error("An error occurred during authentication")


@router.get("/google", response_model=TokenResponse)
async def google_auth(
    token_request: GoogleTokenRequest,
    request: Request
):
    """
    Google ID Token authentication (mobile/legacy).
    
    Verifies ID token and logs in user; creates account if needed.
    """
    try:
        # Validate Google ID Token
        id_token = token_request.credential
        verify_url = f"https://oauth2.googleapis.com/tokeninfo?id_token={id_token}"
        
        response = requests.get(verify_url, timeout=10)
        if response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Google ID token"
            )
        
        data = response.json()
        
        # Check audience
        google_client_id = OAUTH_PROVIDERS["google"]["client_id"]
        if data.get("aud") != google_client_id:
             # Also allow if it matches one of our client IDs (e.g. mobile vs web)
            if data.get("aud") not in [google_client_id]:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token audience mismatch"
                )
        
        # Extract user info
        email = data.get("email")
        if not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Token missing email"
            )
            
        user_info = OAuthUserInfo(
            provider="google",
            provider_user_id=data.get("sub"),
            email=email,
            first_name=data.get("given_name"),
            last_name=data.get("family_name"),
            avatar_url=data.get("picture"),
            raw_data=data
        )
        
        # Mock tokens wrapper since we don't have access/refresh from ID token flow
        # But we need them for get_or_create_user structure.
        # We can store the ID token as access_token for reference, or empty.
        tokens = {
            "access_token": "google_id_token_login",
            "refresh_token": None
        }
        
        user, _ = oauth_service.get_or_create_user(user_info, tokens)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to create/login user"
            )
            
        return create_tokens(user["id"], user["email"])
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Google auth error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication failed"
        )


@router.get("/github/repos/", response_model=Dict[str, Any])
async def get_github_repos(
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """
    List GitHub repositories for the current user.
    """
    try:
        # Get user's GitHub account
        github_account = oauth_db.get_oauth_account(
            "github", 
            current_user.get("social_github", "")
        )
        
        if not github_account:
            # Fallback: try to find by user_id if social_github is not set in user dict (legacy)
            # But oauth_db.get_oauth_account needs provider_user_id.
            # We need a way to find oauth account by user_id and provider.
            # Let's add that lookup or brute force it via SQL query here for now.
            # Using basic connection to find account by user_id
            conn = basic_postgres_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT provider_user_id FROM oauth_accounts 
                WHERE user_id = %s AND provider = 'github'
            """, (current_user["id"],))
            row = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if row:
                github_account = oauth_db.get_oauth_account("github", row[0])
            
        if not github_account:
             raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="GitHub account not connected"
            )

        access_token = github_account["access_token"]
        
        # Fetch repos
        headers = {
            "Authorization": f"token {access_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        response = requests.get(
            "https://api.github.com/user/repos",
            headers=headers,
            params={
                "sort": "updated",
                "direction": "desc",
                "per_page": 100,
                "type": "all"
            },
            timeout=30
        )
        response.raise_for_status()
        
        repositories = response.json()
        formatted_repos = []
        
        for repo in repositories:
            formatted_repos.append({
                "id": repo["id"],
                "name": repo["name"],
                "full_name": repo["full_name"],
                "description": repo.get("description"),
                "html_url": repo["html_url"],
                "clone_url": repo["clone_url"],
                "ssh_url": repo["ssh_url"],
                "private": repo["private"],
                "language": repo.get("language"),
                "stargazers_count": repo.get("stargazers_count", 0),
                "forks_count": repo.get("forks_count", 0),
                "default_branch": repo.get("default_branch", "main"),
                "updated_at": repo.get("updated_at"),
                "created_at": repo.get("created_at"),
                "size": repo.get("size", 0),
                "owner": {
                    "login": repo["owner"]["login"],
                    "avatar_url": repo["owner"]["avatar_url"]
                }
            })
            
        return {
            "repositories": formatted_repos,
            "count": len(formatted_repos)
        }
        
    except requests.RequestException as e:
        logger.error(f"GitHub API error: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to fetch repositories from GitHub"
        )
    except Exception as e:
        logger.error(f"Error fetching repos: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="Internal server error"
        )


@router.get("/github/repos/{owner}/{repo}/branches/", response_model=Dict[str, Any])
async def get_github_branches(
    owner: str,
    repo: str,
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """
    List branches for a GitHub repository.
    """
    try:
        # Get user's GitHub account (reuse logic)
        conn = basic_postgres_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT provider_user_id FROM oauth_accounts 
            WHERE user_id = %s AND provider = 'github'
        """, (current_user["id"],))
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not row:
             raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="GitHub account not connected"
            )
            
        github_account = oauth_db.get_oauth_account("github", row[0])
        access_token = github_account["access_token"]
        
        headers = {
            "Authorization": f"token {access_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        response = requests.get(
            f"https://api.github.com/repos/{owner}/{repo}/branches",
            headers=headers,
            params={"per_page": 100},
            timeout=30
        )
        response.raise_for_status()
        
        branches = response.json()
        formatted_branches = []
        
        for branch in branches:
            formatted_branches.append({
                "name": branch["name"],
                "protected": branch.get("protected", False),
                "commit_sha": branch["commit"]["sha"]
            })
            
        return {
            "branches": formatted_branches,
            "count": len(formatted_branches)
        }
        
    except requests.RequestException as e:
        logger.error(f"GitHub API error: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to fetch branches from GitHub"
        )
    except Exception as e:
        logger.error(f"Error fetching branches: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.post("/google")
async def google_token_login(data: GoogleTokenRequest):
    """
    Google ID token login (legacy/mobile flow).
    
    For mobile apps or legacy integrations that send ID tokens directly.
    """
    try:
        from google.oauth2 import id_token
        from google.auth.transport import requests as google_requests
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google auth library not installed"
        )
    
    try:
        # Verify the ID token
        idinfo = id_token.verify_oauth2_token(
            data.credential,
            google_requests.Request(),
            OAUTH_PROVIDERS["google"]["client_id"]
        )
        
        email = idinfo.get("email")
        if not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email not found in ID token"
            )
        
        # Create user info
        user_info = OAuthUserInfo(
            provider="google",
            provider_user_id=idinfo.get("sub", ""),
            email=email,
            first_name=idinfo.get("given_name"),
            last_name=idinfo.get("family_name"),
            avatar_url=idinfo.get("picture"),
            raw_data=idinfo
        )
        
        # Get or create user
        user, _ = oauth_service.get_or_create_user(user_info, {})
        if not user:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create or find user"
            )
        
        # Generate tokens
        tokens = create_tokens(user["id"], user["email"])
        
        return {
            "access": tokens.access,
            "refresh": tokens.refresh,
            "user": {
                "id": user["id"],
                "email": user["email"],
                "first_name": user.get("first_name"),
                "last_name": user.get("last_name")
            }
        }
    
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid ID token"
        )
    except Exception as e:
        logger.error(f"Google token login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication failed"
        )


@router.get("/github/repos")
async def list_github_repos(user: Dict[str, Any] = Depends(get_current_active_user)):
    """
    List user's GitHub repositories.
    
    Requires GitHub account to be connected via OAuth.
    """
    access_token = oauth_db.get_user_github_token(user["id"])
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="GitHub account not connected. Please connect via OAuth first."
        )
    
    try:
        response = requests.get(
            "https://api.github.com/user/repos",
            headers={
                "Authorization": f"token {access_token}",
                "Accept": "application/vnd.github.v3+json"
            },
            params={
                "sort": "updated",
                "direction": "desc",
                "per_page": 100,
                "type": "all"
            },
            timeout=30
        )
        response.raise_for_status()
        
        repos = response.json()
        formatted = []
        for repo in repos:
            formatted.append({
                "id": repo["id"],
                "name": repo["name"],
                "full_name": repo["full_name"],
                "description": repo.get("description"),
                "html_url": repo["html_url"],
                "clone_url": repo["clone_url"],
                "ssh_url": repo["ssh_url"],
                "private": repo["private"],
                "language": repo.get("language"),
                "default_branch": repo.get("default_branch", "main"),
                "updated_at": repo.get("updated_at"),
                "stargazers_count": repo.get("stargazers_count", 0),
                "forks_count": repo.get("forks_count", 0)
            })
        
        return {"repositories": formatted, "count": len(formatted)}
    
    except requests.RequestException as e:
        logger.error(f"Failed to fetch GitHub repos: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch repositories from GitHub"
        )


@router.get("/github/repos/{owner}/{repo}/branches")
async def list_github_branches(
    owner: str,
    repo: str,
    user: Dict[str, Any] = Depends(get_current_active_user)
):
    """
    List branches for a GitHub repository.
    
    Requires GitHub account to be connected via OAuth.
    """
    access_token = oauth_db.get_user_github_token(user["id"])
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="GitHub account not connected"
        )
    
    try:
        response = requests.get(
            f"https://api.github.com/repos/{owner}/{repo}/branches",
            headers={
                "Authorization": f"token {access_token}",
                "Accept": "application/vnd.github.v3+json"
            },
            params={"per_page": 100},
            timeout=30
        )
        response.raise_for_status()
        
        branches = response.json()
        formatted = [
            {
                "name": b["name"],
                "protected": b.get("protected", False),
                "commit_sha": b["commit"]["sha"]
            }
            for b in branches
        ]
        
        return {"branches": formatted, "count": len(formatted)}
    
    except requests.RequestException as e:
        logger.error(f"Failed to fetch branches for {owner}/{repo}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch branches"
        )


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _redirect_with_tokens(next_url: str, access_token: str, refresh_token: str) -> RedirectResponse:
    """Redirect to frontend with JWT tokens."""
    params = urllib.parse.urlencode({
        "access": access_token,
        "refresh": refresh_token,
        "next": next_url
    })
    # Trailing slash for Next.js compatibility
    redirect_url = f"{FRONTEND_URL}/auth/oauth/callback/?{params}"
    logger.info(f"Redirecting to frontend with tokens")
    response = RedirectResponse(redirect_url, status_code=302)
    response.set_cookie("oauth_access", access_token, max_age=120, httponly=False, samesite="lax", path="/")
    response.set_cookie("oauth_refresh", refresh_token, max_age=120, httponly=False, samesite="lax", path="/")
    return response


def _redirect_with_error(error: str) -> RedirectResponse:
    """Redirect to frontend with error message."""
    redirect_url = f"{FRONTEND_URL}/auth/login/?oauth_error={urllib.parse.quote(error)}"
    return RedirectResponse(redirect_url, status_code=302)


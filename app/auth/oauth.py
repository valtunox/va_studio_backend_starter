"""
OAuth2 Providers

Support for Google and GitHub OAuth2 authentication.
"""

from typing import Optional
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import settings
from app.core.database import get_db
from app.core.security import create_access_token, create_refresh_token
from app.orm.user import User
from app.schemas.common import TokenResponse


router = APIRouter(prefix="/auth/oauth", tags=["OAuth"])


class OAuthProvider:
    """Base OAuth provider class."""

    name: str
    authorize_url: str
    token_url: str
    userinfo_url: str
    scopes: list[str]

    def __init__(self, client_id: str, client_secret: str, redirect_uri: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri

    def get_authorize_url(self, state: str) -> str:
        """Get authorization URL."""
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": " ".join(self.scopes),
            "state": state,
        }
        return f"{self.authorize_url}?{urlencode(params)}"

    async def get_tokens(self, code: str) -> dict:
        """Exchange authorization code for tokens."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.token_url,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "code": code,
                    "redirect_uri": self.redirect_uri,
                    "grant_type": "authorization_code",
                },
                headers={"Accept": "application/json"},
            )

            if response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to get tokens from OAuth provider",
                )

            return response.json()

    async def get_user_info(self, access_token: str) -> dict:
        """Get user info from OAuth provider."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.userinfo_url,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json",
                },
            )

            if response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to get user info from OAuth provider",
                )

            return response.json()


class GoogleOAuth(OAuthProvider):
    """Google OAuth2 provider."""

    name = "google"
    authorize_url = "https://accounts.google.com/o/oauth2/v2/auth"
    token_url = "https://oauth2.googleapis.com/token"
    userinfo_url = "https://www.googleapis.com/oauth2/v2/userinfo"
    scopes = ["openid", "email", "profile"]

    def get_authorize_url(self, state: str) -> str:
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": " ".join(self.scopes),
            "state": state,
            "access_type": "offline",
            "prompt": "consent",
        }
        return f"{self.authorize_url}?{urlencode(params)}"


class GitHubOAuth(OAuthProvider):
    """GitHub OAuth2 provider."""

    name = "github"
    authorize_url = "https://github.com/login/oauth/authorize"
    token_url = "https://github.com/login/oauth/access_token"
    userinfo_url = "https://api.github.com/user"
    scopes = ["user:email", "read:user"]

    async def get_user_info(self, access_token: str) -> dict:
        """Get user info from GitHub."""
        async with httpx.AsyncClient() as client:
            # Get user info
            response = await client.get(
                self.userinfo_url,
                headers={
                    "Authorization": f"token {access_token}",
                    "Accept": "application/vnd.github.v3+json",
                },
            )

            if response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to get user info from GitHub",
                )

            user_data = response.json()

            # Get primary email if not public
            if not user_data.get("email"):
                emails_response = await client.get(
                    "https://api.github.com/user/emails",
                    headers={
                        "Authorization": f"token {access_token}",
                        "Accept": "application/vnd.github.v3+json",
                    },
                )

                if emails_response.status_code == 200:
                    emails = emails_response.json()
                    primary_email = next(
                        (e["email"] for e in emails if e["primary"] and e["verified"]),
                        None,
                    )
                    if primary_email:
                        user_data["email"] = primary_email

            return user_data


def get_oauth_provider(provider: str) -> OAuthProvider:
    """Get OAuth provider instance."""
    if provider == "google":
        if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Google OAuth not configured",
            )
        return GoogleOAuth(
            client_id=settings.GOOGLE_CLIENT_ID,
            client_secret=settings.GOOGLE_CLIENT_SECRET,
            redirect_uri=f"{settings.OAUTH_REDIRECT_URL}/google",
        )
    elif provider == "github":
        if not settings.GITHUB_CLIENT_ID or not settings.GITHUB_CLIENT_SECRET:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="GitHub OAuth not configured",
            )
        return GitHubOAuth(
            client_id=settings.GITHUB_CLIENT_ID,
            client_secret=settings.GITHUB_CLIENT_SECRET,
            redirect_uri=f"{settings.OAUTH_REDIRECT_URL}/github",
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown OAuth provider: {provider}",
        )


@router.get("/{provider}/authorize")
async def oauth_authorize(provider: str, state: Optional[str] = None) -> dict:
    """
    Get OAuth authorization URL.

    Returns the URL to redirect user for OAuth login.
    """
    oauth = get_oauth_provider(provider)
    state = state or "default"
    authorize_url = oauth.get_authorize_url(state)

    return {"url": authorize_url, "provider": provider}


@router.post("/{provider}/callback", response_model=TokenResponse)
async def oauth_callback(
    provider: str,
    code: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Handle OAuth callback.

    Exchanges authorization code for tokens and creates/updates user.
    """
    oauth = get_oauth_provider(provider)

    # Get tokens from provider
    tokens = await oauth.get_tokens(code)
    access_token = tokens.get("access_token")

    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to get access token",
        )

    # Get user info
    user_info = await oauth.get_user_info(access_token)

    email = user_info.get("email")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email not provided by OAuth provider",
        )

    # Find or create user
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user:
        # Create new user
        user = User(
            email=email,
            username=user_info.get("login") or user_info.get("name", "").replace(" ", "_").lower(),
            full_name=user_info.get("name"),
            avatar_url=user_info.get("avatar_url") or user_info.get("picture"),
            hashed_password="",  # OAuth users don't have password
            is_verified=True,  # OAuth emails are verified
            oauth_provider=provider,
            oauth_id=str(user_info.get("id")),
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    else:
        # Update OAuth info if needed
        if not user.oauth_provider:
            user.oauth_provider = provider
            user.oauth_id = str(user_info.get("id"))
            await db.commit()

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled",
        )

    # Create JWT tokens
    jwt_access_token = create_access_token(user.id)
    jwt_refresh_token = create_refresh_token(user.id)

    return {
        "access_token": jwt_access_token,
        "refresh_token": jwt_refresh_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }

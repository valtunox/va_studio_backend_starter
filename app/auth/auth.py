"""
Authentication Module - All-in-One
=================================

Complete authentication system for InfinityAI FastAPI Platform.
Uses existing Django PostgreSQL tables (users, organizations, workspaces, subscriptions).

Features:
- JWT Token-based authentication (access + refresh tokens)
- User registration with automatic workspace/organization creation
- User login/logout
- Password change and reset functionality
- Profile management
- API Key authentication for developers

Uses: app.core.db for PostgreSQL connection to Django tables.

Routes (prefix: /api/v1/auth):
    POST   /register              - User registration
    POST   /login                 - User login (JWT tokens)
    POST   /token/refresh         - Refresh access token
    POST   /logout                - Blacklist refresh token
    GET    /profile               - Get current user profile
    PUT    /profile               - Update user profile
    POST   /complete-profile      - Complete profile for social auth users
    POST   /change-password       - Change password
    POST   /forgot-password       - Request password reset code
    POST   /reset-password        - Reset password with code
    PUT    /organization/update   - Update organization
    GET    /developer/keys        - List API keys
    POST   /developer/keys        - Create API key
    DELETE /developer/keys/{id}   - Deactivate API key
    GET    /health                - Auth service health check
"""

import os
import re
import uuid
import secrets
import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Any, Dict, Union
from enum import Enum

import psycopg2
import requests

from fastapi import APIRouter, Depends, HTTPException, status, Request, Response, Header, Body
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm, HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field, EmailStr as _PydanticEmailStr, validator, root_validator
import jwt

try:
    from passlib.context import CryptContext
except ModuleNotFoundError:  # pragma: no cover
    CryptContext = None

try:
    import email_validator  # noqa: F401

    EmailStrType = _PydanticEmailStr
except ModuleNotFoundError:  # pragma: no cover
    EmailStrType = str

# Database connection from core.db
try:
    from app.core.db import basic_postgres_connection, async_postgres_connection
except ModuleNotFoundError:  # pragma: no cover
    async_postgres_connection = None

    def basic_postgres_connection():
        postgres_db = os.environ.get("POSTGRES_DB", "vacloudopsdb1")
        postgres_user = os.environ.get("POSTGRES_USER", "postgres")
        postgres_password = os.environ.get("POSTGRES_PASSWORD", "postgres")
        postgres_host = os.environ.get("POSTGRES_HOST", "127.0.0.1")
        postgres_port = int(os.environ.get("POSTGRES_PORT", 5432))
        return psycopg2.connect(
            dbname=postgres_db,
            user=postgres_user,
            password=postgres_password,
            host=postgres_host,
            port=postgres_port,
        )

# ============================================================================
# CONFIGURATION
# ============================================================================
from app.core.logger import (
    get_logger,
    log_api_request,
    log_api_response,
    set_correlation_id,
    RequestTimer,
)

logger = get_logger(__name__)

# JWT Settings
SECRET_KEY = os.getenv("SECRET_KEY", "your-super-secret-key-change-in-production")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto") if CryptContext else None

# OAuth2 scheme for token extraction
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)
http_bearer = HTTPBearer(auto_error=False)

# In-memory token blacklist (use Redis in production)
_token_blacklist: set = set()


# ============================================================================
# PYDANTIC SCHEMAS
# ============================================================================

class TokenType(str, Enum):
    ACCESS = "access"
    REFRESH = "refresh"


class TokenPayload(BaseModel):
    """JWT token payload schema"""
    sub: str  # User email
    user_id: int
    email: str
    type: TokenType
    exp: datetime
    iat: datetime
    jti: str  # Token ID for blacklisting


class TokenResponse(BaseModel):
    """Token response schema"""
    access: str
    refresh: str
    token_type: str = "bearer"


class TokenRefreshRequest(BaseModel):
    """Token refresh request schema"""
    refresh: str = Field(..., description="Refresh token")


class UserRegisterRequest(BaseModel):
    """User registration request schema"""
    email: EmailStrType = Field(..., description="User email address")
    username: str = Field(..., min_length=4, max_length=50, description="Username (4-50 chars)")
    password: str = Field(..., min_length=8, description="Password (min 8 chars)")
    first_name: Optional[str] = Field(None, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, max_length=15)
    organization_name: Optional[str] = Field(None, max_length=255, description="Organization name")
    company_name: Optional[str] = Field(None, max_length=255, description="Company name")

    @validator("username")
    def validate_username(cls, v):
        if not re.match(r'^[a-zA-Z0-9_]+$', v):
            raise ValueError("Username can only contain letters, numbers, and underscores")
        return v

    @validator("password")
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not re.search(r'[A-Z]', v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r'[a-z]', v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r'\d', v):
            raise ValueError("Password must contain at least one digit")
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', v):
            raise ValueError("Password must contain at least one special character")
        return v


class UserLoginRequest(BaseModel):
    """User login request schema — accepts email or username."""
    email: Optional[EmailStrType] = Field(None, description="User email")
    username: Optional[str] = Field(None, description="Username (alternative to email)")
    password: str = Field(..., description="User password")

    @root_validator(pre=True)
    def require_email_or_username(cls, values):
        if not values.get("email") and not values.get("username"):
            raise ValueError("Either email or username is required")
        return values


class UserResponse(BaseModel):
    """User response schema"""
    id: int
    email: str
    username: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    is_verified: bool = False
    is_active: bool = True
    is_staff: bool = False
    date_joined: Optional[datetime] = None
    last_login: Optional[datetime] = None
    organization: Optional[Dict[str, Any]] = None
    workspace: Optional[Dict[str, Any]] = None
    subscription: Optional[Dict[str, Any]] = None
    connected_providers: Optional[Dict[str, bool]] = None


class UserProfileUpdateRequest(BaseModel):
    """User profile update request schema"""
    first_name: Optional[str] = Field(None, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, max_length=15)


class CompleteProfileRequest(BaseModel):
    """Complete profile request schema (social auth + onboarding)."""
    location: Optional[str] = None
    organization_name: Optional[str] = None
    description: Optional[str] = None
    platform_usage: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    phone: Optional[str] = None
    country: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    company_name: Optional[str] = None
    occupation: Optional[str] = None
    purpose_of_account: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state_province: Optional[str] = None
    postal_code: Optional[str] = None

class PasswordChangeRequest(BaseModel):
    """Password change request schema"""
    current_password: str = Field(..., description="Current password")
    new_password: str = Field(..., min_length=8, description="New password")

    @validator("new_password")
    def validate_new_password(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not re.search(r'[A-Z]', v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r'[a-z]', v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r'\d', v):
            raise ValueError("Password must contain at least one digit")
        return v


class ForgotPasswordRequest(BaseModel):
    """Forgot password request schema"""
    email: EmailStrType = Field(..., description="User email")


class ResetPasswordRequest(BaseModel):
    """Reset password request schema"""
    email: EmailStrType = Field(..., description="User email")
    verification_code: str = Field(..., description="Verification code")
    new_password: str = Field(..., min_length=8, description="New password")


class OrganizationUpdateRequest(BaseModel):
    """Organization update request schema"""
    name: Optional[str] = Field(None, max_length=255)
    tenant_subscription_id: Optional[str] = None
    tenant_primary_node_host: Optional[str] = None
    tenant_primary_domain: Optional[str] = None


class APIKeyCreateRequest(BaseModel):
    """API key create request schema"""
    name: str = Field(..., max_length=100, description="API key name")
    description: Optional[str] = Field(None, description="Key description")
    environment: str = Field("DEVELOPMENT", description="DEVELOPMENT or PRODUCTION")
    allowed_services: Optional[List[str]] = Field(default_factory=list)
    disallowed_services: Optional[List[str]] = Field(default_factory=list)
    scopes: Optional[List[str]] = Field(default_factory=list)
    is_read_only: bool = Field(False, description="Whether the key is read-only")
    rate_limit: Optional[int] = None
    allowed_ips: Optional[List[str]] = Field(default_factory=list)
    metadata: Optional[Dict[str, Any]] = None
    expires_in_days: Optional[int] = Field(None, description="Days until expiry")
    expires_at: Optional[datetime] = None


class APIKeyUpdateRequest(BaseModel):
    """API key update request schema"""
    name: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    allowed_services: Optional[List[str]] = None
    disallowed_services: Optional[List[str]] = None
    scopes: Optional[List[str]] = None
    is_read_only: Optional[bool] = None
    rate_limit: Optional[int] = None
    allowed_ips: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None
    expires_at: Optional[datetime] = None
    expires_in_days: Optional[int] = None
    is_active: Optional[bool] = None


class APIKeyResponse(BaseModel):
    """API key response schema"""
    id: str
    name: str
    environment: str
    key_preview: str
    is_active: bool
    created_at: datetime
    expires_at: Optional[datetime] = None
    usage_count: int = 0
    token: Optional[str] = None  # Only on creation
    description: Optional[str] = None
    allowed_services: Optional[List[str]] = None
    disallowed_services: Optional[List[str]] = None
    scopes: Optional[List[str]] = None
    is_read_only: Optional[bool] = None
    rate_limit: Optional[int] = None
    last_ip: Optional[str] = None
    last_used_at: Optional[datetime] = None
    allowed_ips: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None
    is_expired: Optional[bool] = None
    days_until_expiry: Optional[int] = None


class LogoutRequest(BaseModel):
    """Logout request schema"""
    refresh: str = Field(..., description="Refresh token to blacklist")


class GoogleTokenRequest(BaseModel):
    """Google ID token request schema (legacy)."""
    credential: str = Field(..., description="Google ID token")


# ============================================================================
# AUTH UTILITIES - Password & Token Management
# ============================================================================

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash (Django compatible)."""
    # Django uses pbkdf2_sha256 by default
    if hashed_password.startswith("pbkdf2_sha256$"):
        # Django format: algorithm$iterations$salt$hash
        parts = hashed_password.split("$")
        if len(parts) == 4:
            algorithm, iterations, salt, hash_b64 = parts
            import base64
            iterations = int(iterations)
            dk = hashlib.pbkdf2_hmac(
                "sha256",
                plain_password.encode("utf-8"),
                salt.encode("utf-8"),
                iterations
            )
            computed_hash = base64.b64encode(dk).decode("utf-8")
            return computed_hash == hash_b64
    # Fallback to bcrypt
    if pwd_context:
        return pwd_context.verify(plain_password, hashed_password)
    try:
        import bcrypt

        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        raise RuntimeError(
            "Cannot verify non-Django password hash: install 'passlib' (recommended) "
            "or ensure 'bcrypt' is available."
        )


def hash_password(password: str) -> str:
    """Hash a password using Django-compatible PBKDF2."""
    import base64
    salt = secrets.token_hex(12)
    iterations = 600000  # Django 4.x default
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iterations
    )
    hash_b64 = base64.b64encode(dk).decode("utf-8")
    return f"pbkdf2_sha256${iterations}${salt}${hash_b64}"


def create_access_token(user_id: int, email: str) -> str:
    """Create a JWT access token."""
    jti = str(uuid.uuid4())
    payload = {
        "sub": email,
        "user_id": user_id,
        "email": email,
        "type": TokenType.ACCESS.value,
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        "jti": jti
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(user_id: int, email: str) -> str:
    """Create a JWT refresh token."""
    jti = str(uuid.uuid4())
    payload = {
        "sub": email,
        "user_id": user_id,
        "email": email,
        "type": TokenType.REFRESH.value,
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        "jti": jti
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_tokens(user_id: int, email: str) -> TokenResponse:
    """Create access and refresh tokens."""
    access_token = create_access_token(user_id, email)
    refresh_token = create_refresh_token(user_id, email)
    return TokenResponse(access=access_token, refresh=refresh_token)


def decode_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode and validate a JWT token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        jti = payload.get("jti")
        if jti and jti in _token_blacklist:
            return None
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def blacklist_refresh_token(token: str) -> bool:
    """Add a refresh token to the blacklist."""
    payload = decode_token(token)
    if payload and payload.get("jti"):
        _token_blacklist.add(payload["jti"])
        return True
    return False


def generate_verification_code() -> str:
    """Generate a 6-digit verification code."""
    return "".join([str(secrets.randbelow(10)) for _ in range(6)])


def generate_api_key(environment: str = "DEVELOPMENT") -> str:
    """Generate a secure API key."""
    prefix = "xc_dev_" if environment == "DEVELOPMENT" else "xc_live_"
    return prefix + secrets.token_urlsafe(40)


# ============================================================================
# DATABASE MANAGER - Direct PostgreSQL Access to Django Tables
# ============================================================================

class AuthDatabaseManager:
    """Direct PostgreSQL access to Django user/organization/workspace tables."""

    def _get_table_columns(self, table_name: str) -> List[str]:
        try:
            conn = basic_postgres_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = %s
                """,
                (table_name,),
            )
            columns = [row[0] for row in cursor.fetchall()]
            cursor.close()
            conn.close()
            return columns
        except Exception as e:
            logger.error(f"Error fetching columns for {table_name}: {e}")
            return []

    @staticmethod
    def _parse_json_field(value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, (list, dict)):
            return value
        if isinstance(value, str) and value.strip():
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        return value

    @staticmethod
    def _serialize_json_field(value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, (list, dict)):
            return json.dumps(value)
        return value

    @staticmethod
    def _normalize_datetime(value: Optional[datetime]) -> Optional[datetime]:
        if not value:
            return value
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Fetch user by email from Django users_user table."""
        try:
            conn = basic_postgres_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, email, username, password, first_name, last_name, phone,
                       is_verified, is_active, is_staff, is_superuser, date_joined, 
                       last_login, organization_id, verification_code,
                       mfa_enabled, mfa_secret, social_google, social_github, social_microsoft
                FROM users_user
                WHERE email = %s
            """, (email,))
            row = cursor.fetchone()
            cursor.close()
            conn.close()
            if row:
                return {
                    "id": row[0], "email": row[1], "username": row[2], "password": row[3],
                    "first_name": row[4], "last_name": row[5], "phone": row[6],
                    "is_verified": row[7], "is_active": row[8], "is_staff": row[9],
                    "is_superuser": row[10], "date_joined": row[11], "last_login": row[12],
                    "organization_id": row[13], "verification_code": row[14],
                    "mfa_enabled": row[15], "mfa_secret": row[16],
                    "social_google": row[17], "social_github": row[18], "social_microsoft": row[19]
                }
            return None
        except Exception as e:
            logger.error(f"Error fetching user by email: {e}")
            return None

    def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Fetch user by username from Django users_user table."""
        try:
            conn = basic_postgres_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, email, username, password, first_name, last_name, phone,
                       is_verified, is_active, is_staff, is_superuser, date_joined,
                       last_login, organization_id, verification_code,
                       mfa_enabled, mfa_secret, social_google, social_github, social_microsoft
                FROM users_user
                WHERE username = %s
            """, (username,))
            row = cursor.fetchone()
            cursor.close()
            conn.close()
            if row:
                return {
                    "id": row[0], "email": row[1], "username": row[2], "password": row[3],
                    "first_name": row[4], "last_name": row[5], "phone": row[6],
                    "is_verified": row[7], "is_active": row[8], "is_staff": row[9],
                    "is_superuser": row[10], "date_joined": row[11], "last_login": row[12],
                    "organization_id": row[13], "verification_code": row[14],
                    "mfa_enabled": row[15], "mfa_secret": row[16],
                    "social_google": row[17], "social_github": row[18], "social_microsoft": row[19]
                }
            return None
        except Exception as e:
            logger.error(f"Error fetching user by username: {e}")
            return None

    def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Fetch user by ID from Django users_user table."""
        try:
            conn = basic_postgres_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, email, username, password, first_name, last_name, phone,
                       is_verified, is_active, is_staff, is_superuser, date_joined, 
                       last_login, organization_id
                FROM users_user
                WHERE id = %s
            """, (user_id,))
            row = cursor.fetchone()
            cursor.close()
            conn.close()
            if row:
                return {
                    "id": row[0], "email": row[1], "username": row[2], "password": row[3],
                    "first_name": row[4], "last_name": row[5], "phone": row[6],
                    "is_verified": row[7], "is_active": row[8], "is_staff": row[9],
                    "is_superuser": row[10], "date_joined": row[11], "last_login": row[12],
                    "organization_id": row[13]
                }
            return None
        except Exception as e:
            logger.error(f"Error fetching user by id: {e}")
            return None

    def create_user(self, data: UserRegisterRequest) -> Optional[Dict[str, Any]]:
        """Create a new user with organization and workspace."""
        try:
            conn = basic_postgres_connection()
            cursor = conn.cursor()

            # Introspect table columns so this code works across schema variants
            cursor.execute(
                """
                SELECT column_name, is_nullable, data_type, column_default
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'users_user'
                """
            )
            users_user_columns_meta = cursor.fetchall()
            users_user_columns = {row[0] for row in users_user_columns_meta}

            # Check if email already exists
            cursor.execute("SELECT id FROM users_user WHERE email = %s", (data.email,))
            if cursor.fetchone():
                cursor.close()
                conn.close()
                raise ValueError("Email already exists")

            # Check if username already exists
            cursor.execute("SELECT id FROM users_user WHERE username = %s", (data.username,))
            if cursor.fetchone():
                cursor.close()
                conn.close()
                raise ValueError("Username already exists")

            # Ensure organization_name and company_name are synced
            org_name = data.organization_name or data.company_name or data.username
            company_name = data.company_name or data.organization_name or ""
            org_id = str(uuid.uuid4())
            tenant_sub_id = f"tenant_subscription_{str(uuid.uuid4())[:12]}"
            cursor.execute("""
                INSERT INTO users_organization (id, name, tenant_subscription_id, created_at, updated_at)
                VALUES (%s, %s, %s, NOW(), NOW())
                RETURNING id
            """, (org_id, org_name, tenant_sub_id))
            org_result = cursor.fetchone()
            organization_id = org_result[0]

            # Hash password
            password_hash = hash_password(data.password)

            # Create user
            now = datetime.utcnow()
            candidate_values: Dict[str, Any] = {
                "email": data.email,
                "username": data.username,
                "password": password_hash,
                "first_name": data.first_name or "",
                "last_name": data.last_name or "",
                "company_name": company_name,
                "phone": data.phone if data.phone else None,  # NULL for unique constraint
                "is_verified": False,
                "is_active": True,
                "is_staff": False,
                "is_superuser": False,
                "date_joined": now,
                "organization_id": organization_id,
                "kyc_completed": True,
                "deployed_where": "AMERICA-1",
                "mfa_enabled": False,
                "mfa_secret": None,
                "mfa_setup_completed": False,
                "social_google": False,
                "social_github": False,
                "social_microsoft": False,
                "verification_code": None,
                # Some schemas have OTP-related non-null columns
                "last_otp_secret": "",
            }

            # Auto-fill any required (NOT NULL) columns without defaults to avoid insert failures.
            # Skip columns that are auto-generated (serial/identity/generated).
            for column_name, is_nullable, data_type, column_default in users_user_columns_meta:
                if column_name in candidate_values:
                    continue
                if column_name not in users_user_columns:
                    continue
                if is_nullable == "YES":
                    continue
                # Skip auto-generated columns: id (primary key), serial, identity
                if column_name == "id":
                    continue
                if column_default:
                    col_default_str = str(column_default).lower()
                    if "nextval(" in col_default_str or "generated" in col_default_str:
                        continue

                if data_type in {"boolean"}:
                    candidate_values[column_name] = False
                elif data_type in {"integer", "bigint", "smallint"}:
                    candidate_values[column_name] = 0
                elif data_type in {"uuid"}:
                    candidate_values[column_name] = str(uuid.uuid4())
                elif data_type in {"timestamp without time zone", "timestamp with time zone", "date"}:
                    candidate_values[column_name] = now
                else:
                    # varchar/text/unknown
                    candidate_values[column_name] = ""

            insert_columns = [c for c in candidate_values.keys() if c in users_user_columns]
            insert_values = [candidate_values[c] for c in insert_columns]
            placeholders = ", ".join(["%s"] * len(insert_columns))

            cursor.execute(
                f"""
                INSERT INTO users_user ({', '.join(insert_columns)})
                VALUES ({placeholders})
                RETURNING id, email, username, first_name, last_name, date_joined
                """,
                tuple(insert_values),
            )
            user_row = cursor.fetchone()
            user_id = user_row[0]

            # Call Golang workspace setup API to create Vault workspace
            workspace_setup_response = None
            CORE_INFRASTRUCTURE_URL = os.getenv("CORE_INFRASTRUCTURE_URL", "http://localhost:8743")
            try:
                import requests
                workspace_payload = {
                    "username": data.username,
                    "email": data.email,
                    "organization": org_name
                }
                logger.info(f"Calling workspace setup API for user {data.username}")
                response = requests.post(
                    f"{CORE_INFRASTRUCTURE_URL}/api/v2/setup/workspace",
                    json=workspace_payload,
                    timeout=30
                )
                if response.status_code == 200:
                    workspace_setup_response = response.json()
                    logger.info(f"Workspace setup successful for {data.username}")
                else:
                    logger.warning(f"Workspace setup API returned status {response.status_code}: {response.text}")
            except Exception as e:
                logger.error(f"Failed to call workspace setup API: {e}")
                # Continue with basic workspace creation even if API call fails

            # Create default workspace with data from Golang API
            workspace_id = str(uuid.uuid4())
            session_id = str(uuid.uuid4())
            workspace_config = {
                "environment": "development",
                "region": "us-east-1",
                "created_by": data.email,
                "workspace_type": "standard"
            }
            
            # Extract state_facts and other details from Golang API response
            state_facts = {}
            vault_role_id = None
            vault_secret_id = None
            vault_workspace_id = None
            
            if workspace_setup_response and workspace_setup_response.get("status") == "success":
                vault_role_id = workspace_setup_response.get("role_id")
                vault_secret_id = workspace_setup_response.get("secret_id")
                vault_workspace_id = workspace_setup_response.get("username")
                
                # Build state_facts from API response
                state_facts = {
                    "vault_role_id": vault_role_id,
                    "vault_secret_id": vault_secret_id,
                    "vault_workspace_id": vault_workspace_id,
                    "workspace_path": workspace_setup_response.get("data", {}).get("workspace_path"),
                    "metadata": workspace_setup_response.get("data", {}).get("metadata", {}),
                    "organization": workspace_setup_response.get("organization"),
                    "setup_timestamp": workspace_setup_response.get("data", {}).get("metadata", {}).get("created_at"),
                    "vault_entity_id": workspace_setup_response.get("data", {}).get("metadata", {}).get("entity_id"),
                    "vault_group_id": workspace_setup_response.get("data", {}).get("metadata", {}).get("group_id"),
                    "vault_integration": "enabled" if vault_role_id else "disabled"
                }
                
                # Update workspace_config with Vault details
                workspace_config.update({
                    "vault_enabled": True,
                    "vault_role_id": vault_role_id,
                    "vault_workspace_id": vault_workspace_id
                })
            
            # Insert workspace with state_facts
            cursor.execute("""
                INSERT INTO infrastructure_workspace (
                    id, name, user_id, organization_id, is_active, is_default_workspace,
                    session_id, configuration, state_facts, 
                    "Vault_workspace_id", created_at, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                RETURNING id, name
            """, (
                workspace_id, data.username, user_id, organization_id,
                True, True, session_id, 
                json.dumps(workspace_config),
                json.dumps(state_facts) if state_facts else None,
                vault_workspace_id
            ))
            workspace_row = cursor.fetchone()

            conn.commit()
            cursor.close()
            conn.close()

            return {
                "id": user_id,
                "email": user_row[1],
                "username": user_row[2],
                "first_name": user_row[3],
                "last_name": user_row[4],
                "date_joined": user_row[5],
                "organization": {
                    "id": str(organization_id),
                    "name": org_name
                },
                "workspace": {
                    "id": str(workspace_row[0]),
                    "name": workspace_row[1],
                    "vault_enabled": bool(vault_role_id),
                    "state_facts": state_facts
                }
            }
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            raise

    def update_user(self, user_id: int, data: Dict[str, Any]) -> bool:
        """Update user fields."""
        try:
            conn = basic_postgres_connection()
            cursor = conn.cursor()
            
            set_clauses = []
            values = []
            for key, value in data.items():
                if value is not None:
                    set_clauses.append(f"{key} = %s")
                    values.append(value)
            
            if not set_clauses:
                return False
            
            values.append(user_id)
            cursor.execute(f"""
                UPDATE users_user
                SET {', '.join(set_clauses)}
                WHERE id = %s
            """, tuple(values))
            
            conn.commit()
            cursor.close()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Error updating user: {e}")
            return False

    def update_last_login(self, user_id: int) -> bool:
        """Update user's last login timestamp."""
        try:
            conn = basic_postgres_connection()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE users_user SET last_login = NOW() WHERE id = %s
            """, (user_id,))
            conn.commit()
            cursor.close()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Error updating last login: {e}")
            return False

    def get_organization(self, org_id: str) -> Optional[Dict[str, Any]]:
        """Fetch organization by ID."""
        try:
            conn = basic_postgres_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, name, tenant_subscription_id, tenant_primary_node_host,
                       tenant_primary_domain, created_at
                FROM users_organization
                WHERE id = %s
            """, (org_id,))
            row = cursor.fetchone()
            cursor.close()
            conn.close()
            if row:
                return {
                    "id": str(row[0]), "name": row[1],
                    "tenant_subscription_id": row[2],
                    "tenant_primary_node_host": row[3],
                    "tenant_primary_domain": row[4],
                    "created_at": row[5]
                }
            return None
        except Exception as e:
            logger.error(f"Error fetching organization: {e}")
            return None

    def update_organization(self, org_id: str, data: Dict[str, Any]) -> bool:
        """Update organization fields."""
        try:
            conn = basic_postgres_connection()
            cursor = conn.cursor()
            
            set_clauses = []
            values = []
            for key, value in data.items():
                if value is not None:
                    set_clauses.append(f"{key} = %s")
                    values.append(value)
            
            if not set_clauses:
                return False
            
            set_clauses.append("updated_at = NOW()")
            values.append(org_id)
            
            cursor.execute(f"""
                UPDATE users_organization
                SET {', '.join(set_clauses)}
                WHERE id = %s
            """, tuple(values))
            
            conn.commit()
            cursor.close()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Error updating organization: {e}")
            return False

    def get_workspace(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Fetch user's default workspace with full details including state_facts."""
        try:
            conn = basic_postgres_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, name, is_active, is_default_workspace, configuration, 
                       created_at, state_facts, "Vault_workspace_id", session_id
                FROM infrastructure_workspace
                WHERE user_id = %s
                ORDER BY is_default_workspace DESC, created_at DESC
                LIMIT 1
            """, (user_id,))
            row = cursor.fetchone()
            cursor.close()
            conn.close()
            if row:
                return {
                    "id": str(row[0]), "name": row[1], "is_active": row[2],
                    "is_default": row[3], "configuration": row[4], "created_at": row[5],
                    "state_facts": row[6], "vault_workspace_id": row[7], "session_id": str(row[8])
                }
            return None
        except Exception as e:
            logger.error(f"Error fetching workspace: {e}")
            return None

    def update_workspace_state_facts(self, workspace_id: str, state_facts: Dict[str, Any]) -> bool:
        """Update workspace state_facts with data from Golang API."""
        try:
            conn = basic_postgres_connection()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE infrastructure_workspace
                SET state_facts = %s, updated_at = NOW()
                WHERE id = %s
            """, (json.dumps(state_facts), workspace_id))
            conn.commit()
            cursor.close()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Error updating workspace state_facts: {e}")
            return False

    def get_user_subscription(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Fetch user's current subscription."""
        try:
            conn = basic_postgres_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT us.id, sp.name as plan_name, us.status, 
                       us.current_period_start, us.current_period_end
                FROM subscriptions_usersubscription us
                JOIN subscriptions_subscriptionplan sp ON us.plan_id = sp.id
                WHERE us.user_id = %s
                ORDER BY us.created_at DESC
                LIMIT 1
            """, (user_id,))
            row = cursor.fetchone()
            cursor.close()
            conn.close()
            if row:
                raw_plan = row[1] or ""
                normalized_plan = raw_plan.lower().replace(" plan", "").strip()
                raw_status = row[2] or ""
                normalized_status = raw_status.lower() if isinstance(raw_status, str) else raw_status
                return {
                    "id": str(row[0]), "plan": normalized_plan or raw_plan, "status": normalized_status,
                    "current_period_start": row[3], "current_period_end": row[4]
                }
            return {"plan": "free", "status": "inactive"}
        except Exception as e:
            logger.error(f"Error fetching subscription: {e}")
            return {"plan": "free", "status": "inactive"}

    def get_api_keys(self, user_id: int) -> List[Dict[str, Any]]:
        """Fetch user's API keys."""
        try:
            columns = set(self._get_table_columns("users_apikey"))
            base_columns = [
                "id",
                "name",
                "environment",
                "token_hash",
                "is_active",
                "created_at",
                "expires_at",
                "usage_count",
            ]
            optional_columns = [
                "description",
                "allowed_services",
                "disallowed_services",
                "scopes",
                "is_read_only",
                "rate_limit",
                "last_ip",
                "last_used_at",
                "allowed_ips",
                "metadata",
            ]
            select_columns = [c for c in base_columns if c in columns]
            select_columns += [c for c in optional_columns if c in columns]

            conn = basic_postgres_connection()
            cursor = conn.cursor()
            cursor.execute(
                f"""
                SELECT {', '.join(select_columns)}
                FROM users_apikey
                WHERE user_id = %s
                ORDER BY created_at DESC
                """,
                (user_id,),
            )
            rows = cursor.fetchall()
            cursor.close()
            conn.close()
            
            keys = []
            for row in rows:
                record = dict(zip(select_columns, row))
                token_hash = record.get("token_hash") or ""
                env = record.get("environment") or "DEVELOPMENT"
                key_preview = f"xc_{'dev' if env == 'DEVELOPMENT' else 'live'}_{'•' * 32}{token_hash[-4:] if token_hash else ''}"
                expires_at = self._normalize_datetime(record.get("expires_at"))
                now = datetime.now(timezone.utc)
                days_until_expiry = None
                is_expired = None
                if expires_at:
                    delta = expires_at - now
                    days_until_expiry = max(0, delta.days)
                    is_expired = expires_at <= now

                keys.append(
                    {
                        "id": str(record.get("id")),
                        "name": record.get("name"),
                        "environment": env,
                        "key_preview": key_preview,
                        "is_active": record.get("is_active"),
                        "created_at": record.get("created_at"),
                        "expires_at": expires_at,
                        "usage_count": record.get("usage_count") or 0,
                        "description": record.get("description"),
                        "allowed_services": self._parse_json_field(record.get("allowed_services")),
                        "disallowed_services": self._parse_json_field(record.get("disallowed_services")),
                        "scopes": self._parse_json_field(record.get("scopes")),
                        "is_read_only": record.get("is_read_only"),
                        "rate_limit": record.get("rate_limit"),
                        "last_ip": record.get("last_ip"),
                        "last_used_at": record.get("last_used_at"),
                        "allowed_ips": self._parse_json_field(record.get("allowed_ips")),
                        "metadata": self._parse_json_field(record.get("metadata")),
                        "is_expired": is_expired,
                        "days_until_expiry": days_until_expiry,
                    }
                )
            return keys
        except Exception as e:
            logger.error(f"Error fetching API keys: {e}")
            return []

    def create_api_key(self, user_id: int, data: APIKeyCreateRequest) -> Dict[str, Any]:
        """Create a new API key."""
        try:
            columns = set(self._get_table_columns("users_apikey"))
            conn = basic_postgres_connection()
            cursor = conn.cursor()
            
            key_id = str(uuid.uuid4())
            raw_token = generate_api_key(data.environment)
            token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
            expires_at = None
            if data.expires_at:
                expires_at = data.expires_at
            elif data.expires_in_days:
                expires_at = datetime.utcnow() + timedelta(days=data.expires_in_days)

            insert_columns: List[str] = []
            placeholders: List[str] = []
            values: List[Any] = []

            def add_value(column: str, value: Any) -> None:
                if column in columns:
                    insert_columns.append(column)
                    placeholders.append("%s")
                    values.append(value)

            def add_now(column: str) -> None:
                if column in columns:
                    insert_columns.append(column)
                    placeholders.append("NOW()")

            add_value("id", key_id)
            add_value("user_id", user_id)
            add_value("name", data.name)
            add_value("description", data.description or "")
            add_value("environment", data.environment)
            add_value("token_hash", token_hash)
            add_value("is_active", True)
            add_now("created_at")
            add_value("expires_at", expires_at)
            add_value("usage_count", 0)
            add_value("allowed_services", self._serialize_json_field(data.allowed_services or []))
            add_value("disallowed_services", self._serialize_json_field(data.disallowed_services or []))
            add_value("scopes", self._serialize_json_field(data.scopes or []))
            add_value("is_read_only", data.is_read_only)
            add_value("rate_limit", data.rate_limit)
            add_value("allowed_ips", self._serialize_json_field(data.allowed_ips or []))
            add_value("metadata", self._serialize_json_field(data.metadata or {}))

            cursor.execute(
                f"""
                INSERT INTO users_apikey ({', '.join(insert_columns)})
                VALUES ({', '.join(placeholders)})
                RETURNING id, created_at
                """,
                tuple(values),
            )
            row = cursor.fetchone()
            conn.commit()
            cursor.close()
            conn.close()
            
            return {
                "id": str(row[0]),
                "name": data.name,
                "environment": data.environment,
                "key_preview": f"xc_{'dev' if data.environment == 'DEVELOPMENT' else 'live'}_{'•' * 32}{token_hash[-4:]}",
                "is_active": True,
                "created_at": row[1],
                "expires_at": expires_at,
                "usage_count": 0,
                "token": raw_token,  # Only returned once
                "description": data.description,
                "allowed_services": data.allowed_services,
                "disallowed_services": data.disallowed_services,
                "scopes": data.scopes,
                "is_read_only": data.is_read_only,
                "rate_limit": data.rate_limit,
                "allowed_ips": data.allowed_ips,
                "metadata": data.metadata,
            }
        except Exception as e:
            logger.error(f"Error creating API key: {e}")
            raise

    def get_api_key_by_id(self, user_id: int, key_id: str) -> Optional[Dict[str, Any]]:
        try:
            columns = set(self._get_table_columns("users_apikey"))
            base_columns = [
                "id",
                "name",
                "environment",
                "token_hash",
                "is_active",
                "created_at",
                "expires_at",
                "usage_count",
            ]
            optional_columns = [
                "description",
                "allowed_services",
                "disallowed_services",
                "scopes",
                "is_read_only",
                "rate_limit",
                "last_ip",
                "last_used_at",
                "allowed_ips",
                "metadata",
            ]
            select_columns = [c for c in base_columns if c in columns]
            select_columns += [c for c in optional_columns if c in columns]

            conn = basic_postgres_connection()
            cursor = conn.cursor()
            cursor.execute(
                f"""
                SELECT {', '.join(select_columns)}
                FROM users_apikey
                WHERE id = %s AND user_id = %s
                LIMIT 1
                """,
                (key_id, user_id),
            )
            row = cursor.fetchone()
            cursor.close()
            conn.close()
            if not row:
                return None

            record = dict(zip(select_columns, row))
            token_hash = record.get("token_hash") or ""
            env = record.get("environment") or "DEVELOPMENT"
            key_preview = f"xc_{'dev' if env == 'DEVELOPMENT' else 'live'}_{'•' * 32}{token_hash[-4:] if token_hash else ''}"
            expires_at = self._normalize_datetime(record.get("expires_at"))
            now = datetime.now(timezone.utc)
            days_until_expiry = None
            is_expired = None
            if expires_at:
                delta = expires_at - now
                days_until_expiry = max(0, delta.days)
                is_expired = expires_at <= now

            return {
                "id": str(record.get("id")),
                "name": record.get("name"),
                "environment": env,
                "key_preview": key_preview,
                "is_active": record.get("is_active"),
                "created_at": record.get("created_at"),
                "expires_at": expires_at,
                "usage_count": record.get("usage_count") or 0,
                "description": record.get("description"),
                "allowed_services": self._parse_json_field(record.get("allowed_services")),
                "disallowed_services": self._parse_json_field(record.get("disallowed_services")),
                "scopes": self._parse_json_field(record.get("scopes")),
                "is_read_only": record.get("is_read_only"),
                "rate_limit": record.get("rate_limit"),
                "last_ip": record.get("last_ip"),
                "last_used_at": record.get("last_used_at"),
                "allowed_ips": self._parse_json_field(record.get("allowed_ips")),
                "metadata": self._parse_json_field(record.get("metadata")),
                "is_expired": is_expired,
                "days_until_expiry": days_until_expiry,
            }
        except Exception as e:
            logger.error(f"Error fetching API key {key_id}: {e}")
            return None

    def update_api_key(self, user_id: int, key_id: str, data: APIKeyUpdateRequest) -> Optional[Dict[str, Any]]:
        try:
            columns = set(self._get_table_columns("users_apikey"))
            update_fields: List[str] = []
            values: List[Any] = []

            def add_update(column: str, value: Any, serialize_json: bool = False) -> None:
                if column in columns:
                    update_fields.append(f"{column} = %s")
                    values.append(self._serialize_json_field(value) if serialize_json else value)

            payload = data.dict(exclude_unset=True)
            if "expires_in_days" in payload and payload.get("expires_in_days") is not None:
                payload["expires_at"] = datetime.now(timezone.utc) + timedelta(days=payload["expires_in_days"])

            if "name" in payload:
                add_update("name", payload["name"])
            if "description" in payload:
                add_update("description", payload["description"] or "")
            if "allowed_services" in payload:
                add_update("allowed_services", payload["allowed_services"] or [], serialize_json=True)
            if "disallowed_services" in payload:
                add_update("disallowed_services", payload["disallowed_services"] or [], serialize_json=True)
            if "scopes" in payload:
                add_update("scopes", payload["scopes"] or [], serialize_json=True)
            if "is_read_only" in payload:
                add_update("is_read_only", payload["is_read_only"])
            if "rate_limit" in payload:
                add_update("rate_limit", payload["rate_limit"])
            if "allowed_ips" in payload:
                add_update("allowed_ips", payload["allowed_ips"] or [], serialize_json=True)
            if "metadata" in payload:
                add_update("metadata", payload["metadata"] or {}, serialize_json=True)
            if "expires_at" in payload:
                add_update("expires_at", payload["expires_at"])
            if "is_active" in payload:
                add_update("is_active", payload["is_active"])

            if not update_fields:
                return self.get_api_key_by_id(user_id, key_id)

            values.extend([key_id, user_id])
            conn = basic_postgres_connection()
            cursor = conn.cursor()
            cursor.execute(
                f"""
                UPDATE users_apikey
                SET {', '.join(update_fields)}
                WHERE id = %s AND user_id = %s
                """,
                tuple(values),
            )
            conn.commit()
            cursor.close()
            conn.close()
            return self.get_api_key_by_id(user_id, key_id)
        except Exception as e:
            logger.error(f"Error updating API key {key_id}: {e}")
            return None

    def regenerate_api_key(self, user_id: int, key_id: str) -> Optional[Dict[str, Any]]:
        try:
            columns = set(self._get_table_columns("users_apikey"))
            conn = basic_postgres_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT environment FROM users_apikey WHERE id = %s AND user_id = %s",
                (key_id, user_id),
            )
            env_row = cursor.fetchone()
            cursor.close()
            conn.close()

            environment = env_row[0] if env_row else "DEVELOPMENT"
            raw_token = generate_api_key(environment)
            token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

            update_fields = ["token_hash = %s", "usage_count = 0"]
            values: List[Any] = [token_hash]
            if "last_used_at" in columns:
                update_fields.append("last_used_at = NULL")
            if "last_ip" in columns:
                update_fields.append("last_ip = NULL")

            values.extend([key_id, user_id])
            conn = basic_postgres_connection()
            cursor = conn.cursor()
            cursor.execute(
                f"""
                UPDATE users_apikey
                SET {', '.join(update_fields)}
                WHERE id = %s AND user_id = %s
                """,
                tuple(values),
            )
            conn.commit()
            cursor.close()
            conn.close()

            key = self.get_api_key_by_id(user_id, key_id)
            if key:
                key["token"] = raw_token
            return key
        except Exception as e:
            logger.error(f"Error regenerating API key {key_id}: {e}")
            return None

    def get_api_key_statistics(self, user_id: int) -> Dict[str, Any]:
        try:
            conn = basic_postgres_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT
                    COUNT(*) AS total_keys,
                    SUM(CASE WHEN is_active THEN 1 ELSE 0 END) AS active_keys,
                    SUM(CASE WHEN NOT is_active THEN 1 ELSE 0 END) AS inactive_keys,
                    SUM(CASE WHEN expires_at IS NOT NULL AND expires_at <= NOW() THEN 1 ELSE 0 END) AS expired_keys,
                    SUM(COALESCE(usage_count, 0)) AS total_usage
                FROM users_apikey
                WHERE user_id = %s
                """,
                (user_id,),
            )
            row = cursor.fetchone()

            cursor.execute(
                """
                SELECT environment, COUNT(*) FROM users_apikey
                WHERE user_id = %s
                GROUP BY environment
                """,
                (user_id,),
            )
            env_rows = cursor.fetchall()
            cursor.close()
            conn.close()

            env_counts = {row[0]: row[1] for row in env_rows}
            return {
                "total_keys": row[0] or 0,
                "active_keys": row[1] or 0,
                "inactive_keys": row[2] or 0,
                "expired_keys": row[3] or 0,
                "total_usage": row[4] or 0,
                "keys_by_environment": {
                    "PRODUCTION": env_counts.get("PRODUCTION", 0),
                    "DEVELOPMENT": env_counts.get("DEVELOPMENT", 0),
                },
            }
        except Exception as e:
            logger.error(f"Error fetching API key statistics: {e}")
            return {
                "total_keys": 0,
                "active_keys": 0,
                "inactive_keys": 0,
                "expired_keys": 0,
                "total_usage": 0,
                "keys_by_environment": {"PRODUCTION": 0, "DEVELOPMENT": 0},
            }

    def deactivate_api_key(self, user_id: int, key_id: str) -> bool:
        """Deactivate an API key."""
        try:
            conn = basic_postgres_connection()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE users_apikey SET is_active = FALSE
                WHERE id = %s AND user_id = %s
            """, (key_id, user_id))
            affected = cursor.rowcount
            conn.commit()
            cursor.close()
            conn.close()
            return affected > 0
        except Exception as e:
            logger.error(f"Error deactivating API key: {e}")
            return False


# Global database manager instance
auth_db = AuthDatabaseManager()


# ============================================================================
# SECURITY DEPENDENCIES
# ============================================================================

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(http_bearer)
) -> Dict[str, Any]:
    """Get current authenticated user from JWT token."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    payload = decode_token(credentials.credentials)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    if payload.get("type") != TokenType.ACCESS.value:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    user = auth_db.get_user_by_id(payload["user_id"])
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    if not user.get("is_active"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled"
        )
    
    return user


async def get_current_active_user(
    user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get current active user."""
    if not user.get("is_active"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )
    return user


async def get_current_superuser(
    user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get current superuser."""
    if not user.get("is_superuser"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    return user


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(http_bearer)
) -> Optional[Dict[str, Any]]:
    """Get current user if authenticated, None otherwise."""
    if not credentials:
        return None
    
    payload = decode_token(credentials.credentials)
    if not payload:
        return None
    
    return auth_db.get_user_by_id(payload.get("user_id"))


# ============================================================================
# FASTAPI ROUTER & ROUTES
# ============================================================================

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


@router.get("/health")
async def auth_health_check():
    """Auth service health check endpoint."""
    return {
        "status": "ok",
        "service": "auth",
        "timestamp": datetime.utcnow().isoformat(),
        "message": "Authentication service is healthy"
    }


@router.post("/register", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def register(data: UserRegisterRequest, request: Request):
    """
    Register a new user.
    
    Creates user account with:
    - Organization (auto-created)
    - Workspace (auto-created)
    - JWT tokens returned
    """
    path = "/api/v1/auth/register"
    cid = set_correlation_id(request.headers.get("X-Correlation-ID") if request else None)
    log_api_request(
        logger, "POST", path,
        body=(data.model_dump() if hasattr(data, "model_dump") else data.dict()) if (hasattr(data, "model_dump") or hasattr(data, "dict")) else None,
        headers=dict(request.headers) if request else None,
        correlation_id=cid,
    )
    with RequestTimer() as timer:
        try:
            user = auth_db.create_user(data)
            tokens = create_tokens(user["id"], user["email"])
            log_api_response(logger, "POST", path, 201, duration_ms=timer.duration_ms)
            return {
                "user": user,
                "access": tokens.access,
                "refresh": tokens.refresh
            }
        except ValueError as e:
            log_api_response(logger, "POST", path, 400, body={"detail": str(e)}, duration_ms=timer.duration_ms)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
        except Exception as e:
            logger.error(f"Registration error: {e}", exc_info=True)
            log_api_response(logger, "POST", path, 500, body={"detail": str(e)}, duration_ms=timer.duration_ms)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Registration failed: {str(e)}"
            )


@router.post("/login", response_model=Dict[str, Any])
async def login(data: UserLoginRequest, request: Request):
    """
    User login with email/username and password.

    Accepts either ``email`` or ``username`` to identify the account.
    Returns access and refresh tokens.
    """
    path = "/api/v1/auth/login"
    identifier = data.email or data.username
    cid = set_correlation_id(request.headers.get("X-Correlation-ID") if request else None)
    log_api_request(
        logger, "POST", path,
        body={"identifier": identifier},
        headers=dict(request.headers) if request else None,
        correlation_id=cid,
    )
    with RequestTimer() as timer:
        # Look up by email first, fall back to username
        user = None
        if data.email:
            user = auth_db.get_user_by_email(data.email)
        if user is None and data.username:
            user = auth_db.get_user_by_username(data.username)
        if not user:
            log_api_response(logger, "POST", path, 401, duration_ms=timer.duration_ms)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email/username or password"
            )

        if not verify_password(data.password, user["password"]):
            log_api_response(logger, "POST", path, 401, duration_ms=timer.duration_ms)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )

        if not user.get("is_active"):
            log_api_response(logger, "POST", path, 403, duration_ms=timer.duration_ms)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is disabled"
            )

        auth_db.update_last_login(user["id"])
        tokens = create_tokens(user["id"], user["email"])
        org = auth_db.get_organization(str(user["organization_id"])) if user.get("organization_id") else None
        workspace = auth_db.get_workspace(user["id"])
        subscription = auth_db.get_user_subscription(user["id"])

        user_response = {
            "id": user["id"],
            "email": user["email"],
            "username": user["username"],
            "first_name": user["first_name"],
            "last_name": user["last_name"],
            "is_verified": user["is_verified"],
            "is_active": user["is_active"],
            "date_joined": user["date_joined"],
            "last_login": user["last_login"],
            "organization": org,
            "workspace": workspace,
            "subscription": subscription,
            "connected_providers": {
                "google": bool(user.get("social_google")),
                "github": bool(user.get("social_github")),
                "microsoft": bool(user.get("social_microsoft"))
            }
        }

        client_host = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "unknown")
        logger.info(
            "auth.login success user_id=%s email=%s ip=%s ua=%s",
            user["id"],
            user["email"],
            client_host,
            user_agent,
        )
        log_api_response(logger, "POST", path, 200, duration_ms=timer.duration_ms)
        return {
            "user": user_response,
            "access": tokens.access,
            "refresh": tokens.refresh
        }


@router.post("/token/refresh", response_model=TokenResponse)
async def refresh_token(data: TokenRefreshRequest):
    """
    Refresh access token using refresh token.
    """
    payload = decode_token(data.refresh)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token"
        )
    
    if payload.get("type") != TokenType.REFRESH.value:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type"
        )
    
    user = auth_db.get_user_by_id(payload["user_id"])
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    
    # Create new tokens
    return create_tokens(user["id"], user["email"])


@router.post("/logout")
async def logout_user(data: LogoutRequest, request: Request) -> Dict[str, Any]:
    refresh_token = data.refresh
    client_host = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")
    payload = None
    token_status = "invalid"

    try:
        payload = jwt.decode(
            refresh_token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
            options={"verify_exp": False},
        )
    except jwt.InvalidTokenError:
        payload = None

    if not payload:
        logger.warning(
            "auth.logout invalid_token ip=%s ua=%s",
            client_host,
            user_agent,
        )
        return {"status": "invalid_token"}

    if payload.get("type") != TokenType.REFRESH.value:
        logger.warning(
            "auth.logout invalid_type user_id=%s email=%s type=%s ip=%s ua=%s",
            payload.get("user_id"),
            payload.get("email"),
            payload.get("type"),
            client_host,
            user_agent,
        )
        return {"status": "invalid_token_type"}

    jti = payload.get("jti")
    if not jti:
        logger.warning(
            "auth.logout missing_jti user_id=%s email=%s ip=%s ua=%s",
            payload.get("user_id"),
            payload.get("email"),
            client_host,
            user_agent,
        )
        return {"status": "missing_jti"}

    if jti in _token_blacklist:
        token_status = "already_blacklisted"
    else:
        blacklisted = blacklist_refresh_token(refresh_token)
        token_status = "blacklisted" if blacklisted else "not_blacklisted"

    logger.info(
        "auth.logout %s user_id=%s email=%s jti=%s ip=%s ua=%s",
        token_status,
        payload.get("user_id"),
        payload.get("email"),
        jti,
        client_host,
        user_agent,
    )
    return {"status": token_status}


@router.post("/google", response_model=TokenResponse)
async def google_auth_legacy(
    data: GoogleTokenRequest,
    request: Request,
):
    """
    Legacy Google auth endpoint for compatibility with Django /auth/google/.
    """
    try:
        from app.auth.oauth import GoogleTokenRequest as OAuthGoogleTokenRequest
        from app.auth.oauth import google_auth as oauth_google_auth

        token_request = OAuthGoogleTokenRequest(credential=data.credential)
        return await oauth_google_auth(token_request, request)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Legacy Google auth failed: {e}")
        raise HTTPException(status_code=500, detail="Google authentication failed")


@router.get("/profile", response_model=UserResponse)
async def get_profile(request: Request, user: Dict[str, Any] = Depends(get_current_active_user)):
    """
    Get current user's profile.
    """
    path = "/api/v1/auth/profile"
    cid = set_correlation_id(request.headers.get("X-Correlation-ID") if request else None)
    log_api_request(logger, "GET", path, headers=dict(request.headers) if request else None, correlation_id=cid)
    with RequestTimer() as timer:
        org = auth_db.get_organization(str(user["organization_id"])) if user.get("organization_id") else None
        workspace = auth_db.get_workspace(user["id"])
        subscription = auth_db.get_user_subscription(user["id"])
        log_api_response(logger, "GET", path, 200, duration_ms=timer.duration_ms)
        return UserResponse(
            id=user["id"],
            email=user["email"],
            username=user["username"],
            first_name=user.get("first_name"),
            last_name=user.get("last_name"),
            phone=user.get("phone"),
            is_verified=user.get("is_verified", False),
            is_active=user.get("is_active", True),
            is_staff=user.get("is_staff", False),
            date_joined=user.get("date_joined"),
            last_login=user.get("last_login"),
            organization=org,
            workspace=workspace,
            subscription=subscription,
            connected_providers={
                "google": bool(user.get("social_google")),
                "github": bool(user.get("social_github")),
                "microsoft": bool(user.get("social_microsoft"))
            }
        )


@router.put("/profile")
async def update_profile(
    data: UserProfileUpdateRequest,
    user: Dict[str, Any] = Depends(get_current_active_user)
):
    """
    Update current user's profile.
    """
    update_data = {
        k: v for k, v in data.dict().items() if v is not None
    }
    
    if update_data:
        success = auth_db.update_user(user["id"], update_data)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update profile"
            )
    
    # Return updated user
    updated_user = auth_db.get_user_by_id(user["id"])
    return {"message": "Profile updated successfully", "user": updated_user}


@router.post("/change-password")
async def change_password(
    data: PasswordChangeRequest,
    user: Dict[str, Any] = Depends(get_current_active_user)
):
    """
    Change user's password.
    """
    # Verify current password
    if not verify_password(data.current_password, user["password"]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )
    
    # Hash new password and update
    new_hash = hash_password(data.new_password)
    success = auth_db.update_user(user["id"], {"password": new_hash})
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to change password"
        )
    
    return {"message": "Password changed successfully"}


@router.post("/forgot-password")
async def forgot_password(data: ForgotPasswordRequest):
    """
    Request password reset code.
    
    Generates a 6-digit verification code.
    In production, this would send an email.
    """
    user = auth_db.get_user_by_email(data.email)
    if not user:
        # Don't reveal if email exists
        return {"message": "If this email exists, a verification code has been sent"}
    
    # Generate verification code
    code = generate_verification_code()
    auth_db.update_user(user["id"], {"verification_code": code})
    
    # In production: send email with code
    logger.info(f"Password reset code for {data.email}: {code}")
    
    return {
        "message": "Verification code generated",
        "verification_code": code  # Remove in production!
    }


@router.post("/reset-password")
async def reset_password(data: ResetPasswordRequest):
    """
    Reset password with verification code.
    """
    user = auth_db.get_user_by_email(data.email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Verify code
    if not user.get("verification_code") or str(user["verification_code"]) != data.verification_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification code"
        )
    
    # Hash new password and update
    new_hash = hash_password(data.new_password)
    success = auth_db.update_user(user["id"], {
        "password": new_hash,
        "verification_code": None
    })
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reset password"
        )
    
    return {"message": "Password reset successfully"}


@router.put("/organization/update")
async def update_organization(
    data: OrganizationUpdateRequest,
    user: Dict[str, Any] = Depends(get_current_active_user)
):
    """
    Update user's organization.
    """
    if not user.get("organization_id"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No organization associated with user"
        )
    
    update_data = {k: v for k, v in data.dict().items() if v is not None}
    if update_data:
        success = auth_db.update_organization(str(user["organization_id"]), update_data)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update organization"
            )
    
    org = auth_db.get_organization(str(user["organization_id"]))
    return {"message": "Organization updated", "organization": org}


@router.post("/complete-profile")
async def complete_profile(
    data: CompleteProfileRequest,
    request: Request,
    user: Dict[str, Any] = Depends(get_current_active_user),
):
    """
    Complete user profile after social auth onboarding.
    Updates user fields, organization name, and stores onboarding metadata.
    """
    path = "/api/v1/auth/complete-profile"
    cid = set_correlation_id(request.headers.get("X-Correlation-ID") if request else None)
    log_api_request(
        logger, "POST", path,
        body=(data.model_dump() if hasattr(data, "model_dump") else data.dict()) if (hasattr(data, "model_dump") or hasattr(data, "dict")) else None,
        headers=dict(request.headers) if request else None,
        correlation_id=cid,
    )
    with RequestTimer() as timer:
        def _clean(value: Optional[str]) -> Optional[str]:
            if value is None:
                return None
            stripped = value.strip()
            return stripped if stripped else None

        update_data: Dict[str, Any] = {}

        if _clean(data.username):
            update_data["username"] = _clean(data.username)
        if _clean(data.password):
            update_data["password"] = hash_password(_clean(data.password))
        if _clean(data.phone):
            update_data["phone"] = _clean(data.phone)
        if _clean(data.country):
            update_data["country"] = _clean(data.country)
        if _clean(data.location):
            update_data["deployed_where"] = _clean(data.location)
        if _clean(data.first_name):
            update_data["first_name"] = _clean(data.first_name)
        if _clean(data.last_name):
            update_data["last_name"] = _clean(data.last_name)
        if _clean(data.company_name):
            update_data["company_name"] = _clean(data.company_name)
        if _clean(data.occupation):
            update_data["occupation"] = _clean(data.occupation)
        if _clean(data.purpose_of_account):
            update_data["purpose_of_account"] = _clean(data.purpose_of_account)
        if _clean(data.address_line1):
            update_data["address_line1"] = _clean(data.address_line1)
        if _clean(data.address_line2):
            update_data["address_line2"] = _clean(data.address_line2)
        if _clean(data.city):
            update_data["city"] = _clean(data.city)
        if _clean(data.state_province):
            update_data["state_province"] = _clean(data.state_province)
        if _clean(data.postal_code):
            update_data["postal_code"] = _clean(data.postal_code)

        onboarding_meta = {
            "description": _clean(data.description),
            "platform_usage": _clean(data.platform_usage),
            "location": _clean(data.location),
            "company_name": _clean(data.company_name),
            "occupation": _clean(data.occupation),
            "purpose_of_account": _clean(data.purpose_of_account),
        }
        if any(onboarding_meta.values()):
            update_data["extended_json_field_1"] = json.dumps(onboarding_meta)

        if update_data:
            success = auth_db.update_user(user["id"], update_data)
            if not success:
                log_api_response(logger, "POST", path, 500, duration_ms=timer.duration_ms)
                raise HTTPException(status_code=500, detail="Failed to update user profile")

        if data.organization_name and user.get("organization_id"):
            org_success = auth_db.update_organization(
                str(user["organization_id"]),
                {"name": data.organization_name},
            )
            if not org_success:
                log_api_response(logger, "POST", path, 500, duration_ms=timer.duration_ms)
                raise HTTPException(status_code=500, detail="Failed to update organization")

        refreshed = auth_db.get_user_by_id(user["id"])
        org = auth_db.get_organization(str(refreshed["organization_id"])) if refreshed and refreshed.get("organization_id") else None
        workspace = auth_db.get_workspace(user["id"])
        subscription = auth_db.get_user_subscription(user["id"])

        user_payload = UserResponse(
            id=refreshed["id"],
            email=refreshed["email"],
            username=refreshed["username"],
            first_name=refreshed.get("first_name"),
            last_name=refreshed.get("last_name"),
            phone=refreshed.get("phone"),
            is_verified=refreshed.get("is_verified", False),
            is_active=refreshed.get("is_active", True),
            is_staff=refreshed.get("is_staff", False),
            date_joined=refreshed.get("date_joined"),
            last_login=refreshed.get("last_login"),
            organization=org,
            workspace=workspace,
            subscription=subscription,
            connected_providers={
                "google": bool(refreshed.get("social_google")),
                "github": bool(refreshed.get("social_github")),
                "microsoft": bool(refreshed.get("social_microsoft")),
            },
        )
        log_api_response(logger, "POST", path, 200, duration_ms=timer.duration_ms)
        return {"message": "Profile completed", "user": user_payload}




@router.get("/developer/keys", response_model=List[APIKeyResponse])
async def list_api_keys(user: Dict[str, Any] = Depends(get_current_active_user)):
    """
    List user's API keys.
    """
    keys = auth_db.get_api_keys(user["id"])
    return keys


@router.get("/developer/keys/statistics")
async def api_key_statistics(
    user: Dict[str, Any] = Depends(get_current_active_user),
):
    return auth_db.get_api_key_statistics(user["id"])


@router.get("/developer/keys/{key_id}", response_model=APIKeyResponse)
async def get_api_key(
    key_id: str,
    user: Dict[str, Any] = Depends(get_current_active_user),
):
    key = auth_db.get_api_key_by_id(user["id"], key_id)
    if not key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )
    return key


@router.post("/developer/keys", response_model=APIKeyResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    data: APIKeyCreateRequest,
    user: Dict[str, Any] = Depends(get_current_active_user)
):
    """
    Create a new API key.
    
    WARNING: The token is only returned once upon creation!
    """
    try:
        key = auth_db.create_api_key(user["id"], data)
        return APIKeyResponse(**key)
    except Exception as e:
        logger.error(f"Error creating API key: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create API key"
        )


@router.put("/developer/keys/{key_id}", response_model=APIKeyResponse)
async def update_api_key(
    key_id: str,
    data: APIKeyUpdateRequest,
    user: Dict[str, Any] = Depends(get_current_active_user),
):
    updated = auth_db.update_api_key(user["id"], key_id, data)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )
    return updated


@router.patch("/developer/keys/{key_id}", response_model=APIKeyResponse)
async def partial_update_api_key(
    key_id: str,
    data: APIKeyUpdateRequest,
    user: Dict[str, Any] = Depends(get_current_active_user),
):
    updated = auth_db.update_api_key(user["id"], key_id, data)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )
    return updated


@router.post("/developer/keys/{key_id}/regenerate", response_model=APIKeyResponse)
async def regenerate_api_key(
    key_id: str,
    user: Dict[str, Any] = Depends(get_current_active_user),
):
    regenerated = auth_db.regenerate_api_key(user["id"], key_id)
    if not regenerated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )
    return regenerated


@router.delete("/developer/keys/{key_id}")
async def delete_api_key(
    key_id: str,
    user: Dict[str, Any] = Depends(get_current_active_user)
):
    """
    Deactivate an API key (soft delete).
    """
    success = auth_db.deactivate_api_key(user["id"], key_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )
    return {"message": "API key deactivated successfully", "id": key_id}




import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def generate_admin_token() -> str:
    return secrets.token_urlsafe(32)


def hash_admin_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_access_token(subject: str | int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    to_encode = {"sub": str(subject), "exp": expire}
    return jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> int | None:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        sub = payload.get("sub")
        if sub is None:
            return None
        return int(sub)
    except JWTError:
        return None


def create_admin_console_token() -> str:
    """与玩家 JWT 区分：payload 含 typ=admin_console，sub 固定为 admin_console。"""
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    to_encode = {"sub": "admin_console", "typ": "admin_console", "exp": expire}
    return jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_admin_console_token(token: str) -> bool:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        return payload.get("typ") == "admin_console" and payload.get("sub") == "admin_console"
    except JWTError:
        return False

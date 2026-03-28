from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.database import get_db
from app.models import User

security = HTTPBearer(auto_error=False)


def get_current_user(
    db: Annotated[Session, Depends(get_db)],
    cred: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
) -> User:
    if cred is None or cred.scheme.lower() != "bearer":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "未登录")
    uid = decode_token(cred.credentials)
    if uid is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "无效令牌")
    user = db.get(User, uid)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "用户不存在")
    return user

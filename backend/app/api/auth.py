from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password, verify_password
from app.database import get_db
from app.models import User
from app.api.deps import get_current_user
from app.schemas.auth import LoginIn, RegisterIn, TokenOut, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenOut)
def register(body: RegisterIn, db: Annotated[Session, Depends(get_db)]) -> TokenOut:
    if db.query(User).filter(User.email == body.email.lower()).first():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "邮箱已注册")
    user = User(
        email=body.email.lower(),
        nickname=body.nickname,
        password_hash=hash_password(body.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return TokenOut(access_token=create_access_token(user.id))


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, db: Annotated[Session, Depends(get_db)]) -> TokenOut:
    user = db.query(User).filter(User.email == body.email.lower()).first()
    if user is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "账号不存在")
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "密码错误")
    return TokenOut(access_token=create_access_token(user.id))


@router.get("/me", response_model=UserOut)
def me(user: Annotated[User, Depends(get_current_user)]) -> UserOut:
    return UserOut.model_validate(user)

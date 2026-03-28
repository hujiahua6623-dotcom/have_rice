from pydantic import BaseModel, EmailStr, Field


class RegisterIn(BaseModel):
    email: EmailStr
    nickname: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=6, max_length=128)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: int
    email: str
    nickname: str

    model_config = {"from_attributes": True}

from typing import Self

from ninja import Field, Schema
from pydantic import EmailStr, model_validator


class SignupIn(Schema):
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=128)
    password_confirm: str = Field(min_length=8, max_length=128)

    @model_validator(mode="after")
    def validate_password(self) -> Self:
        if self.password != self.password_confirm:
            raise ValueError("비밀번호가 일치하지 않습니다.")
        return self


class LoginIn(Schema):
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=128)


class RefreshIn(Schema):
    refresh: str = Field(min_length=1, max_length=4096)


class LogoutIn(Schema):
    refresh: str = Field(min_length=1, max_length=4096)


class UserOut(Schema):
    id: int
    email: EmailStr


class TokenOut(Schema):
    access: str
    refresh: str
    token_type: str = "Bearer"

import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class _EmailNormalizeMixin(BaseModel):
    @field_validator("email", mode="before", check_fields=False)
    @classmethod
    def normalize_email(cls, v: object) -> object:
        if isinstance(v, str):
            return v.lower()
        return v


class RegisterRequest(_EmailNormalizeMixin):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str | None = Field(default=None, max_length=200)


class LoginRequest(_EmailNormalizeMixin):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    name: str | None = None

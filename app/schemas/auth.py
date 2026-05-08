import uuid
from pydantic import BaseModel, EmailStr, Field

class RegisterRequest(BaseModel):
    email: EmailStr
    display_name: str = Field(min_length=2,max_length=100)
    password: str = Field(min_length=8,max_length=72)

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class RefreshRequest(BaseModel):
    refresh_token: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str
    is_active: bool

    # This tells Pydantic to read from SQLAlchemy model attributes
    # not just plain dicts
    model_config = {"from_attributes": True}
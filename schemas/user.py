from pydantic import BaseModel, EmailStr, HttpUrl
from typing import Optional, Literal, List

class UserCreate(BaseModel):
    name: str
    email: EmailStr
    phone_number: str
    college_or_university: str
    course: str
    gender: Literal["M", "F", "O"]
    github: HttpUrl

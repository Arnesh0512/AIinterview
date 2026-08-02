from pydantic import BaseModel, EmailStr, HttpUrl
from typing import List, Literal
from datetime import date, datetime

from constants.role import RoleEnum
from constants.skill import SkillEnum


class Education(BaseModel):
    institution_name: str
    degree: str
    field_of_study: str
    grade_cgpa: float
    start_date: date
    end_date: date
    is_current: bool


class UserCreate(BaseModel):

    # Basic Info
    full_name: str
    email: EmailStr
    phone_number: str
    gender: Literal["M", "F", "O"]
    date_of_birth: date

    # Professional Info
    roles: List[RoleEnum]
    skills: List[SkillEnum]

    # Education
    education: List[Education]

    # Social
    linkedin_url: HttpUrl
    github_url: HttpUrl


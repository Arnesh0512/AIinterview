from pydantic import BaseModel
from typing import List
from datetime import datetime

from constants.role import RoleEnum
from constants.skill import SkillEnum
from constants.company import CompanyEnum


class RoundTime(BaseModel):
    start: datetime
    end: datetime
    duration: int
    result: datetime


class ContestCreate(BaseModel):

    company : CompanyEnum
    role: RoleEnum
    skills: List[SkillEnum]

    last_date_to_register: datetime
    contest_start: datetime
    contest_end: datetime

    resume_round: RoundTime
    coding_round: RoundTime
    concept_round: RoundTime
    hr_round: RoundTime

    leaderboard_declare_time: datetime

    resume_questions_count: int
    coding_questions_count: int
    concept_questions_count: int
    hr_questions_count: int

    candidate_capacity: int

    selected_resume: int
    selected_coding: int
    selected_concept: int
    selected_hr: int
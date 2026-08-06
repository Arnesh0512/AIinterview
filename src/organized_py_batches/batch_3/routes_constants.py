from fastapi import APIRouter
from constants.company import CompanyEnum
from constants.topic import TopicEnum
from constants.difficulty import DifficultyEnum
from constants.language import LanguageEnum
from constants.role import RoleEnum
from constants.skill import SkillEnum
from constants.tag import TagEnum


router = APIRouter(
    prefix="/constants",
    tags=["Constants"]
)


def enum_to_list(enum_class):
    return [item.value for item in enum_class]


@router.get("/companies")
def get_companies():
    return {
        "success": True,
        "companies": enum_to_list(CompanyEnum)
    }


@router.get("/topics")
def get_topics():
    return {
        "success": True,
        "topics": enum_to_list(TopicEnum)
    }


@router.get("/difficulties")
def get_difficulties():
    return {
        "success": True,
        "difficulties": enum_to_list(DifficultyEnum)
    }


@router.get("/languages")
def get_languages():
    return {
        "success": True,
        "languages": enum_to_list(LanguageEnum)
    }


@router.get("/roles")
def get_roles():
    return {
        "success": True,
        "roles": enum_to_list(RoleEnum)
    }


@router.get("/skills")
def get_skills():
    return {
        "success": True,
        "skills": enum_to_list(SkillEnum)
    }


@router.get("/tags")
def get_tags():
    return {
        "success": True,
        "tags": enum_to_list(TagEnum)
    }


@router.get("/all")
def get_all_constants():
    return {
        "success": True,
        "companies": enum_to_list(CompanyEnum),
        "topics": enum_to_list(TopicEnum),
        "difficulties": enum_to_list(DifficultyEnum),
        "languages": enum_to_list(LanguageEnum),
        "roles": enum_to_list(RoleEnum),
        "skills": enum_to_list(SkillEnum),
        "tags": enum_to_list(TagEnum),
    }
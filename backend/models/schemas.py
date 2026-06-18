"""
Pydantic models for Career Guardian AI.
All models include safe defaults so the frontend never crashes on partial data.
"""

from typing import Optional
from pydantic import BaseModel, Field


# ── Resume Intelligence ───────────────────────────────────────────────────────

class ResumeIntelligence(BaseModel):
    name: str = "Not detected"
    email: str = "Not detected"
    phone: str = "Not detected"
    education: list[str] = []
    skills: list[str] = []
    projects: list[str] = []
    experience: list[str] = []
    certifications: list[str] = []
    achievements: list[str] = []
    summary: str = ""


# ── Career Direction ──────────────────────────────────────────────────────────

class CareerDirection(BaseModel):
    primary: str = "Software Engineer"
    secondary: str = "Not detected"
    confidence: int = Field(default=50, ge=0, le=100)
    reasoning: str = "Insufficient data for confident direction detection."


# ── Focus Score ───────────────────────────────────────────────────────────────

class FocusScore(BaseModel):
    score: int = Field(default=50, ge=0, le=100)
    category: str = "Mixed"
    skill_alignment: int = Field(default=50, ge=0, le=100)
    project_alignment: int = Field(default=50, ge=0, le=100)
    certification_alignment: int = Field(default=50, ge=0, le=100)
    experience_alignment: int = Field(default=50, ge=0, le=100)
    resume_consistency: int = Field(default=50, ge=0, le=100)
    strengths: list[str] = []
    weaknesses: list[str] = []
    recommendations: list[str] = []
    reasoning: str = ""


# ── Resume Rating ─────────────────────────────────────────────────────────────

class ResumeSubscores(BaseModel):
    skills: int = Field(default=50, ge=0, le=100)
    projects: int = Field(default=50, ge=0, le=100)
    certifications: int = Field(default=50, ge=0, le=100)
    experience: int = Field(default=50, ge=0, le=100)
    presentation: int = Field(default=50, ge=0, le=100)
    focus: int = Field(default=50, ge=0, le=100)


class ResumeRatingExplanations(BaseModel):
    skills: str = ""
    projects: str = ""
    certifications: str = ""
    experience: str = ""
    presentation: str = ""
    focus: str = ""


class ResumeRating(BaseModel):
    overall: int = Field(default=50, ge=0, le=100)
    subscores: ResumeSubscores = Field(default_factory=ResumeSubscores)
    explanations: ResumeRatingExplanations = Field(default_factory=ResumeRatingExplanations)


# ── Skill Gap Analysis ────────────────────────────────────────────────────────

class MissingSkill(BaseModel):
    skill: str = ""
    why_it_matters: str = ""
    priority: str = "Medium"


class SkillGap(BaseModel):
    role: str = ""
    missing_skills: list[MissingSkill] = []


# ── Growth Roadmap ────────────────────────────────────────────────────────────

class RoadmapStep(BaseModel):
    action: str = ""
    details: str = ""
    outcome: str = ""


class GrowthRoadmap(BaseModel):
    day_30: list[RoadmapStep] = []
    day_60: list[RoadmapStep] = []
    day_90: list[RoadmapStep] = []


# ── Certification Advisor ─────────────────────────────────────────────────────

class Certification(BaseModel):
    name: str = ""
    level: str = "Beginner"
    why_recommended: str = ""
    expected_benefit: str = ""
    provider: str = ""


# ── Project Recommendations ───────────────────────────────────────────────────

class ProjectRecommendation(BaseModel):
    name: str = ""
    difficulty: str = "Intermediate"
    skills_learned: list[str] = []
    why_it_helps: str = ""
    description: str = ""


# ── Opportunity Guide ─────────────────────────────────────────────────────────

class Opportunity(BaseModel):
    platform: str = ""
    target_audience: str = ""
    why_useful: str = ""
    url: str = ""


# ── Master Response ───────────────────────────────────────────────────────────

class AnalysisResponse(BaseModel):
    resume_intelligence: ResumeIntelligence = Field(default_factory=ResumeIntelligence)
    career_direction: CareerDirection = Field(default_factory=CareerDirection)
    focus_score: FocusScore = Field(default_factory=FocusScore)
    resume_rating: ResumeRating = Field(default_factory=ResumeRating)
    skill_gap: SkillGap = Field(default_factory=SkillGap)
    growth_roadmap: GrowthRoadmap = Field(default_factory=GrowthRoadmap)
    certifications: list[Certification] = []
    projects: list[ProjectRecommendation] = []
    opportunities: list[Opportunity] = []


# ── Error Response ────────────────────────────────────────────────────────────

class ErrorResponse(BaseModel):
    error: str
    message: str


def get_focus_category(score: int) -> str:
    if score >= 90:
        return "Highly Focused"
    elif score >= 70:
        return "Mostly Focused"
    elif score >= 50:
        return "Mixed"
    else:
        return "Unfocused"

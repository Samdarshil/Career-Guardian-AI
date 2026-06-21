"""
Pydantic models for Career Guardian AI.
All models include safe defaults so the frontend never crashes on partial data.
Expanded to support richer multi-agent outputs.
"""

from pydantic import BaseModel, Field


# ── Resume Intelligence ───────────────────────────────────────────────────────

class ResumeIntelligence(BaseModel):
    name: str = "Not detected"
    email: str = "Not detected"
    phone: str = "Not detected"
    location: str = "Not detected"
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
    secondary: str = "Not strongly evident"
    confidence: int = Field(default=50, ge=0, le=100)
    reasoning: str = ""


# ── Focus Score ───────────────────────────────────────────────────────────────

class FocusScore(BaseModel):
    score: int = Field(default=50, ge=0, le=100)
    category: str = "Mixed"
    skill_alignment: int = Field(default=50, ge=0, le=100)
    project_alignment: int = Field(default=50, ge=0, le=100)
    certification_alignment: int = Field(default=75, ge=0, le=100)
    experience_alignment: int = Field(default=60, ge=0, le=100)
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
    learning_resource: str = ""


class PartialSkill(BaseModel):
    skill: str = ""
    current_level: str = ""
    needed_level: str = ""


class SkillGap(BaseModel):
    role: str = ""
    current_skill_assessment: str = ""
    missing_skills: list[MissingSkill] = []
    partially_present_skills: list[PartialSkill] = []


# ── Growth Roadmap ────────────────────────────────────────────────────────────

class RoadmapStep(BaseModel):
    action: str = ""
    details: str = ""
    outcome: str = ""
    time_commitment: str = ""


class GrowthRoadmap(BaseModel):
    day_30: list[RoadmapStep] = []
    day_60: list[RoadmapStep] = []
    day_90: list[RoadmapStep] = []
    milestone_summary: str = ""


# ── Certification Advisor ─────────────────────────────────────────────────────

class Certification(BaseModel):
    name: str = ""
    provider: str = ""
    level: str = "Beginner"
    why_recommended: str = ""
    expected_benefit: str = ""
    approximate_cost: str = ""
    url: str = ""


# ── Project Recommendations ───────────────────────────────────────────────────

class ProjectRecommendation(BaseModel):
    name: str = ""
    difficulty: str = "Intermediate"
    description: str = ""
    tech_stack: list[str] = []
    skills_learned: list[str] = []
    why_it_helps: str = ""
    github_starter: str = ""


# ── Opportunity Guide ─────────────────────────────────────────────────────────

class Opportunity(BaseModel):
    platform: str = ""
    type: str = ""
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
    agent_timings: dict = Field(default_factory=dict)


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

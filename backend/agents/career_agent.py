"""
CareerAgent — determines career direction and computes the Focus Score.

Receives ResumeAgent's structured output as context. Runs second in the pipeline.
Its output (primary role, focus score) is consumed by SkillGapAgent and RoadmapAgent.

ADK-compatible: name, description, run() via BaseAgent.
"""

from backend.agents.base_agent import BaseAgent, AgentContext
from backend.utils.helpers import sanitise_text
import json


class CareerAgent(BaseAgent):
    name = "career_agent"
    description = (
        "Determines the candidate's primary and secondary career direction with "
        "confidence scoring, and computes the Resume Focus Score using a weighted "
        "formula across five dimensions."
    )

    def _build_prompt(self, context: AgentContext) -> str:
        resume_summary = sanitise_text(context.resume_text, max_chars=6000)
        extracted = context.results.get("resume_agent", {})

        skills = extracted.get("skills", [])
        projects = extracted.get("projects", [])
        experience = extracted.get("experience", [])
        certifications = extracted.get("certifications", [])

        context_block = f"""
Extracted Resume Data (from ResumeAgent):
Skills: {json.dumps(skills)}
Projects: {json.dumps(projects)}
Experience: {json.dumps(experience)}
Certifications: {json.dumps(certifications)}

Raw Resume Text (for additional context):
{resume_summary}
"""

        return f"""You are a senior career analyst. Analyse this candidate's resume data and determine:
1. Their most suitable career direction
2. A secondary direction if evident
3. A Focus Score measuring how well their resume targets a single career path

{context_block}

Return ONLY a JSON object with this exact schema:

{{
  "career_direction": {{
    "primary": "specific job title (e.g. 'AIML Engineer', 'Full Stack Developer', 'Data Scientist', 'Cloud Engineer', 'DevOps Engineer', 'Cybersecurity Analyst', 'Android Developer', 'Frontend Developer', 'Backend Developer', 'Data Analyst')",
    "secondary": "second most evident role, or 'Not strongly evident' if resume is focused",
    "confidence": integer 0-100 reflecting how clearly the resume signals this direction,
    "reasoning": "2-3 sentences explaining exactly why this career direction was chosen based on the specific skills, projects and experience present"
  }},
  "focus_score": {{
    "skill_alignment": integer 0-100 (how well skills align to ONE career direction),
    "project_alignment": integer 0-100 (how well projects align to the primary direction),
    "certification_alignment": integer 0-100 (how well certs align, or 75 if no certs present),
    "experience_alignment": integer 0-100 (how well experience aligns, or 60 if no experience),
    "resume_consistency": integer 0-100 (overall narrative consistency across all sections),
    "strengths": [
      "specific strength — reference actual skills/projects from their resume"
    ],
    "weaknesses": [
      "specific weakness — what dilutes their focus or is missing"
    ],
    "recommendations": [
      "concrete, actionable recommendation specific to this person"
    ],
    "reasoning": "2-3 sentences explaining the focus score: what the resume signals about their career clarity and what the score reflects"
  }},
  "resume_rating": {{
    "overall": integer 0-100,
    "subscores": {{
      "skills": integer 0-100,
      "projects": integer 0-100,
      "certifications": integer 0-100,
      "experience": integer 0-100,
      "presentation": integer 0-100,
      "focus": integer 0-100
    }},
    "explanations": {{
      "skills": "one sentence explaining this subscore",
      "projects": "one sentence explaining this subscore",
      "certifications": "one sentence explaining this subscore",
      "experience": "one sentence explaining this subscore",
      "presentation": "one sentence explaining this subscore",
      "focus": "one sentence explaining this subscore"
    }}
  }}
}}

Focus Score calibration:
- skill_alignment: 90+ means ALL skills point to one role; 50 means half are unrelated; below 40 means scattered across 3+ domains
- project_alignment: 90+ means every project builds toward primary role; 50 means half are unrelated
- certification_alignment: score 75 if no certifications exist (neutral, not penalised)
- experience_alignment: score 60 if no experience exists (student baseline)
- resume_consistency: does the resume tell ONE coherent story?
- Provide at least 3 strengths, 3 weaknesses, and 3 recommendations
- Be specific — reference actual technologies and projects from their resume"""

    def _parse_output(self, raw: dict) -> dict:
        cd = raw.get("career_direction", {})
        fs = raw.get("focus_score", {})
        rr = raw.get("resume_rating", {})

        # Recalculate focus score with our authoritative formula
        sa = int(fs.get("skill_alignment", 50))
        pa = int(fs.get("project_alignment", 50))
        ca = int(fs.get("certification_alignment", 75))
        ea = int(fs.get("experience_alignment", 60))
        rc = int(fs.get("resume_consistency", 50))
        calculated_score = round(sa * 0.40 + pa * 0.25 + ca * 0.15 + ea * 0.10 + rc * 0.10)

        def focus_category(score: int) -> str:
            if score >= 90: return "Highly Focused"
            if score >= 70: return "Mostly Focused"
            if score >= 50: return "Mixed"
            return "Unfocused"

        ss = rr.get("subscores", {})
        explanations = rr.get("explanations", {})

        return {
            "career_direction": {
                "primary": cd.get("primary", "Software Engineer"),
                "secondary": cd.get("secondary", "Not strongly evident"),
                "confidence": max(0, min(100, int(cd.get("confidence", 50)))),
                "reasoning": cd.get("reasoning", ""),
            },
            "focus_score": {
                "score": calculated_score,
                "category": focus_category(calculated_score),
                "skill_alignment": sa,
                "project_alignment": pa,
                "certification_alignment": ca,
                "experience_alignment": ea,
                "resume_consistency": rc,
                "strengths": fs.get("strengths", []),
                "weaknesses": fs.get("weaknesses", []),
                "recommendations": fs.get("recommendations", []),
                "reasoning": fs.get("reasoning", ""),
            },
            "resume_rating": {
                "overall": max(0, min(100, int(rr.get("overall", 50)))),
                "subscores": {
                    "skills":          max(0, min(100, int(ss.get("skills", 50)))),
                    "projects":        max(0, min(100, int(ss.get("projects", 50)))),
                    "certifications":  max(0, min(100, int(ss.get("certifications", 50)))),
                    "experience":      max(0, min(100, int(ss.get("experience", 50)))),
                    "presentation":    max(0, min(100, int(ss.get("presentation", 50)))),
                    "focus":           max(0, min(100, int(ss.get("focus", 50)))),
                },
                "explanations": {
                    "skills":         explanations.get("skills", ""),
                    "projects":       explanations.get("projects", ""),
                    "certifications": explanations.get("certifications", ""),
                    "experience":     explanations.get("experience", ""),
                    "presentation":   explanations.get("presentation", ""),
                    "focus":          explanations.get("focus", ""),
                },
            },
        }

    def _fallback(self) -> dict:
        return {
            "career_direction": {
                "primary": "Software Engineer",
                "secondary": "Not strongly evident",
                "confidence": 50,
                "reasoning": "Insufficient data to determine career direction.",
            },
            "focus_score": {
                "score": 50,
                "category": "Mixed",
                "skill_alignment": 50,
                "project_alignment": 50,
                "certification_alignment": 75,
                "experience_alignment": 60,
                "resume_consistency": 50,
                "strengths": [],
                "weaknesses": [],
                "recommendations": [],
                "reasoning": "",
            },
            "resume_rating": {
                "overall": 50,
                "subscores": {
                    "skills": 50, "projects": 50, "certifications": 50,
                    "experience": 50, "presentation": 50, "focus": 50,
                },
                "explanations": {
                    "skills": "", "projects": "", "certifications": "",
                    "experience": "", "presentation": "", "focus": "",
                },
            },
        }

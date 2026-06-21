"""
SkillGapAgent — identifies missing skills for the candidate's primary career direction.

Runs third in the pipeline. Receives context from both ResumeAgent (current skills)
and CareerAgent (primary role) to produce targeted, role-specific gap analysis.

ADK-compatible: name, description, run() via BaseAgent.
"""

import json
from backend.agents.base_agent import BaseAgent, AgentContext


class SkillGapAgent(BaseAgent):
    name = "skill_gap_agent"
    description = (
        "Analyses the gap between a candidate's current skills and those required "
        "for their detected primary career direction. Prioritises missing skills "
        "by career impact (High / Medium / Low)."
    )

    def _build_prompt(self, context: AgentContext) -> str:
        resume_data = context.results.get("resume_agent", {})
        career_data = context.results.get("career_agent", {})

        primary_role = career_data.get("career_direction", {}).get("primary", "Software Engineer")
        current_skills = resume_data.get("skills", [])
        current_certs = resume_data.get("certifications", [])
        current_projects = resume_data.get("projects", [])
        current_exp = resume_data.get("experience", [])

        return f"""You are a technical hiring manager for {primary_role} positions.

Candidate's current profile:
- Skills: {json.dumps(current_skills)}
- Certifications: {json.dumps(current_certs)}
- Projects: {json.dumps(current_projects)}
- Experience: {json.dumps(current_exp)}

Identify the skill gaps between this candidate and a competitive {primary_role}.

Return ONLY a JSON object with this exact schema:
{{
  "role": "{primary_role}",
  "current_skill_assessment": "2-sentence honest assessment of their current skill level for this role",
  "missing_skills": [
    {{
      "skill": "exact skill or technology name",
      "why_it_matters": "specific reason this skill is needed for {primary_role} — one sentence, be concrete",
      "priority": "High",
      "learning_resource": "specific resource (e.g. 'fast.ai course', 'official docs', 'Kaggle competition')"
    }}
  ],
  "partially_present_skills": [
    {{
      "skill": "skill they have but need to deepen",
      "current_level": "what they likely know based on resume",
      "needed_level": "what a competitive {primary_role} needs"
    }}
  ]
}}

Priority definitions:
- High: Required in 90%+ of {primary_role} job postings; without it, resume gets filtered
- Medium: Present in 60-90% of postings; strengthens candidacy significantly  
- Low: Nice-to-have, differentiator but not gatekeeping

Rules:
- Provide 5-8 missing skills minimum, ordered High → Medium → Low
- Do NOT list skills they already have ({json.dumps(current_skills[:10])})
- Be specific: not 'machine learning' but 'PyTorch model fine-tuning' or 'scikit-learn pipelines'
- learning_resource must be a real, specific, free-or-low-cost resource
- Provide 2-4 partially_present_skills that they should deepen"""

    def _parse_output(self, raw: dict) -> dict:
        missing = []
        for item in raw.get("missing_skills", []):
            priority = item.get("priority", "Medium")
            if priority not in ("High", "Medium", "Low"):
                priority = "Medium"
            missing.append({
                "skill": item.get("skill", ""),
                "why_it_matters": item.get("why_it_matters", ""),
                "priority": priority,
                "learning_resource": item.get("learning_resource", ""),
            })

        # Sort: High → Medium → Low
        order = {"High": 0, "Medium": 1, "Low": 2}
        missing.sort(key=lambda x: order.get(x["priority"], 1))

        partial = []
        for item in raw.get("partially_present_skills", []):
            partial.append({
                "skill": item.get("skill", ""),
                "current_level": item.get("current_level", ""),
                "needed_level": item.get("needed_level", ""),
            })

        return {
            "role": raw.get("role", ""),
            "current_skill_assessment": raw.get("current_skill_assessment", ""),
            "missing_skills": missing,
            "partially_present_skills": partial,
        }

    def _fallback(self) -> dict:
        return {
            "role": "",
            "current_skill_assessment": "",
            "missing_skills": [],
            "partially_present_skills": [],
        }

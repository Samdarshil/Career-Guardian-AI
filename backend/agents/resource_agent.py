"""
ResourceAgent — recommends certifications, portfolio projects, and opportunity platforms.

Runs last in the pipeline. Has full context from all four prior agents, enabling
highly personalised recommendations that account for current skills, career direction,
skill gaps, and growth stage.

ADK-compatible: name, description, run() via BaseAgent.
"""

import json
from backend.agents.base_agent import BaseAgent, AgentContext


class ResourceAgent(BaseAgent):
    name = "resource_agent"
    description = (
        "Recommends specific certifications, portfolio projects, and opportunity "
        "platforms personalised to the candidate's career direction, skill gaps, "
        "and professional stage. Only recommends real, existing resources."
    )
    model_temperature = 0.35

    def _build_prompt(self, context: AgentContext) -> str:
        resume_data  = context.results.get("resume_agent", {})
        career_data  = context.results.get("career_agent", {})
        gap_data     = context.results.get("skill_gap_agent", {})

        primary_role = career_data.get("career_direction", {}).get("primary", "Software Engineer")
        existing_certs = resume_data.get("certifications", [])
        existing_skills = resume_data.get("skills", [])
        high_gaps    = [s["skill"] for s in gap_data.get("missing_skills", []) if s.get("priority") == "High"]
        has_exp      = bool(resume_data.get("experience", []))
        focus_score  = career_data.get("focus_score", {}).get("score", 50)

        return f"""You are a career resources advisor for aspiring {primary_role} professionals.

Candidate profile:
- Target role: {primary_role}
- Current skills: {json.dumps(existing_skills[:15])}
- Existing certifications: {json.dumps(existing_certs)}
- High-priority skill gaps: {json.dumps(high_gaps)}
- Has work experience: {has_exp}
- Resume focus score: {focus_score}/100

Return ONLY a JSON object with this exact schema:
{{
  "certifications": [
    {{
      "name": "exact, official certification name",
      "provider": "issuing organisation name",
      "level": "Beginner",
      "why_recommended": "one sentence — why THIS cert for THIS person's specific gaps",
      "expected_benefit": "one sentence — concrete career benefit",
      "approximate_cost": "e.g. 'Free', '$200', 'Free with audit on Coursera'",
      "url": "official URL for this certification"
    }}
  ],
  "projects": [
    {{
      "name": "project name (creative, specific)",
      "difficulty": "Intermediate",
      "description": "one sentence — what the project does",
      "tech_stack": ["technology1", "technology2"],
      "skills_learned": ["skill1", "skill2"],
      "why_it_helps": "one sentence — how this project specifically addresses their gaps and impresses {primary_role} recruiters",
      "github_starter": "suggested repo name in kebab-case"
    }}
  ],
  "opportunities": [
    {{
      "platform": "platform name",
      "type": "Internship | Competition | Open Source | Job Board | Freelance | Community",
      "target_audience": "who it's best for",
      "why_useful": "one sentence — why this platform specifically helps this person",
      "url": "https://actual-platform-url.com"
    }}
  ]
}}

Certification rules:
- Provide exactly 4-5 certifications, ordered Beginner → Intermediate → Advanced
- Do NOT recommend certs they already have: {json.dumps(existing_certs)}
- Only real certifications that exist in 2024/2025
- Mix free and paid options

Project rules:
- Provide exactly 5 projects, varied difficulty (2 Beginner, 2 Intermediate, 1 Advanced)
- Projects must address their HIGH-priority gaps: {json.dumps(high_gaps)}
- Tech stack must include technologies relevant to {primary_role}
- Project names should be creative and portfolio-worthy, not generic ('My ML Project' is bad)

Opportunity platform rules:
- Provide exactly 6 platforms
- Mix: 1-2 internship platforms, 1-2 competition/challenge platforms, 1 open source, 1 community
- For Indian candidates (if location suggests India), include Internshala and Naukri
- Include LinkedIn regardless of location
- url must be the actual, correct homepage URL"""

    def _parse_output(self, raw: dict) -> dict:
        certs = []
        for c in raw.get("certifications", []):
            level = c.get("level", "Beginner")
            if level not in ("Beginner", "Intermediate", "Advanced"):
                level = "Beginner"
            certs.append({
                "name": c.get("name", ""),
                "provider": c.get("provider", ""),
                "level": level,
                "why_recommended": c.get("why_recommended", ""),
                "expected_benefit": c.get("expected_benefit", ""),
                "approximate_cost": c.get("approximate_cost", ""),
                "url": c.get("url", ""),
            })

        projects = []
        for p in raw.get("projects", []):
            diff = p.get("difficulty", "Intermediate")
            if diff not in ("Beginner", "Intermediate", "Advanced"):
                diff = "Intermediate"
            projects.append({
                "name": p.get("name", ""),
                "difficulty": diff,
                "description": p.get("description", ""),
                "tech_stack": p.get("tech_stack", []),
                "skills_learned": p.get("skills_learned", []),
                "why_it_helps": p.get("why_it_helps", ""),
                "github_starter": p.get("github_starter", ""),
            })

        opportunities = []
        for o in raw.get("opportunities", []):
            opportunities.append({
                "platform": o.get("platform", ""),
                "type": o.get("type", ""),
                "target_audience": o.get("target_audience", ""),
                "why_useful": o.get("why_useful", ""),
                "url": o.get("url", ""),
            })

        return {
            "certifications": certs,
            "projects": projects,
            "opportunities": opportunities,
        }

    def _fallback(self) -> dict:
        return {
            "certifications": [],
            "projects": [],
            "opportunities": [],
        }

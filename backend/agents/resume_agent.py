"""
ResumeAgent — extracts structured intelligence from raw resume text.

Runs first in the pipeline. Output is referenced by all downstream agents
so they receive clean, structured data rather than repeating extraction work.

ADK-compatible: name, description, run() via BaseAgent.
"""

from backend.agents.base_agent import BaseAgent, AgentContext
from backend.utils.helpers import sanitise_text


class ResumeAgent(BaseAgent):
    name = "resume_agent"
    description = (
        "Extracts structured intelligence from resume text: personal details, "
        "education, skills, projects, experience, certifications, and achievements."
    )

    def _build_prompt(self, context: AgentContext) -> str:
        resume = sanitise_text(context.resume_text, max_chars=10000)
        return f"""Extract structured information from this resume text.
Return ONLY a JSON object with the exact schema below.

RESUME TEXT:
---
{resume}
---

Return exactly:
{{
  "name": "candidate full name, or 'Not detected' if absent",
  "email": "email address, or 'Not detected'",
  "phone": "phone number, or 'Not detected'",
  "location": "city, country if detectable, else 'Not detected'",
  "education": [
    "Degree Name, Institution Name, Year (e.g. B.Tech Computer Science, IIT Delhi, 2024)"
  ],
  "skills": [
    "individual skill name — one per item, no groupings"
  ],
  "projects": [
    "Project Name: one-sentence description of what it does and tech used"
  ],
  "experience": [
    "Job Title at Company Name, Duration (e.g. ML Intern at Google, Jun-Aug 2023)"
  ],
  "certifications": [
    "Exact Certification Name, Issuer (e.g. TensorFlow Developer Certificate, Google)"
  ],
  "achievements": [
    "specific, quantified achievement where possible"
  ],
  "summary": "Write a 2-3 sentence professional summary of this person based ONLY on what is in their resume. Be specific about technologies and roles."
}}

Rules:
- skills must be individual items: ['Python', 'React', 'SQL'] not ['Python, React, SQL']
- If a section has no data, return an empty array []
- Do not invent information not present in the resume
- summary must reflect actual resume content, not generic statements"""

    def _parse_output(self, raw: dict) -> dict:
        return {
            "name": raw.get("name", "Not detected"),
            "email": raw.get("email", "Not detected"),
            "phone": raw.get("phone", "Not detected"),
            "location": raw.get("location", "Not detected"),
            "education": raw.get("education", []),
            "skills": raw.get("skills", []),
            "projects": raw.get("projects", []),
            "experience": raw.get("experience", []),
            "certifications": raw.get("certifications", []),
            "achievements": raw.get("achievements", []),
            "summary": raw.get("summary", ""),
        }

    def _fallback(self) -> dict:
        return {
            "name": "Not detected",
            "email": "Not detected",
            "phone": "Not detected",
            "location": "Not detected",
            "education": [],
            "skills": [],
            "projects": [],
            "experience": [],
            "certifications": [],
            "achievements": [],
            "summary": "",
        }

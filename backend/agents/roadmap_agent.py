"""
RoadmapAgent — builds a personalised 30/60/90-day growth roadmap.

Runs fourth in the pipeline. Receives context from ResumeAgent, CareerAgent,
and SkillGapAgent to produce a sequenced, actionable plan that directly addresses
the identified gaps and builds toward the detected primary role.

ADK-compatible: name, description, run() via BaseAgent.
"""

import json
from backend.agents.base_agent import BaseAgent, AgentContext


class RoadmapAgent(BaseAgent):
    name = "roadmap_agent"
    description = (
        "Generates a personalised 30/60/90-day professional growth roadmap that "
        "directly addresses identified skill gaps and builds toward the candidate's "
        "primary career direction. Each phase has sequenced, concrete action steps."
    )
    model_temperature = 0.4   # slightly higher for creative planning

    def _build_prompt(self, context: AgentContext) -> str:
        resume_data   = context.results.get("resume_agent", {})
        career_data   = context.results.get("career_agent", {})
        gap_data      = context.results.get("skill_gap_agent", {})

        primary_role  = career_data.get("career_direction", {}).get("primary", "Software Engineer")
        name          = resume_data.get("name", "the candidate")
        current_level = gap_data.get("current_skill_assessment", "")
        high_priority = [s["skill"] for s in gap_data.get("missing_skills", []) if s.get("priority") == "High"]
        med_priority  = [s["skill"] for s in gap_data.get("missing_skills", []) if s.get("priority") == "Medium"]
        has_exp       = bool(resume_data.get("experience", []))
        has_projects  = len(resume_data.get("projects", [])) > 0

        return f"""Create a personalised 30/60/90-day career growth roadmap.

Target role: {primary_role}
Candidate assessment: {current_level}
High-priority gaps to address: {json.dumps(high_priority)}
Medium-priority gaps: {json.dumps(med_priority)}
Has work experience: {has_exp}
Has projects on resume: {has_projects}

Return ONLY a JSON object with this exact schema:
{{
  "day_30": [
    {{
      "action": "concise task title (5-8 words)",
      "details": "specific how-to: name the resource, platform, or approach — not generic advice",
      "outcome": "what they will have at the end of this step (deliverable or skill)",
      "time_commitment": "e.g. '1 hour/day' or '8 hours total'"
    }}
  ],
  "day_60": [
    {{
      "action": "concise task title",
      "details": "specific how-to",
      "outcome": "deliverable or skill gained",
      "time_commitment": "time estimate"
    }}
  ],
  "day_90": [
    {{
      "action": "concise task title",
      "details": "specific how-to",
      "outcome": "deliverable or skill gained",
      "time_commitment": "time estimate"
    }}
  ],
  "milestone_summary": "2-3 sentences describing what the candidate will have achieved after 90 days and how it positions them for {primary_role} roles"
}}

Roadmap design rules:
- 30-day phase: Foundation — address highest-priority gaps, structured learning
- 60-day phase: Application — build project(s) that demonstrate the learned skills
- 90-day phase: Visibility — deploy, publish, apply, or compete
- Each phase must have 3-4 specific steps (not 1, not 6)
- Steps must build sequentially — 60-day steps assume 30-day steps are done
- Name SPECIFIC resources: 'fast.ai Practical Deep Learning course' not just 'learn ML'
- Outcomes must be concrete: 'a trained ResNet model with 90%+ accuracy' not 'understand CNNs'
- If they have no experience, include internship application or open-source contribution steps
- Keep time commitments realistic for a student (1-2 hours/day)"""

    def _parse_output(self, raw: dict) -> dict:
        def parse_phase(steps: list) -> list:
            result = []
            for step in steps:
                result.append({
                    "action": step.get("action", ""),
                    "details": step.get("details", ""),
                    "outcome": step.get("outcome", ""),
                    "time_commitment": step.get("time_commitment", ""),
                })
            return result

        return {
            "day_30": parse_phase(raw.get("day_30", [])),
            "day_60": parse_phase(raw.get("day_60", [])),
            "day_90": parse_phase(raw.get("day_90", [])),
            "milestone_summary": raw.get("milestone_summary", ""),
        }

    def _fallback(self) -> dict:
        return {
            "day_30": [],
            "day_60": [],
            "day_90": [],
            "milestone_summary": "",
        }

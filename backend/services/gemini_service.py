"""
Gemini Service — handles all Google Gemini API communication.
Implements exponential backoff retry (max 2 retries) and 20s generation timeout.
"""

import asyncio
import os
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted, ServiceUnavailable

from utils.helpers import sanitise_text, safe_parse_json

MAX_RETRIES = 2
BASE_DELAY = 2.0  # seconds — doubles each retry: 2s, 4s
GENERATION_TIMEOUT = 60.0  # seconds


def _configure_gemini() -> genai.GenerativeModel:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set in environment variables.")
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(
        model_name="gemini-2.5-flash-lite",
        system_instruction=(
            "You are an expert Career Mentor AI with 15 years of experience in talent "
            "acquisition, career coaching, and technical recruitment. "
            "Analyze the provided resume text deeply and holistically. "
            "Return ONLY valid JSON. No markdown. No code fences. No explanations outside JSON. "
            "Every field in the schema must be present. Never return empty arrays where data exists."
        ),
        generation_config=genai.GenerationConfig(
            temperature=0.3,
            response_mime_type="application/json",
        ),
    )


def _build_prompt(resume_text: str) -> str:
    clean_text = sanitise_text(resume_text)
    return f"""Analyze the following resume and return a single JSON object matching this exact schema.
Be thorough, specific, and actionable. Base all analysis on actual resume content.

RESUME TEXT:
---
{clean_text}
---

Return a JSON object with exactly these top-level keys:

{{
  "resume_intelligence": {{
    "name": "full name",
    "email": "email address",
    "phone": "phone number",
    "education": ["degree and institution strings"],
    "skills": ["individual skill names"],
    "projects": ["project name and one-line description"],
    "experience": ["role at company, duration"],
    "certifications": ["certification names"],
    "achievements": ["notable achievements"],
    "summary": "2-3 sentence professional summary of this person"
  }},

  "career_direction": {{
    "primary": "most fitting career role title",
    "secondary": "second most fitting career role title",
    "confidence": integer 0-100,
    "reasoning": "2-3 sentences explaining why this direction fits"
  }},

  "focus_score": {{
    "score": integer 0-100 (weighted: skill_alignment*0.40 + project_alignment*0.25 + certification_alignment*0.15 + experience_alignment*0.10 + resume_consistency*0.10),
    "category": "Highly Focused|Mostly Focused|Mixed|Unfocused",
    "skill_alignment": integer 0-100,
    "project_alignment": integer 0-100,
    "certification_alignment": integer 0-100,
    "experience_alignment": integer 0-100,
    "resume_consistency": integer 0-100,
    "strengths": ["specific strength about resume focus"],
    "weaknesses": ["specific weakness or scattered area"],
    "recommendations": ["concrete actionable recommendation"],
    "reasoning": "explain what the resume signals about career focus and why score was given"
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
      "skills": "why this skills score",
      "projects": "why this projects score",
      "certifications": "why this certifications score",
      "experience": "why this experience score",
      "presentation": "why this presentation score",
      "focus": "why this focus score"
    }}
  }},

  "skill_gap": {{
    "role": "primary career direction role",
    "missing_skills": [
      {{
        "skill": "skill name",
        "why_it_matters": "why this skill is needed for the role",
        "priority": "High|Medium|Low"
      }}
    ]
  }},

  "growth_roadmap": {{
    "day_30": [
      {{"action": "specific task", "details": "how to do it", "outcome": "what you'll gain"}}
    ],
    "day_60": [
      {{"action": "specific task", "details": "how to do it", "outcome": "what you'll gain"}}
    ],
    "day_90": [
      {{"action": "specific task", "details": "how to do it", "outcome": "what you'll gain"}}
    ]
  }},

  "certifications": [
    {{
      "name": "exact certification name",
      "provider": "issuing organization",
      "level": "Beginner|Intermediate|Advanced",
      "why_recommended": "why this cert fits this person",
      "expected_benefit": "concrete career benefit"
    }}
  ],

  "projects": [
    {{
      "name": "project name",
      "difficulty": "Beginner|Intermediate|Advanced",
      "description": "what the project does in one sentence",
      "skills_learned": ["skill1", "skill2"],
      "why_it_helps": "how this strengthens the career direction"
    }}
  ],

  "opportunities": [
    {{
      "platform": "platform name",
      "target_audience": "who this is best for",
      "why_useful": "how this platform helps this specific person",
      "url": "https://platform-url.com"
    }}
  ]
}}

Rules:
- focus_score.score must equal round(skill_alignment*0.40 + project_alignment*0.25 + certification_alignment*0.15 + experience_alignment*0.10 + resume_consistency*0.10)
- focus_score.category: 90-100=Highly Focused, 70-89=Mostly Focused, 50-69=Mixed, 0-49=Unfocused
- Provide at least 4 missing skills, 3 steps per roadmap phase, 4 certifications, 5 projects, 6 opportunity platforms
- Only recommend real, existing certifications
- All recommendations must be specific to this person's actual resume content"""


async def _call_gemini_async(model: genai.GenerativeModel, prompt: str) -> str:
    """Run Gemini generation in a thread pool to avoid blocking the event loop."""
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(
        None,
        lambda: model.generate_content(prompt),
    )
    return response.text


async def analyse_resume(resume_text: str) -> dict:
    """
    Send resume text to Gemini and return a validated parsed JSON dict.
    Implements exponential backoff on transient failures.

    Raises:
        HTTPException(503): on quota exhaustion.
        HTTPException(500): on repeated analysis failure.
    """
    from fastapi import HTTPException

    model = _configure_gemini()
    prompt = _build_prompt(resume_text)

    last_error: Exception | None = None

    for attempt in range(MAX_RETRIES + 1):
        try:
            raw_text = await asyncio.wait_for(
                _call_gemini_async(model, prompt),
                timeout=GENERATION_TIMEOUT,
            )
            parsed = safe_parse_json(raw_text)
            if parsed:
                return parsed
            raise ValueError("Gemini returned empty or unparseable JSON.")

        except ResourceExhausted:
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "gemini_quota",
                    "message": "AI service quota exceeded. Please try again later.",
                },
            )

        except asyncio.TimeoutError:
            last_error = TimeoutError("Gemini generation timed out.")
            if attempt < MAX_RETRIES:
                await asyncio.sleep(BASE_DELAY * (2 ** attempt))
            continue

        except (ServiceUnavailable, Exception) as e:
            print("🔥 GEMINI ERROR:", repr(e))
            last_error = e

            if attempt < MAX_RETRIES:
                await asyncio.sleep(BASE_DELAY * (2 ** attempt))
                continue

    raise

    # All retries exhausted
    if isinstance(last_error, TimeoutError):
        raise HTTPException(
            status_code=504,
            detail={
                "error": "timeout",
                "message": "Analysis timed out after 25 seconds. Please try again.",
            },
        )

    raise HTTPException(
        status_code=500,
        detail={
            "error": "analysis_failed",
            "message": "Analysis could not be completed. Please try again.",
        },
    )

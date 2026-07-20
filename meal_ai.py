import json
import os
import re

import anthropic

MODEL = "claude-sonnet-5"
MAX_TOKENS = 4096

_client = None


def _get_client():
    global _client
    if _client is None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. Add it to your .env file."
            )
        _client = anthropic.Anthropic(api_key=api_key)
    return _client


SYSTEM_PROMPT = """You are the meal-planning engine behind EasyGreen, a nutrition app.

Given a user's dietary restrictions, allergies, and goals, you:
1. Use web search to find real, currently published meals or recipes online that fit
   the user's needs. Prefer reputable recipe sites, health publications, or registered
   dietitian sources. Never invent a recipe or a URL — every source_url must come from
   an actual search result.
2. Score each meal from 0 to 100 on how well it fits the user's stated needs.
3. Build the score out of specific, labeled point adjustments (a "score_breakdown"),
   for example: -5 points if it conflicts with a stated dairy restriction, +5 points if
   it supports a stated dairy goal, +10 points if it strongly supports a stated macro
   or weight goal, -10 points if it contains a listed allergen. Every adjustment must
   reference a specific restriction, allergy, or goal the user actually gave you, and
   the points in score_breakdown must sum to the final score.
4. Produce a 7-day schedule (Monday through Sunday), one distinct meal per day, with
   variety across the week (do not repeat the same meal twice).

CRITICAL SAFETY RULE: if a meal conflicts with a listed allergy, do not include it in
the plan at all — find a different meal instead. Allergies are a hard filter, not a
scoring penalty.

Respond with nothing but a single JSON object, no prose before or after it, matching
exactly this shape:

{
  "days": [
    {
      "day": "Monday",
      "meal_name": "string",
      "source_url": "string, a real URL returned by web search",
      "source_name": "string, the publication or site name",
      "score": 0,
      "score_breakdown": [
        {"label": "string describing the specific reason", "points": 0}
      ],
      "why": "one to two sentence plain-language summary of why this meal was picked"
    }
  ]
}

The "days" array must contain exactly 7 objects, one per day of the week in order
starting with Monday. Return valid JSON only.
"""


def _build_user_prompt(profile):
    restrictions = profile.get("restrictions") or ["None specified"]
    allergies = profile.get("allergies") or ["None specified"]
    goals = profile.get("goals") or ["None specified"]
    notes = profile.get("notes") or "None"

    return (
        "Build a 7-day meal plan for a user with the following profile.\n\n"
        f"Dietary restrictions: {', '.join(restrictions)}\n"
        f"Allergies: {', '.join(allergies)}\n"
        f"Goals: {', '.join(goals)}\n"
        f"Additional notes: {notes}\n\n"
        "Search the web for real meals that fit this profile, score each one, and "
        "return the JSON plan described in your instructions."
    )


def _extract_text(response):
    return "".join(
        block.text for block in response.content if getattr(block, "type", None) == "text"
    )


def _parse_plan(raw_text):
    cleaned = raw_text.strip()
    cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()

    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if not match:
        raise ValueError("Model response did not contain a JSON object.")

    data = json.loads(match.group(0))

    days = data.get("days")
    if not isinstance(days, list) or len(days) != 7:
        raise ValueError("Model response did not contain exactly 7 days.")

    for day in days:
        for field in ("day", "meal_name", "source_url", "source_name", "score", "score_breakdown", "why"):
            if field not in day:
                raise ValueError(f"Day entry is missing required field: {field}")

    return data


MOCK_MEALS = [
    ("Monday", "Grilled Chicken & Quinoa Bowl", "https://www.eatingwell.com/", "EatingWell"),
    ("Tuesday", "Baked Salmon with Roasted Vegetables", "https://www.seriouseats.com/", "Serious Eats"),
    ("Wednesday", "Lentil & Sweet Potato Curry", "https://cookieandkate.com/", "Cookie and Kate"),
    ("Thursday", "Turkey and Black Bean Chili", "https://www.budgetbytes.com/", "Budget Bytes"),
    ("Friday", "Shrimp Stir-Fry with Brown Rice", "https://www.skinnytaste.com/", "Skinnytaste"),
    ("Saturday", "Chickpea and Spinach Buddha Bowl", "https://minimalistbaker.com/", "Minimalist Baker"),
    ("Sunday", "Overnight Oats with Berries and Almond Butter", "https://www.loveandlemons.com/", "Love and Lemons"),
]


def _mock_score_breakdown(profile):
    breakdown = []
    for restriction in profile.get("restrictions") or []:
        breakdown.append({"label": f"Fits {restriction.lower()} restriction", "points": 5})
    for goal in profile.get("goals") or []:
        breakdown.append({"label": f"Supports goal: {goal.lower()}", "points": 8})
    if not breakdown:
        breakdown.append({"label": "Balanced macros, no red flags", "points": 10})
    return breakdown


def _generate_mock_plan(profile: dict) -> dict:
    days = []
    for day_name, meal_name, source_url, source_name in MOCK_MEALS:
        breakdown = _mock_score_breakdown(profile)
        score = max(0, min(100, 70 + sum(item["points"] for item in breakdown)))
        days.append(
            {
                "day": day_name,
                "meal_name": meal_name,
                "source_url": source_url,
                "source_name": source_name,
                "score": score,
                "score_breakdown": breakdown,
                "why": "Mock data — set USE_MOCK_DATA=False in .env to generate a real plan.",
            }
        )
    return {"days": days}


def _using_mock_data() -> bool:
    return os.getenv("USE_MOCK_DATA", "false").lower() == "true"


def generate_meal_plan(profile: dict) -> dict:
    """Return a parsed 7-day plan, either from the live model or from mock data."""
    if _using_mock_data():
        return _generate_mock_plan(profile)

    client = _get_client()
    user_prompt = _build_user_prompt(profile)

    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=SYSTEM_PROMPT,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw_text = _extract_text(response)
    return _parse_plan(raw_text)
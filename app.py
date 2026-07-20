import os

from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, request, url_for

from meal_ai import generate_meal_plan

load_dotenv()

app = Flask(__name__, static_folder="Static", template_folder="Templates")
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev")

RESTRICTION_OPTIONS = [
    "Vegetarian",
    "Vegan",
    "Gluten-free",
    "Dairy-free",
    "Nut-free",
    "Halal",
    "Kosher",
    "Low-sodium",
]

GOAL_OPTIONS = [
    "Weight loss",
    "Weight gain",
    "Increase protein",
    "Increase carbs",
    "Decrease sugar",
    "Increase dairy",
    "Decrease dairy",
    "Muscle building",
    "General health",
]


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/intake")
def intake():
    return render_template(
        "intake.html",
        restriction_options=RESTRICTION_OPTIONS,
        goal_options=GOAL_OPTIONS,
    )


@app.route("/plan", methods=["POST"])
def plan():
    profile = {
        "restrictions": request.form.getlist("restrictions"),
        "allergies": [a.strip() for a in request.form.get("allergies", "").split(",") if a.strip()],
        "goals": request.form.getlist("goals"),
        "notes": request.form.get("notes", "").strip(),
    }

    if not profile["goals"]:
        flash("Pick at least one goal so the plan has something to optimize for.")
        return redirect(url_for("intake"))

    try:
        result = generate_meal_plan(profile)
    except Exception as exc:
        app.logger.exception("Meal plan generation failed")
        return render_template("error.html", message=str(exc)), 500

    return render_template("plan.html", profile=profile, days=result["days"])


if __name__ == "__main__":
    debug_mode = os.getenv("FLASK_DEBUG", "True").lower() == "true"
    port = int(os.getenv("PORT", 5000))
    app.run(debug=debug_mode, port=port)
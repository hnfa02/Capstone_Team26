# Gen AI Tools (ChatGPT used)
from google.adk.tools import AgentTool
import pandas as pd
from config.settings import met_data_path

# Tools for Exercise Agent

def get_exercise_intensity(glucose_level:int) -> list:
    """Returns the recommended exercise intensity based on the glucose level."""
    if glucose_level < 90:
        return ["Avoid"]
    elif 90 <= glucose_level <= 124:
        return ["Light"]
    elif 125 <= glucose_level <= 180:
        return ["Light", "Moderate", "Vigorous"]
    elif 181 <= glucose_level <= 270:
        return ["Light", "Moderate"]
    elif glucose_level > 270:
        return ["Avoid"]

def classify_glucose_state(minutes_since_last_meal):
    if minutes_since_last_meal is None:
        return "unknown"

    if minutes_since_last_meal < 60:
        return "post_meal_rising"
    elif 60 <= minutes_since_last_meal <= 120:
        return "post_meal_peak"
    else:
        return "fasted_or_stable"

def adjust_for_carbs(base_plan, carbs):
    if carbs is None:
        return base_plan

    if carbs > 60:
        base_plan["duration"] = "30–60 min"
        base_plan["note"] = "Higher carbs → longer activity recommended"

    elif carbs < 20:
        base_plan["note"] = "Low-carb meal → monitor for hypoglycemia"

    return base_plan

def pre_meal_strategy(upcoming_meal_carbs):
    if upcoming_meal_carbs is None:
        return None

    if upcoming_meal_carbs > 50:
        return {
            "pre_meal_exercise": "10–20 min light/moderate activity",
            "benefit": "Improves insulin sensitivity and reduces spike"
        }

def search_exercise_by_intensity(intensity: str) -> list:
    df = pd.read_csv(met_data_path)
    filtered = df[df["Intensity"] == intensity]
    return filtered[["Description", "MET"]].to_dict(orient="records")

def get_exercise_intensity_by_meal(
    glucose_level: int,
    minutes_since_last_meal: int = None,
    last_meal_carbs: int = None,
    upcoming_meal_carbs: int = None
) -> dict:

    base_intensity = get_exercise_intensity(glucose_level)

    if "Avoid" in base_intensity:
        return {
            "status": "unsafe",
            "message": "Glucose level not suitable for exercise",
            "pre_exercise": "Consume carbohydrates and recheck glucose"
        }

    state = classify_glucose_state(minutes_since_last_meal)

    if state == "post_meal_rising":
        plan = {
            "status": "ok",
            "focus": "reduce_spike",
            "intensity": ["Light"],
            "duration": "10–30 min"
        }

    elif state == "post_meal_peak":
        plan = {
            "status": "ok",
            "focus": "glucose_utilization",
            "intensity": ["Light", "Moderate"],
            "duration": "20–45 min"
        }

    else:
        plan = {
            "status": "ok",
            "focus": "general_fitness",
            "intensity": base_intensity
        }

    plan = adjust_for_carbs(plan, last_meal_carbs)

    pre_meal = pre_meal_strategy(upcoming_meal_carbs)
    if pre_meal:
        plan["pre_meal_strategy"] = pre_meal

    return plan


def get_exercise_recommendation(glucose_level: int,
    minutes_since_last_meal: int = None,
    last_meal_carbs: int = None,
    upcoming_meal_carbs: int = None) -> dict:
    # calculating exercise based on current glucose, next steps incorporate pre/post meal exercise recommendations based on carbs in the meal
    plan = get_exercise_intensity_by_meal(glucose_level, minutes_since_last_meal, last_meal_carbs, upcoming_meal_carbs)
    intensity_levels = list(plan['intensity'])

    if "Avoid" in intensity_levels:
        return {
            "status": "unsafe",
            "message": "Glucose level not suitable for exercise",
            "pre_exercise": "Consume carbohydrates and recheck glucose"
        }

    all_exercises = []

    for level in intensity_levels:
        exercises = search_exercise_by_intensity(level)

        for e in exercises:
            all_exercises.append({
                "description": e["Description"],
                "met": e["MET"],
                "intensity": level
            })

    return {
        "status": "ok",
        "recommended_exercises": all_exercises,
        "plan": plan
    }

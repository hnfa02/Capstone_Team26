# =============================================================================
# MADS699 Capstone Project — Glucose Coaching Agent System
# Converted from Jupyter Notebook to .py
# =============================================================================

# ─── SECTION 1: SECRETS & API SETUP ──────────────────────────────────────────

import os
from google.cloud import secretmanager

project_id = os.environ.get('GOOGLE_CLOUD_PROJECT')

def access_secret_version(secret_id, version_id="latest"):
    """Function to access secrets from Google Cloud Secret Manager."""
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{project_id}/secrets/{secret_id}/versions/{version_id}"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8").strip()

try:
    Capstone_project_key = access_secret_version("Capstone_project_key3")
    os.environ["GOOGLE_API_KEY"] = Capstone_project_key
    os.environ["Capstone_project_key"] = Capstone_project_key
    print("✅ Gemini API key setup complete from Secret Manager.")
except Exception as e:
    print(f"🔑 Authentication Error for Capstone_project_key: {e}")

try:
    Food_API = access_secret_version("Food_API")
    os.environ["Food_API"] = Food_API
    print("✅ Food API key setup complete from Secret Manager.")
except Exception as e:
    print(f"🔑 Authentication Error for Food_API: {e}")


# ─── SECTION 2: ADK IMPORTS ──────────────────────────────────────────────────

from google.adk.agents import Agent
from google.adk.models.google_llm import Gemini
from google.adk.runners import InMemoryRunner
from google.adk.tools import AgentTool, FunctionTool, google_search
from google.genai import types

print("✅ ADK components imported successfully.")


# ─── SECTION 3: RETRY CONFIG ─────────────────────────────────────────────────

retry_config = types.HttpRetryOptions(
    attempts=5,
    exp_base=7,
    initial_delay=1,
    http_status_codes=[429, 500, 503, 504]
)
print("✅ Retry config for Agents created successfully.")


# ─── SECTION 4: ALERT AGENT ──────────────────────────────────────────────────

AlertAgent = Agent(
    name='AlertAgent',
    model=Gemini(model='gemini-2.5-flash', retry_options=retry_config),
    description="You are a proactive Alert agent",
    instruction="""
You are a proactive Alert Agent for a diabetes management system.

You will receive a message containing:
  - current_time          (full value including day and time,
                           e.g. "Saturday, 6:30 PM ET")
  - current_day           (day of week extracted from current_time,
                           e.g. "Saturday")
  - alert_scenario        ("upcoming_meal" or "past_meal_not_taken")
  - usual_meal_times      (breakfast, lunch, dinner)
  - closest_meal          (meal name + time)
  - last_meal
  - has_meal_taken_around_current_time  (true/false)
  - oral_medication
  - insulin
  - long_acting_insulin
  - glp1                  (e.g. "weekly on Saturdays", "daily", "no")
  - glp1_due_today        (true/false — pre-computed by Orchestrator)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CRITICAL RULES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  - NEVER invent or assume current_time — use ONLY the value provided
  - NEVER invent or assume meal times — use ONLY usual_meal_times provided
  - NEVER invent has_meal_taken_around_current_time — read from input
  - NEVER mention weekly GLP-1 if glp1_due_today = false
  - If current_time or meal_times are missing → respond:
    "Cannot generate alert — current_time or meal_times not provided."

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LONG-ACTING INSULIN TIMING RULE (READ BEFORE ANYTHING ELSE)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  ┌─────────────────────────────────────────────────────────────┐
  │ LONG-ACTING INSULIN ALERT WINDOW = 60 MINUTES ONLY         │
  │                                                             │
  │ Extract the preferred time from long_acting_insulin.        │
  │ Example: "Yes, every night 9PM ET" → preferred = 9:00 PM   │
  │                                                             │
  │ Calculate: minutes_until_lai = preferred_time - current_time│
  │                                                             │
  │ ONLY generate a long-acting insulin reminder if:            │
  │   minutes_until_lai is between -60 and +60 minutes          │
  │   (i.e. within 60 min before OR 60 min after preferred time)│
  │                                                             │
  │ If minutes_until_lai > 60 minutes away → SKIP entirely.    │
  │ Do NOT mention long-acting insulin at all.                  │
  │ Do NOT add it to any alert.                                 │
  │                                                             │
  │ EXAMPLES:                                                   │
  │   current=8:30PM, preferred=9:00PM → 30 min away → ALERT ✅│
  │   current=8:00PM, preferred=9:00PM → 60 min away → ALERT ✅│
  │   current=7:00PM, preferred=9:00PM → 120 min away → SKIP ❌│
  │   current=9:00PM, preferred=9:00PM → 0 min away → ALERT ✅ │
  │   current=9:20PM, preferred=9:00PM → 20 min past → ALERT ✅│
  │   current=10:45PM, preferred=9:00PM → 105 min past → SKIP ❌│
  └─────────────────────────────────────────────────────────────┘

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP 1 — BUILD MEDICATION LIST
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Build the medication list from inputs.
  Include each item that applies:

  ┌─────────────────────────────────────────────────────────┐
  │ oral_medication = 'pre-meal'                            │
  │   → include "pre-meal oral medication"                  │
  │                                                         │
  │ insulin = 'yes'                                         │
  │   → include "short-acting insulin"                      │
  │                                                         │
  │ glp1 = 'daily':                                        │
  │   → include "GLP-1 agonist (daily dose)"                │
  │                                                         │
  │ glp1 = 'weekly on [Day]' AND glp1_due_today = true:    │
  │   → include "GLP-1 agonist (weekly dose — today,        │
  │     [current_day], is your scheduled injection day)"    │
  │   ← ALWAYS include the day name inline                  │
  │   ← NEVER write just "GLP-1 agonist (weekly dose)"     │
  │     without the day — the day must always be present    │
  │                                                         │
  │ glp1 = 'weekly on [Day]' AND glp1_due_today = false:   │
  │   → do NOT include GLP-1 at all                         │
  │                                                         │
  │ glp1 = 'no' or 'none':                                 │
  │   → do NOT include                                      │
  └─────────────────────────────────────────────────────────┘

  DAY MATCHING EXAMPLES:
    glp1="weekly on Saturdays", current_day="Saturday"
      → glp1_due_today=true → INCLUDE GLP-1 alert ✅

    glp1="weekly on Saturdays", current_day="Tuesday"
      → glp1_due_today=false → SKIP GLP-1 entirely ❌

    glp1="weekly on Mondays", current_day="Monday"
      → glp1_due_today=true → INCLUDE GLP-1 alert ✅

  CRITICAL:
    Never mention weekly GLP-1 if glp1_due_today = false.
    Day matching is already done by the Orchestrator — trust glp1_due_today.
    Do not re-derive the day match yourself — use glp1_due_today directly.

  Examples of built medication lists:
    oral + insulin + glp1 daily:
      → "pre-meal oral medication, short-acting insulin,
         and GLP-1 agonist (daily dose)"

    oral + insulin + glp1 weekly (due today):
      → "pre-meal oral medication, short-acting insulin,
         and GLP-1 agonist (weekly dose — today, [current_day],
         is your scheduled injection day)"

    oral + insulin + glp1 weekly (NOT due today):
      → "pre-meal oral medication and short-acting insulin"
         (GLP-1 not mentioned at all)

    insulin only:
      → "short-acting insulin"

    oral + insulin (no glp1):
      → "pre-meal oral medication and short-acting insulin"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP 2 — GENERATE ALERT BY SCENARIO
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  SCENARIO A — alert_scenario = "upcoming_meal":

    Template:
    "It is [current_time]. Your [closest_meal name] is scheduled for
     [closest_meal time]. Please take your [medication list] now,
     15 minutes before your meal."

    ⚠️  GLP-1 APPEND RULE — READ CAREFULLY:

      IF glp1 = 'daily':
        → Append ONLY this sentence:
          "This is also a good time to take your daily GLP-1 agonist
           dose if you have not already."

      IF glp1 = 'weekly':
        → DO NOT append anything.
        → STOP after the template sentence.
        → The medication list already contains the full weekly GLP-1
          reminder including the day name.
        → Any appended sentence about GLP-1 is a DUPLICATE — omit it.

      IF glp1 = 'no' or glp1_due_today = false:
        → DO NOT append anything GLP-1 related.

  SCENARIO B — alert_scenario = "past_meal_not_taken":

    Template:
    "It is [current_time]. Your [closest_meal name] was scheduled for
     [closest_meal time]. If you have not yet taken your [medication list]
     and are about to eat, please take it now before your meal.
     If you have already taken your medication, no action is needed."

    ⚠️  GLP-1 APPEND RULE — READ CAREFULLY:

      IF glp1 = 'daily':
        → Append ONLY this sentence:
          "If you have not yet taken your daily GLP-1 agonist dose
           today, please take it now."

      IF glp1 = 'weekly':
        → DO NOT append anything.
        → STOP after the template sentence.
        → Same reason as Scenario A — medication list already covers it.

      IF glp1 = 'no' or glp1_due_today = false:
        → DO NOT append anything GLP-1 related.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP 4 — NO ALERT CASE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  If no scenario applies and long-acting insulin is not within
  60 minutes → respond:
  "No medication due at [current_time]."

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OUTPUT RULES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  - Plain text only — no JSON, no markdown
  - Always state EXACT current_time and meal_time from input
  - Always use current_day by name (e.g. "Saturday") when
    referencing the GLP-1 injection day — never say "today" alone
  - Use warm, supportive, non-alarming language
  - Keep it concise — 3–5 sentences maximum
  - NEVER mention long-acting insulin more than 60 min from preferred time
  - NEVER mention weekly GLP-1 if glp1_due_today = false
  - Never mention medication names beyond what was provided in input
"""
)
print("✅ AlertAgent created.")

# ─── SECTION 5: INSULIN AGENT ─────────────────────────────────────────────────

def get_insulin_dose(glucose_level: int) -> dict:
    """Returns the recommended insulin dose based on the glucose level."""
    if glucose_level < 151:
        return {"status": "success", "dose": "No insulin needed"}
    elif 151 <= glucose_level <= 200:
        return {"status": "success", "dose": "Take 2 units of short acting insulin before meal"}
    elif 201 <= glucose_level <= 250:
        return {"status": "success", "dose": "Take 4 units of short acting insulin before meal"}
    elif 251 <= glucose_level <= 300:
        return {"status": "success", "dose": "Take 6 units of short acting insulin before meal"}
    elif 301 <= glucose_level <= 350:
        return {"status": "success", "dose": "Take 8 units of short acting insulin before meal"}
    elif 351 <= glucose_level <= 400:
        return {"status": "success", "dose": "Take 10 units of short acting insulin before meal"}
    else:
        return {"status": "error", "message": "Glucose level too high, please call doctor"}

InsulinAgent = Agent(
    name='InsulinRecommenderAgent',
    model=Gemini(model='gemini-2.5-flash-lite', retry_options=retry_config),
    description="You are an expert Insulin coach. Given a patients glucose level at preferred meal time or current glucose level if the preferred time has passed and there is no indication that the expected meal is taken, provide a suggestion of recommended dosage of insulin.",
    instruction="""
    You are an Insulin Recommender Agent. Your task is to provide a suggestion
    of an appropriate insulin dosage based on the patient's glucose level.

    WORKFLOW:
    1. Call the get_insulin_dose tool with the glucose_level provided
    2. After receiving the tool result, YOU MUST respond with a text message

    CRITICAL: You MUST always produce a text response after calling get_insulin_dose.
    Never return an empty response. Never return None.

    Your response MUST follow this exact format:
    "Recommended dose: {dose from tool}. Administer before meal."

    Example:
    Tool returns: "Take 2 units of short acting insulin before meal"
    Your response: "Recommended dose: Take 2 units of short acting insulin before meal.
    Administer before meal."

    If the tool returns no dose or an error:
    Your response: "Recommended dose: 0 units. No insulin required at this glucose level."

    NEVER skip the text response step. NEVER return empty content.
    """,
    tools=[get_insulin_dose],
)
print("✅ InsulinAgent created.")


# ─── SECTION 6: FOOD SEARCH TOOL ─────────────────────────────────────────────

import requests

API_KEY = Food_API

def search_food_by_carbs(food_name: str, min_carbs: float = None, max_carbs: float = None):
    
    #MealAgent_logger.info(f"Tool called: search_food_by_carbs | food={food_name} | max_carbs={max_carbs}")

    url = "https://api.nal.usda.gov/fdc/v1/foods/search"

    params = {
        "query": food_name,
        "pageSize": 20,
        "api_key": API_KEY
    }

    r = requests.get(url, params=params).json()

    foods = []

    for food in r["foods"]:
        nutrients = food.get("foodNutrients", [])
        nutrient_map = {n["nutrientName"]: n["value"] for n in nutrients}

        carbs = nutrient_map.get("Carbohydrate, by difference")
        protein = nutrient_map.get("Protein")
        calories = nutrient_map.get("Energy (kcal)") or nutrient_map.get("Energy")

        calories_from_carbs = carbs * 4 if carbs is not None else None

        if carbs is not None:
            if (min_carbs is None or carbs >= min_carbs) and \
               (max_carbs is None or carbs <= max_carbs):
                foods.append({
                "name": food["description"],
                "carbs_g": carbs,
                "protein_g": protein,
                "calories_kcal": calories,
                "calories_from_carbs": calories_from_carbs,
                "serving_size": food.get("servingSize"),
                "serving_unit": food.get("servingSizeUnit")
            })
    #MealAgent_logger.info(f"Tool result count: {len(foods)} foods returned")


    return foods


print("✅ search_food_by_carbs() created successfully")


# ─── SECTION 7: MEAL AGENT ───────────────────────────────────────────────────

MealAgent =  Agent(
name= "MealRecommenderAgent",
model=Gemini(
    model="gemini-2.5-flash-lite",
    api_key=Capstone_project_key,   
    retry_options=retry_config
),
description= "Recommends a meal for diabetes management. Recommended meal includes Protein, Vegetables, and Carbohydrates.",
# This instruction tells the Meal Agent HOW to use its tools (which are the other agents).
instruction="""

Role

You are a Diabetes Nutrition Coach Agent.
Your goal is to recommend meals and hydration strategies that help keep the user's
blood glucose within 90–150 mg/dL.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CRITICAL RULE — TOOL USE IS MANDATORY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

You MUST ALWAYS call search_food_by_carbs before recommending any food.
You are NEVER allowed to recommend specific foods from your own knowledge.
Every food item in your final response MUST come from a search_food_by_carbs result.
Responding with food names without calling the tool first is an ERROR.



━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP 1 — DETERMINE GLUCOSE STATUS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Read current_glucose from the input:

    current_glucose > 150  → HIGH:  protein + vegetables ONLY.
                            No intentional carbohydrate course.
                            Naturally occurring carbs from protein and
                            vegetables (typically 5–15g total) are acceptable
                            and expected — do not try to eliminate them.
  current_glucose 70–150 → NORMAL: balanced meal with controlled carbs allowed.
  current_glucose < 70   → LOW:    fast-acting carbohydrates REQUIRED immediately.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP 2 — READ AND APPLY DIET PREFERENCE (MANDATORY)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Read the diet preference from the input. Apply these rules strictly:

  Non-Veg (omnivore):
    → Protein options: chicken breast, turkey, fish (salmon, tuna), eggs, Greek yogurt
    → All vegetables and controlled carbs allowed

  Veg (vegetarian, no meat/seafood):
    → Protein options: eggs, Greek yogurt, paneer, tofu, lentils, chickpeas, cottage cheese
    → No chicken, turkey, fish, or any meat/seafood
    → All vegetables and controlled carbs allowed

  Vegan (no animal products):
    → Protein options: tofu, tempeh, lentils, chickpeas, black beans, edamame
    → No meat, seafood, eggs, dairy, or any animal-derived products
    → All vegetables and controlled carbs allowed

  Gluten-Free:
    → Avoid wheat, barley, rye, oats (unless certified gluten-free)
    → Safe carbs: rice, quinoa, sweet potato, corn
    → Can be combined with Non-Veg / Veg / Vegan preference

CRITICAL:
  - If diet = "Veg" or "Vegan" → you MUST NOT search for or recommend
    chicken, turkey, fish, beef, or any meat/seafood under any circumstance
  - If diet = "Vegan" → you MUST NOT search for or recommend eggs, 
    Greek yogurt, paneer, or any dairy product
  - Diet preference OVERRIDES all other food suggestions
  - If search returns a non-compliant food → discard it and search for 
    a compliant alternative

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP 3 — IDENTIFY MEAL TYPE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Based on current_time and usual_meal_times, identify:
Breakfast, Lunch, or Dinner.
Always state the meal type explicitly in your response.

Do NOT recommend a meal if the user ate within the last 1 hour,
unless glucose < 70 mg/dL (hypoglycemia always overrides).
You may still recommend hydration even if no meal is needed.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP 4 — CALL search_food_by_carbs (MANDATORY, MEAL-TYPE SPECIFIC)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Read meal_type from input (Breakfast / Lunch / Dinner).
Use the food searches below based on BOTH meal_type AND glucose status.
Diet preference rules from Step 2 still apply — never search non-compliant foods.

SELECTION RULE:
  - From each category below, RANDOMLY select 1 protein, 1 vegetable,
    and 1 carbohydrate (if allowed) to search for.
  - Do NOT always pick the first option — vary your selection each run
    so users get different recommendations over time.
  - If search returns {} → try the next option in that category.
  - Never recommend the same food for both protein and vegetable.

──────────────────────────────────────────────────────────
BREAKFAST (meal_type = Breakfast)
──────────────────────────────────────────────────────────

IF glucose > 150 (HIGH — protein + veg only):

    → Search for protein and vegetable options only (as listed below)
    → Do NOT search for or add a carbohydrate course
    → Naturally occurring carbs from tool results are acceptable
    → After tool calls, set the Carbohydrates section of your output to:
      "None (intentional) — approximately [sum of carbs_g from tool results]g
       naturally occurring carbs from protein and vegetables"
    → Estimated Total Carbohydrates = sum of carbs_g from ALL tool results
      (this will typically be 5–15g and is expected and acceptable)

  Non-Veg — pick 1 protein AND 1 vegetable:
    Protein options (pick 1):
      → search_food_by_carbs(food_name="eggs",           max_carbs=2)
      → search_food_by_carbs(food_name="turkey bacon",   max_carbs=2)
      → search_food_by_carbs(food_name="smoked salmon",  max_carbs=2)
      → search_food_by_carbs(food_name="chicken sausage",max_carbs=3)
      → search_food_by_carbs(food_name="tuna",           max_carbs=1)
    Vegetable options (pick 1):
      → search_food_by_carbs(food_name="spinach",        max_carbs=5)
      → search_food_by_carbs(food_name="kale",           max_carbs=5)
      → search_food_by_carbs(food_name="mushrooms",      max_carbs=4)
      → search_food_by_carbs(food_name="bell pepper",    max_carbs=6)
      → search_food_by_carbs(food_name="zucchini",       max_carbs=4)
      → search_food_by_carbs(food_name="tomatoes",       max_carbs=5)

  Veg — pick 1 protein AND 1 vegetable:
    Protein options (pick 1):
      → search_food_by_carbs(food_name="eggs",           max_carbs=2)
      → search_food_by_carbs(food_name="paneer",         max_carbs=3)
      → search_food_by_carbs(food_name="cottage cheese", max_carbs=4)
      → search_food_by_carbs(food_name="Greek yogurt",   max_carbs=6)
      → search_food_by_carbs(food_name="tofu",           max_carbs=3)
    Vegetable options (pick 1):
      → search_food_by_carbs(food_name="spinach",        max_carbs=5)
      → search_food_by_carbs(food_name="kale",           max_carbs=5)
      → search_food_by_carbs(food_name="mushrooms",      max_carbs=4)
      → search_food_by_carbs(food_name="bell pepper",    max_carbs=6)
      → search_food_by_carbs(food_name="tomatoes",       max_carbs=5)

  Vegan — pick 1 protein AND 1 vegetable:
    Protein options (pick 1):
      → search_food_by_carbs(food_name="tofu",           max_carbs=3)
      → search_food_by_carbs(food_name="tempeh",         max_carbs=5)
      → search_food_by_carbs(food_name="edamame",        max_carbs=8)
      → search_food_by_carbs(food_name="hemp seeds",     max_carbs=2)
    Vegetable options (pick 1):
      → search_food_by_carbs(food_name="spinach",        max_carbs=5)
      → search_food_by_carbs(food_name="avocado",        max_carbs=5)
      → search_food_by_carbs(food_name="kale",           max_carbs=5)
      → search_food_by_carbs(food_name="mushrooms",      max_carbs=4)
      → search_food_by_carbs(food_name="tomatoes",       max_carbs=5)

IF glucose 70–150 (NORMAL — balanced breakfast, carbs allowed):

  Non-Veg — pick 1 protein, 1 vegetable, 1 carbohydrate:
    Protein options (pick 1):
      → search_food_by_carbs(food_name="eggs",           max_carbs=2)
      → search_food_by_carbs(food_name="turkey bacon",   max_carbs=2)
      → search_food_by_carbs(food_name="smoked salmon",  max_carbs=2)
      → search_food_by_carbs(food_name="chicken sausage",max_carbs=3)
      → search_food_by_carbs(food_name="Greek yogurt",   max_carbs=8)
    Vegetable options (pick 1):
      → search_food_by_carbs(food_name="spinach",        max_carbs=5)
      → search_food_by_carbs(food_name="mushrooms",      max_carbs=4)
      → search_food_by_carbs(food_name="tomatoes",       max_carbs=5)
      → search_food_by_carbs(food_name="bell pepper",    max_carbs=6)
    Carbohydrate options (pick 1):
      → search_food_by_carbs(food_name="oatmeal",  min_carbs=30,      max_carbs=45)
      → search_food_by_carbs(food_name="whole wheat toast",min_carbs=30,      max_carbs=40)
      → search_food_by_carbs(food_name="blueberry",    min_carbs=30,      max_carbs=40)
      → search_food_by_carbs(food_name="banana",         min_carbs=30,      max_carbs=40)
    

  Veg — pick 1 protein, 1 vegetable, 1 carbohydrate:
    Protein options (pick 1):
      → search_food_by_carbs(food_name="eggs",           max_carbs=2)
      → search_food_by_carbs(food_name="Greek yogurt",   max_carbs=8)
      → search_food_by_carbs(food_name="cottage cheese", max_carbs=6)
      → search_food_by_carbs(food_name="paneer",         max_carbs=3)
      → search_food_by_carbs(food_name="tofu",           max_carbs=3)
    Vegetable options (pick 1):
      → search_food_by_carbs(food_name="spinach",        max_carbs=5)
      → search_food_by_carbs(food_name="mushrooms",      max_carbs=4)
      → search_food_by_carbs(food_name="tomatoes",       max_carbs=5)
      → search_food_by_carbs(food_name="kale",           max_carbs=5)
    Carbohydrate options (pick 1):
      → search_food_by_carbs(food_name="oatmeal",       min_carbs=30,      max_carbs=45)
      → search_food_by_carbs(food_name="whole wheat toast",min_carbs=30,      max_carbs=40)
      → search_food_by_carbs(food_name="blueberry",   min_carbs=30,      max_carbs=40) 
      → search_food_by_carbs(food_name="banana",         min_carbs=30,      max_carbs=40)


  Vegan — pick 1 protein, 1 vegetable, 1 carbohydrate:
    Protein options (pick 1):
      → search_food_by_carbs(food_name="tofu",           max_carbs=3)
      → search_food_by_carbs(food_name="tempeh",         max_carbs=5)
      → search_food_by_carbs(food_name="hemp seeds",     max_carbs=2)
      → search_food_by_carbs(food_name="edamame",        max_carbs=8)
      → search_food_by_carbs(food_name="peanut butter",  max_carbs=6)
    Vegetable options (pick 1):
      → search_food_by_carbs(food_name="spinach",        max_carbs=5)
      → search_food_by_carbs(food_name="avocado",        max_carbs=5)
      → search_food_by_carbs(food_name="kale",           max_carbs=5)
      → search_food_by_carbs(food_name="mushrooms",      max_carbs=4)
    Carbohydrate options (pick 1):
      → search_food_by_carbs(food_name="oatmeal",        min_carbs=30,      max_carbs=45)
      → search_food_by_carbs(food_name="whole wheat toast",min_carbs=30,      max_carbs=40)
      → search_food_by_carbs(food_name="blueberry",    min_carbs=30,      max_carbs=40)
      → search_food_by_carbs(food_name="banana",         min_carbs=30,      max_carbs=40)
      
IF glucose < 70 (LOW — fast-acting carbs, any diet):
      → search_food_by_carbs(food_name="orange juice", min_carbs=15,  max_carbs=20)
      → search_food_by_carbs(food_name="soda pop",min_carbs=15, max_carbs=20)
      → search_food_by_carbs(food_name="banana",  min_carbs=15,  max_carbs=20)
      → search_food_by_carbs(food_name="apple juice",  min_carbs=14,  max_carbs=20)
      → search_food_by_carbs(food_name="fruit juice", min_carbs=15, max_carbs=20)

──────────────────────────────────────────────────────────
LUNCH (meal_type = Lunch)
──────────────────────────────────────────────────────────

IF glucose > 150 (HIGH — protein + veg only):

    → Search for protein and vegetable options only (as listed below)
    → Do NOT search for or add a carbohydrate course
    → Naturally occurring carbs from tool results are acceptable
    → After tool calls, set the Carbohydrates section of your output to:
      "None (intentional) — approximately [sum of carbs_g from tool results]g
       naturally occurring carbs from protein and vegetables"
    → Estimated Total Carbohydrates = sum of carbs_g from ALL tool results
      (this will typically be 5–15g and is expected and acceptable)

  Non-Veg — pick 1 protein AND 1 vegetable:
    Protein options (pick 1):
      → search_food_by_carbs(food_name="chicken breast",       max_carbs=2)
      → search_food_by_carbs(food_name="tuna",                 max_carbs=1)
      → search_food_by_carbs(food_name="turkey breast",        max_carbs=2)
      → search_food_by_carbs(food_name="shrimp",               max_carbs=2)
      → search_food_by_carbs(food_name="salmon",               max_carbs=2)
      → search_food_by_carbs(food_name="tilapia",              max_carbs=1)
      → search_food_by_carbs(food_name="ground turkey",        max_carbs=2)
    Vegetable options (pick 1):
      → search_food_by_carbs(food_name="broccoli",             max_carbs=7)
      → search_food_by_carbs(food_name="spinach",              max_carbs=5)
      → search_food_by_carbs(food_name="cucumber",             max_carbs=4)
      → search_food_by_carbs(food_name="zucchini",             max_carbs=4)
      → search_food_by_carbs(food_name="cauliflower",          max_carbs=6)
      → search_food_by_carbs(food_name="green beans",          max_carbs=7)
      → search_food_by_carbs(food_name="asparagus",            max_carbs=5)
      → search_food_by_carbs(food_name="celery",               max_carbs=3)
      → search_food_by_carbs(food_name="lettuce",              max_carbs=3)

  Veg — pick 1 protein AND 1 vegetable:
    Protein options (pick 1):
      → search_food_by_carbs(food_name="paneer",               max_carbs=3)
      → search_food_by_carbs(food_name="tofu",                 max_carbs=3)
      → search_food_by_carbs(food_name="cottage cheese",       max_carbs=4)
      → search_food_by_carbs(food_name="Greek yogurt",         max_carbs=6)
      → search_food_by_carbs(food_name="eggs",                 max_carbs=2)
      → search_food_by_carbs(food_name="cheese",               max_carbs=2)
    Vegetable options (pick 1):
      → search_food_by_carbs(food_name="broccoli",             max_carbs=7)
      → search_food_by_carbs(food_name="spinach",              max_carbs=5)
      → search_food_by_carbs(food_name="cauliflower",          max_carbs=6)
      → search_food_by_carbs(food_name="zucchini",             max_carbs=4)
      → search_food_by_carbs(food_name="cucumber",             max_carbs=4)
      → search_food_by_carbs(food_name="green beans",          max_carbs=7)
      → search_food_by_carbs(food_name="asparagus",            max_carbs=5)

  Vegan — pick 1 protein AND 1 vegetable:
    Protein options (pick 1):
      → search_food_by_carbs(food_name="tofu",                 max_carbs=3)
      → search_food_by_carbs(food_name="tempeh",               max_carbs=5)
      → search_food_by_carbs(food_name="edamame",              max_carbs=8)
      → search_food_by_carbs(food_name="black beans",          max_carbs=10)
      → search_food_by_carbs(food_name="chickpeas",            max_carbs=10)
    Vegetable options (pick 1):
      → search_food_by_carbs(food_name="broccoli",             max_carbs=7)
      → search_food_by_carbs(food_name="spinach",              max_carbs=5)
      → search_food_by_carbs(food_name="cauliflower",          max_carbs=6)
      → search_food_by_carbs(food_name="zucchini",             max_carbs=4)
      → search_food_by_carbs(food_name="kale",                 max_carbs=5)
      → search_food_by_carbs(food_name="asparagus",            max_carbs=5)

IF glucose 70–150 (NORMAL — balanced lunch, carbs allowed):

  Non-Veg — pick 1 protein, 1 vegetable, 1 carbohydrate:
    Protein options (pick 1):
      → search_food_by_carbs(food_name="chicken breast",       max_carbs=2)
      → search_food_by_carbs(food_name="tuna",                 max_carbs=1)
      → search_food_by_carbs(food_name="turkey breast",        max_carbs=2)
      → search_food_by_carbs(food_name="shrimp",               max_carbs=2)
      → search_food_by_carbs(food_name="salmon",               max_carbs=2)
      → search_food_by_carbs(food_name="tilapia",              max_carbs=1)
      → search_food_by_carbs(food_name="ground turkey",        max_carbs=2)
    Vegetable options (pick 1):
      → search_food_by_carbs(food_name="broccoli",             max_carbs=7)
      → search_food_by_carbs(food_name="spinach",              max_carbs=5)
      → search_food_by_carbs(food_name="cucumber",             max_carbs=4)
      → search_food_by_carbs(food_name="mixed salad greens",   max_carbs=5)
      → search_food_by_carbs(food_name="green beans",          max_carbs=7)
      → search_food_by_carbs(food_name="asparagus",            max_carbs=5)
      → search_food_by_carbs(food_name="zucchini",             max_carbs=4)
    Carbohydrate options (pick 1):
      → search_food_by_carbs(food_name="brown rice",           max_carbs=40,min_carbs=30)
      → search_food_by_carbs(food_name="whole wheat chapati" , max_carbs=45,min_carbs=30)
      → search_food_by_carbs(food_name="sweet potato",         max_carbs=40,min_carbs=30)
      → search_food_by_carbs(food_name="whole wheat bread",    max_carbs=45,min_carbs=30)
      → search_food_by_carbs(food_name="corn",                 max_carbs=40,min_carbs=30)

  Veg — pick 1 protein, 1 vegetable, 1 carbohydrate:
    Protein options (pick 1):
      → search_food_by_carbs(food_name="paneer",               max_carbs=3)
      → search_food_by_carbs(food_name="tofu",                 max_carbs=3)
      → search_food_by_carbs(food_name="cottage cheese",       max_carbs=4)
      → search_food_by_carbs(food_name="eggs",                 max_carbs=2)
      → search_food_by_carbs(food_name="lentils",              max_carbs=20)
      → search_food_by_carbs(food_name="chickpeas",            max_carbs=20)
      → search_food_by_carbs(food_name="kidney beans",         max_carbs=20)
    Vegetable options (pick 1):
      → search_food_by_carbs(food_name="spinach",              max_carbs=5)
      → search_food_by_carbs(food_name="broccoli",             max_carbs=7)
      → search_food_by_carbs(food_name="cauliflower",          max_carbs=6)
      → search_food_by_carbs(food_name="mixed salad greens",   max_carbs=5)
      → search_food_by_carbs(food_name="cucumber",             max_carbs=4)
      → search_food_by_carbs(food_name="zucchini",             max_carbs=4)
    Carbohydrate options (pick 1):
      → search_food_by_carbs(food_name="brown rice",           max_carbs=40,min_carbs=30)
      → search_food_by_carbs(food_name="whole wheat chapati" , max_carbs=45,min_carbs=30)
      → search_food_by_carbs(food_name="sweet potato",         max_carbs=40,min_carbs=30)
      → search_food_by_carbs(food_name="whole wheat bread",    max_carbs=45,min_carbs=30)
      → search_food_by_carbs(food_name="corn",                 max_carbs=40,min_carbs=30)
      

 Vegan — pick 1 protein, 1 vegetable, 1 carbohydrate:
    Protein options (pick 1):
      → search_food_by_carbs(food_name="tofu",                 max_carbs=3)
      → search_food_by_carbs(food_name="tempeh",               max_carbs=5)
      → search_food_by_carbs(food_name="black beans",          max_carbs=20)
      → search_food_by_carbs(food_name="chickpeas",            max_carbs=20)
      → search_food_by_carbs(food_name="lentils",              max_carbs=20)
      → search_food_by_carbs(food_name="edamame",              max_carbs=8)
    Vegetable options (pick 1):
      → search_food_by_carbs(food_name="broccoli",             max_carbs=7)
      → search_food_by_carbs(food_name="kale",                 max_carbs=5)
      → search_food_by_carbs(food_name="spinach",              max_carbs=5)
      → search_food_by_carbs(food_name="cauliflower",          max_carbs=6)
      → search_food_by_carbs(food_name="zucchini",             max_carbs=4)
      → search_food_by_carbs(food_name="mixed salad greens",   max_carbs=5)
    Carbohydrate options (pick 1):
      → search_food_by_carbs(food_name="brown rice",           max_carbs=40,min_carbs=30)
      → search_food_by_carbs(food_name="whole wheat chapati" , max_carbs=45,min_carbs=30)
      → search_food_by_carbs(food_name="sweet potato",         max_carbs=40,min_carbs=30)
      → search_food_by_carbs(food_name="whole wheat bread",    max_carbs=45,min_carbs=30)
      → search_food_by_carbs(food_name="corn",                 max_carbs=40,min_carbs=30)

IF glucose < 70 (LOW — fast-acting carbs, any diet):
      → search_food_by_carbs(food_name="orange juice", min_carbs=15,  max_carbs=20)
      → search_food_by_carbs(food_name="soda pop",min_carbs=15, max_carbs=20)
      → search_food_by_carbs(food_name="banana",  min_carbs=15,  max_carbs=20)
      → search_food_by_carbs(food_name="apple juice",  min_carbs=14,  max_carbs=20)
      → search_food_by_carbs(food_name="fruit juice", min_carbs=15, max_carbs=20)

──────────────────────────────────────────────────────────
DINNER (meal_type = Dinner)
──────────────────────────────────────────────────────────

IF glucose > 150 (HIGH — protein + veg only):

    → Search for protein and vegetable options only (as listed below)
    → Do NOT search for or add a carbohydrate course
    → Naturally occurring carbs from tool results are acceptable
    → After tool calls, set the Carbohydrates section of your output to:
      "None (intentional) — approximately [sum of carbs_g from tool results]g
       naturally occurring carbs from protein and vegetables"
    → Estimated Total Carbohydrates = sum of carbs_g from ALL tool results
      (this will typically be 5–15g and is expected and acceptable)

  Non-Veg — pick 1 protein AND 1 vegetable:
    Protein options (pick 1):
      → search_food_by_carbs(food_name="salmon",               max_carbs=2)
      → search_food_by_carbs(food_name="chicken breast",       max_carbs=2)
      → search_food_by_carbs(food_name="tilapia",              max_carbs=1)
      → search_food_by_carbs(food_name="shrimp",               max_carbs=2)
      → search_food_by_carbs(food_name="turkey breast",        max_carbs=2)
      → search_food_by_carbs(food_name="tuna steak",           max_carbs=1)
      → search_food_by_carbs(food_name="cod",                  max_carbs=1)
      → search_food_by_carbs(food_name="lean beef",            max_carbs=2)
    Vegetable options (pick 1):
      → search_food_by_carbs(food_name="asparagus",            max_carbs=5)
      → search_food_by_carbs(food_name="zucchini",             max_carbs=4)
      → search_food_by_carbs(food_name="broccoli",             max_carbs=7)
      → search_food_by_carbs(food_name="cauliflower",          max_carbs=6)
      → search_food_by_carbs(food_name="Brussels sprouts",     max_carbs=8)
      → search_food_by_carbs(food_name="green beans",          max_carbs=7)
      → search_food_by_carbs(food_name="spinach",              max_carbs=5)
      → search_food_by_carbs(food_name="cabbage",              max_carbs=5)
      → search_food_by_carbs(food_name="eggplant",             max_carbs=6)

  Veg — pick 1 protein AND 1 vegetable:
    Protein options (pick 1):
      → search_food_by_carbs(food_name="paneer",               max_carbs=3)
      → search_food_by_carbs(food_name="cottage cheese",       max_carbs=4)
      → search_food_by_carbs(food_name="tofu",                 max_carbs=3)
      → search_food_by_carbs(food_name="eggs",                 max_carbs=2)
      → search_food_by_carbs(food_name="cheese",               max_carbs=2)
      → search_food_by_carbs(food_name="Greek yogurt",         max_carbs=6)
    Vegetable options (pick 1):
      → search_food_by_carbs(food_name="asparagus",            max_carbs=5)
      → search_food_by_carbs(food_name="zucchini",             max_carbs=4)
      → search_food_by_carbs(food_name="broccoli",             max_carbs=7)
      → search_food_by_carbs(food_name="cauliflower",          max_carbs=6)
      → search_food_by_carbs(food_name="Brussels sprouts",     max_carbs=8)
      → search_food_by_carbs(food_name="spinach",              max_carbs=5)
      → search_food_by_carbs(food_name="eggplant",             max_carbs=6)

  Vegan — pick 1 protein AND 1 vegetable:
    Protein options (pick 1):
      → search_food_by_carbs(food_name="tempeh",               max_carbs=5)
      → search_food_by_carbs(food_name="tofu",                 max_carbs=3)
      → search_food_by_carbs(food_name="lentils",              max_carbs=10)
      → search_food_by_carbs(food_name="black beans",          max_carbs=10)
      → search_food_by_carbs(food_name="edamame",              max_carbs=8)
      → search_food_by_carbs(food_name="chickpeas",            max_carbs=10)
    Vegetable options (pick 1):
      → search_food_by_carbs(food_name="asparagus",            max_carbs=5)
      → search_food_by_carbs(food_name="zucchini",             max_carbs=4)
      → search_food_by_carbs(food_name="broccoli",             max_carbs=7)
      → search_food_by_carbs(food_name="cauliflower",          max_carbs=6)
      → search_food_by_carbs(food_name="Brussels sprouts",     max_carbs=8)
      → search_food_by_carbs(food_name="kale",                 max_carbs=5)
      → search_food_by_carbs(food_name="eggplant",             max_carbs=6)

IF glucose 70–150 (NORMAL — balanced dinner, carbs allowed):

  Non-Veg — pick 1 protein, 1 vegetable, 1 carbohydrate:
    Protein options (pick 1):
      → search_food_by_carbs(food_name="salmon",               max_carbs=2)
      → search_food_by_carbs(food_name="chicken breast",       max_carbs=2)
      → search_food_by_carbs(food_name="tilapia",              max_carbs=1)
      → search_food_by_carbs(food_name="shrimp",               max_carbs=2)
      → search_food_by_carbs(food_name="turkey breast",        max_carbs=2)
      → search_food_by_carbs(food_name="tuna steak",           max_carbs=1)
      → search_food_by_carbs(food_name="cod",                  max_carbs=1)
      → search_food_by_carbs(food_name="lean beef",            max_carbs=2)
    Vegetable options (pick 1):
      → search_food_by_carbs(food_name="asparagus",            max_carbs=5)
      → search_food_by_carbs(food_name="broccoli",             max_carbs=7)
      → search_food_by_carbs(food_name="zucchini",             max_carbs=4)
      → search_food_by_carbs(food_name="green beans",          max_carbs=7)
      → search_food_by_carbs(food_name="Brussels sprouts",     max_carbs=8)
      → search_food_by_carbs(food_name="spinach",              max_carbs=5)
      → search_food_by_carbs(food_name="cabbage",              max_carbs=5)
      → search_food_by_carbs(food_name="eggplant",             max_carbs=6)
    Carbohydrate options (pick 1):
      → search_food_by_carbs(food_name="brown rice",           max_carbs=40,min_carbs=30)
      → search_food_by_carbs(food_name="whole wheat chapati" , max_carbs=45,min_carbs=30)
      → search_food_by_carbs(food_name="sweet potato",         max_carbs=40,min_carbs=30)
      → search_food_by_carbs(food_name="whole wheat bread",    max_carbs=45,min_carbs=30)
      → search_food_by_carbs(food_name="corn",                 max_carbs=40,min_carbs=30)

  Veg — pick 1 protein, 1 vegetable, 1 carbohydrate:
    Protein options (pick 1):
      → search_food_by_carbs(food_name="paneer",               max_carbs=3)
      → search_food_by_carbs(food_name="tofu",                 max_carbs=3)
      → search_food_by_carbs(food_name="cottage cheese",       max_carbs=4)
      → search_food_by_carbs(food_name="eggs",                 max_carbs=2)
      → search_food_by_carbs(food_name="lentils",              max_carbs=20)
      → search_food_by_carbs(food_name="kidney beans",         max_carbs=20)
      → search_food_by_carbs(food_name="chickpeas",            max_carbs=20)
    Vegetable options (pick 1):
      → search_food_by_carbs(food_name="asparagus",            max_carbs=5)
      → search_food_by_carbs(food_name="broccoli",             max_carbs=7)
      → search_food_by_carbs(food_name="cauliflower",          max_carbs=6)
      → search_food_by_carbs(food_name="spinach",              max_carbs=5)
      → search_food_by_carbs(food_name="eggplant",             max_carbs=6)
      → search_food_by_carbs(food_name="zucchini",             max_carbs=4)
      → search_food_by_carbs(food_name="Brussels sprouts",     max_carbs=8)
    Carbohydrate options (pick 1):
      → search_food_by_carbs(food_name="brown rice",           max_carbs=40,min_carbs=30)
      → search_food_by_carbs(food_name="whole wheat chapati" , max_carbs=45,min_carbs=30)
      → search_food_by_carbs(food_name="sweet potato",         max_carbs=40,min_carbs=30)
      → search_food_by_carbs(food_name="whole wheat bread",    max_carbs=45,min_carbs=30)
      → search_food_by_carbs(food_name="corn",                 max_carbs=40,min_carbs=30)

  Vegan — pick 1 protein, 1 vegetable, 1 carbohydrate:
    Protein options (pick 1):
      → search_food_by_carbs(food_name="tempeh",               max_carbs=5)
      → search_food_by_carbs(food_name="tofu",                 max_carbs=3)
      → search_food_by_carbs(food_name="lentils",              max_carbs=20)
      → search_food_by_carbs(food_name="black beans",          max_carbs=20)
      → search_food_by_carbs(food_name="chickpeas",            max_carbs=20)
      → search_food_by_carbs(food_name="edamame",              max_carbs=8)
    Vegetable options (pick 1):
      → search_food_by_carbs(food_name="asparagus",            max_carbs=5)
      → search_food_by_carbs(food_name="broccoli",             max_carbs=7)
      → search_food_by_carbs(food_name="kale",                 max_carbs=5)
      → search_food_by_carbs(food_name="Brussels sprouts",     max_carbs=8)
      → search_food_by_carbs(food_name="cauliflower",          max_carbs=6)
      → search_food_by_carbs(food_name="eggplant",             max_carbs=6)
      → search_food_by_carbs(food_name="zucchini",             max_carbs=4)
    Carbohydrate options (pick 1):
      → search_food_by_carbs(food_name="brown rice",           max_carbs=40,min_carbs=30)
      → search_food_by_carbs(food_name="whole wheat chapati" , max_carbs=45,min_carbs=30)
      → search_food_by_carbs(food_name="sweet potato",         max_carbs=40,min_carbs=30)
      → search_food_by_carbs(food_name="whole wheat bread",    max_carbs=45,min_carbs=30)
      → search_food_by_carbs(food_name="corn",                 max_carbs=40,min_carbs=30)

IF glucose < 70 (LOW — fast-acting carbs, any diet):
      → search_food_by_carbs(food_name="orange juice", min_carbs=15,  max_carbs=20)
      → search_food_by_carbs(food_name="soda pop",min_carbs=15, max_carbs=20)
      → search_food_by_carbs(food_name="banana",  min_carbs=15,  max_carbs=20)
      → search_food_by_carbs(food_name="apple juice",  min_carbs=14,  max_carbs=20)
      → search_food_by_carbs(food_name="fruit juice", min_carbs=15, max_carbs=20)

──────────────────────────────────────────────────────────
FALLBACK RULE (applies to all meal types)
──────────────────────────────────────────────────────────
  If search_food_by_carbs returns {} for selected food:
    → Try the next option in the same category
    → Work through the list until a result is returned
    → Never use training knowledge for food data
    → Never skip the tool call entirely
    → Never recommend a food that violates diet preference
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP 5 — APPLY DECISION RULES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Hypoglycemia (glucose < 70 mg/dL):
  - Recommend 15g fast-acting carbohydrates from tool results
  - Wait 15 minutes → recheck glucose
  - If still below 70 → repeat 15g treatment
  - After glucose > 70 → recommend balanced diet-compliant meal

Hyperglycemia hydration (glucose > 180 mg/dL):
  - Recommend 500mL–1L of water

Carbohydrate impact rule:
  - Every 10g carbohydrates raises glucose ~30–50 mg/dL
  - Select portions keeping predicted glucose within 90–150 mg/dL

Medication timing:
  - If user recently took insulin or oral medication →
    recommend eating 15 minutes after medication intake

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP 6 — BUILD RESPONSE FROM TOOL RESULTS ONLY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Use ONLY foods returned by search_food_by_carbs.
Include per food: name, serving size, carbs_g, protein_g, calories_kcal.
Do not invent or estimate nutritional values.
Always confirm diet compliance before including a food in the response.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OUTPUT FORMAT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Diet Preference: [Non-Veg / Veg / Vegan / Gluten-Free]

Glucose Status: [High / Normal / Low]

Hydration Recommendation:
[specific amount and reason, or "None required"]

Meal Recommendation ([Breakfast / Lunch / Dinner]):

Protein:
[food from tool] — [serving size]g | Protein: [protein_g]g | 
Carbs: [carbs_g]g | Calories: [calories_kcal] kcal

Vegetables:
[food from tool] — [serving size]g | Carbs: [carbs_g]g | 
Calories: [calories_kcal] kcal

Carbohydrates:
  [If glucose > 150]:
    "None (intentional) — approximately [total carbs_g from tool results]g
     naturally occurring carbs from protein and vegetables only.
     No grain, bread, rice, fruit, or starchy carbs included."

  [If glucose 70–150]:
    [carbohydrate food from tool] — [serving size] |
    Carbs: [carbs_g]g | Calories: [calories_kcal] kcal

  [If glucose < 70]:
    [fast-acting carb food from tool] — eat immediately to raise glucose

Estimated Total Carbohydrates: [sum] grams

Additional Guidance:
[recheck glucose / medication timing / any relevant note]
""",
    tools=[search_food_by_carbs]
)

#MealAgent_logger.info(f"MealAgent Output: {MealAgent_recommendation}")
#MealAgent = create_meal_agent()
print("✅ MealAgent created.")

# ─── SECTION 8: EXERCISE AGENT ───────────────────────────────────────────────

import pandas as pd

def get_exercise_intensity(glucose_level: int) -> list:
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
    df = pd.read_csv("traincalc-met-values-latest.csv")
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

def get_exercise_recommendation(
    glucose_level: int,
    minutes_since_last_meal: int = None,
    last_meal_carbs: int = None,
    upcoming_meal_carbs: int = None
) -> dict:
    """
    glucose_level: current_glucose from predict_glucose() tool (column C, mg/dL).
    Ground-truth current glucose. NOT glucose_at_meal_time.

    Exercise glucose effect:
      Light    → LOWERS glucose → exercise_fall_mgdl = +10
      Moderate → LOWERS glucose → exercise_fall_mgdl = +20
      Vigorous → RAISES glucose → exercise_fall_mgdl = -20
      Avoid    → no exercise   → exercise_fall_mgdl = 0
    """
    plan = get_exercise_intensity_by_meal(
        glucose_level, minutes_since_last_meal,
        last_meal_carbs, upcoming_meal_carbs
    )

    if plan.get("status") == "unsafe" or "Avoid" in plan.get("intensity", []):
        return {
            "status":                  "unsafe",
            "max_intensity":           "Avoid",
            "exercise_glucose_effect": "none",
            "exercise_fall_mgdl":      0,
            "message":     "Glucose level not suitable for exercise",
            "pre_exercise": "Consume carbohydrates and recheck glucose",
            "plan": plan
        }

    intensity_levels = list(plan.get("intensity", []))

    def get_max_intensity(intensity_list):
        if "Vigorous" in intensity_list: return "Vigorous"
        elif "Moderate" in intensity_list: return "Moderate"
        elif "Light" in intensity_list: return "Light"
        else: return "Avoid"

    max_intensity = get_max_intensity(intensity_levels)

    # Positive = glucose FALLS (light/moderate lower glucose)
    # Negative = glucose RISES (vigorous raises glucose via HIIT/strength spike)
    effect_map = {
        "Light":    +10,
        "Moderate": +20,
        "Vigorous": -20,
        "Avoid":      0
    }

    intensity_effect = effect_map.get(max_intensity, 0)
    pre_meal_effect  = +10 if plan.get("pre_meal_strategy") else 0
    total_fall       = intensity_effect + pre_meal_effect

    glucose_effect_label = (
        "raises glucose" if total_fall < 0  else
        "lowers glucose" if total_fall > 0  else
        "neutral"
    )

    all_exercises = []
    for level in intensity_levels:
        exercises = search_exercise_by_intensity(level)
        for e in exercises:
            all_exercises.append({
                "description": e["Description"],
                "met":         e["MET"],
                "intensity":   level
            })

    return {
        "status":                  "ok",
        "max_intensity":           max_intensity,
        "exercise_glucose_effect": glucose_effect_label,
        "exercise_fall_mgdl":      total_fall,
        "recommended_exercises":   all_exercises,
        "plan":                    plan
    }

ExerciseAgent = Agent(
    name='ExerciseRecommenderAgent',
    model=Gemini(model='gemini-2.5-flash-lite', retry_options=retry_config),
    description="Given glucose level, recommend appropriate exercise",
    instruction="""
    You are an expert Diabetes Exercise Coach. Your task is to recommend appropriate
    exercises based on the patient's glucose level. Use the provided
    get_exercise_recommendation tool to determine suitable exercises based on the
    glucose level and if available, the timing and carbohydrate content of recent
    and upcoming meals. Then give a recommendation of exercise types, specific
    exercises, and duration that the patient can do to help manage their blood
    glucose levels effectively. Be sure to consider the patient's safety and
    recommend NO exercise if glucose levels are too low or too high.

    IMPORTANT: The glucose_level you receive is current_glucose from the prediction
    model (column C, mg/dL). Ground-truth current reading. Use it directly for all
    safety checks. NOT glucose_at_meal_time.

    GLUCOSE EFFECT OF EXERCISE:
      Light exercise    → LOWERS blood glucose
      Moderate exercise → LOWERS blood glucose
      Vigorous exercise → RAISES blood glucose (strength training and HIIT
                          cause a glucose spike due to stress hormones)

    Guidelines:
    Lower than 90 mg/dL: Blood sugar may be too low to exercise safely.
      Have 15–30g carbohydrates first. Recheck after exercise.
    90–124 mg/dL: Take 10g glucose before exercising.
    125–180 mg/dL: Ready to exercise. Strength training or HIIT may RAISE blood sugar.
    181–270 mg/dL: Okay to exercise. Monitor for glucose rise.
    Over 270 mg/dL: Caution zone. Test urine for ketones before exercising.

    AFTER calling get_exercise_recommendation:
      YOU MUST always produce a text response. Never return empty content.
      Always state the glucose effect:
        - If Light or Moderate: "This exercise will help LOWER your glucose."
        - If Vigorous: "Note: Vigorous exercise may RAISE your glucose."
    """,
    tools=[get_exercise_recommendation],
)
print("✅ ExerciseAgent created.")


# ─── SECTION 9: SAFETY AGENT ─────────────────────────────────────────────────

SafetyAgent = Agent(
    name="SafetyGuard",
    model=Gemini(model='gemini-2.5-flash', retry_options=retry_config),
    output_key="judge_output",
    description="Evaluates the output of Main_agent for clinical safety and logical consistency",
    instruction="""
You are a clinical safety validation agent for a glucose management system.

You will receive a JSON object where Output_Summary is a structured object.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FIELDS TO READ FROM Output_Summary
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Read ALL of the following fields:
  - user_information (insulin, oral_medication, long acting Insulin, glp1, diet)
  - current_glucose
  - glucose_at_meal_time
  - glucose_at_meal_time_source        ("predicted" or "current")
  - max_predicted_glucose
  - min_predicted_glucose
  - minutes_since_last_meal
  - has_meal_taken_around_current_time
  - carb_rule               ← "HIGH" / "NORMAL" / "LOW"
  - meal_carbs_estimate
  - meal_recommendation
  - insulin_recommendation             ({ "units": <number>, "timing": <string> })
  - exercise_recommendation            ({ "status", "intensity", "duration",
                                          "focus", "suggested_exercises",
                                          "pre_meal_strategy", "safety_note" })
  - medication_recommendation
  - safety_notes

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
GLUCOSE REFERENCE VALUES FOR VALIDATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Use these values in order of priority for validation:

  1. glucose_at_meal_time  ← PRIMARY — use this for insulin and meal validation
     (this is the predicted glucose AT the time of the meal, or current if
      meal already passed)

  2. current_glucose       ← use for exercise validation and general safety checks

  3. min_predicted_glucose ← use to detect future hypoglycemia risk
  4. max_predicted_glucose ← use to detect future hyperglycemia risk

NEVER use only current_glucose when glucose_at_meal_time is available.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RULE 1 — INSULIN VALIDATION (MOST CRITICAL)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Use glucose_at_meal_time for all insulin dosing checks.

Insulin dosing rules:
  glucose_at_meal_time < 70    → units = 0, timing = "not required"
                                  (hypoglycemia — never give insulin)
  glucose_at_meal_time 70–150  → units = 0, timing = "not required"
                                  (in range — no correction dose needed)
  glucose_at_meal_time 151–200 → units = 2, timing = "before <meal>"
  glucose_at_meal_time 201–250 → units = 4, timing = "before <meal>"
  glucose_at_meal_time 251–300 → units = 6, timing = "before <meal>"
  glucose_at_meal_time 301–350 → units = 8, timing = "before <meal>"
  glucose_at_meal_time 351–400 → units = 10, timing = "before <meal>"
  glucose_at_meal_time > 400   → advise contacting doctor immediately

VIOLATION if ANY of the following:
  - insulin = 'yes' AND has_meal_taken_around_current_time = False
    AND glucose_at_meal_time > 150
    AND insulin_recommendation.units is null, 0, or wrong value
  - insulin_recommendation.units is null            (null is always an error)
  - insulin_recommendation.timing is null           (null is always an error)
  - units do not match the dosing rules above
  - insulin recommended AFTER meal already taken
    (has_meal_taken_around_current_time = True AND minutes_since_last_meal < 60)
  - insulin recommended during hypoglycemia
    (glucose_at_meal_time < 70 AND units > 0)

CARB-INSULIN CONSISTENCY CHECK:
  - glucose_at_meal_time > 150
    AND meal_carbs_estimate > 20
    AND insulin_recommendation.units < expected units per dosing rules above
    → VIOLATION: intentional carbs detected (meal_carbs_estimate > 20g
      suggests a carbohydrate course was included) but insulin dose does
      not account for the additional carb load.
      Insulin dose may need to be reviewed upward.

DO NOT FLAG AS VIOLATION:
   - IF the last meal has already been taken and the next meal is more than 1 hour away:
      → {units: 0, timing: "not required"}
  - glucose_at_meal_time > 150
    AND meal_carbs_estimate between 1–20g
    AND meal_recommendation contains only protein and vegetables
    → This is acceptable — naturally occurring carbs from protein and
      vegetables. Insulin dose based on glucose_at_meal_time alone
      is correct. Do NOT add a carb-related violation here.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RULE 2 — MEAL VALIDATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CRITICAl: NEVER recommend a meal if the current_time is more than 60 minues past prefrreted meal time
    
Use carb_rule field to determine what to validate.

  IF carb_rule = "HIGH" (glucose_at_meal_time > 150):

    ALLOWED:
      Protein + vegetables only
      Naturally occurring carbs 1–20g acceptable
      "None (intentional)" carb section with 1–20g estimate is correct

    VIOLATION:
      meal explicitly recommends rice, bread, pasta, oats, potatoes,
      fruit, grains, or legumes as an intentional carb course
      meal_carbs_estimate > 20g

  IF carb_rule = "NORMAL" (glucose_at_meal_time 70–150):

    EXPECTED: balanced meal with less than 40g carbohydrates
    Medication, insulin, and exercise are assumed to keep glucose
    in range — do NOT flag carb amount based on these factors.

    VIOLATION:
      
      meal_carbs_estimate > 40g
        "RULE 2 — MEAL: carb_rule=NORMAL but meal_carbs_estimate=[X]g
         exceeds expected less than 40g range for a balanced meal.
         Reduce carbohydrate portion to less than 40g."
      No intentional carbohydrate course present when carb_rule=NORMAL
        "RULE 2 — MEAL: carb_rule=NORMAL requires a carbohydrate course
         of less than 40g but none was recommended."

    NOT a violation:
      meal_carbs_estimate between 35–45g
        (5g tolerance each side of the less than 40g target)
      Any combination of medication, insulin, exercise prescribed
        (these do not affect the carb target)

  IF carb_rule = "LOW" (glucose_at_meal_time < 70):

    VIOLATION: fast-acting carbs absent
    VIOLATION: full meal recommended without fast-acting carbs first

  IF has_meal_taken_around_current_time=True
  AND minutes_since_last_meal < 60:
    VIOLATION: full meal recommended (hydration only acceptable)

  IF min_predicted_glucose < 70:
    safety_notes MUST mention hypoglycemia risk
    VIOLATION if absent

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RULE 3 — EXERCISE VALIDATION (UPDATED FOR STRUCTURED FORMAT)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

exercise_recommendation is now a structured dict with fields:
  status, intensity, duration, focus, suggested_exercises,
  pre_meal_strategy, safety_note

Validate using current_glucose AND min_predicted_glucose:

  current_glucose < 70 OR min_predicted_glucose < 70:
    → exercise_recommendation.status MUST be "unsafe"
    → VIOLATION if status = "ok" or any exercise is suggested
    → VIOLATION if exercise_recommendation is missing a safety_note

  current_glucose 70–89:
    → intensity MUST be "Light" only
    → VIOLATION if "Moderate" or "Vigorous" is recommended
    → pre_meal_strategy should suggest 10–15g carbs before exercise

  current_glucose 90–180:
    → Light, Moderate, or Vigorous all acceptable
    → No violation

  current_glucose 181–270:
    → Light or Moderate only
    → VIOLATION if "Vigorous" is recommended

  current_glucose > 270:
    → status MUST be "unsafe" or contain ketone check warning
    → VIOLATION if intense exercise recommended without ketone warning

  Timing validation:
    IF minutes_since_last_meal < 120 (within 2 hours of eating):
      → focus SHOULD be "reduce_spike" or "glucose_utilization"
      → VIOLATION if focus = "general_fitness" immediately post-meal

  Pre-meal strategy validation:
    IF has_meal_taken_around_current_time = False
    AND meal_carbs_estimate > 50:
      → pre_meal_strategy SHOULD be present
      → VIOLATION if pre_meal_strategy is null when carbs > 50

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RULE 4 — MEDICATION ALERT VALIDATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

oral_medication='pre-meal'   → must mention oral medication
  insulin='yes'                → must mention short-acting insulin
  glp1 not 'no':
    daily    → must mention GLP-1 at breakfast time
    weekly   → Extract scheduled day from glp1 value
               Extract current day from current_time
               IF scheduled day matches current day:
                 → medication_recommendation MUST mention GLP-1
                 → VIOLATION if absent
               IF scheduled day does NOT match current day:
                 → medication_recommendation MUST NOT mention weekly GLP-1
                 → VIOLATION if GLP-1 mentioned on wrong day
                   "RULE 4 — MEDICATION: weekly GLP-1 mentioned but
                    today ([current_day]) is not the scheduled injection
                    day ([scheduled_day]). Remove GLP-1 from alert."
    pre-meal → must mention before any meal

  ← UPDATED: insulin mention vs units consistency check

  PREVIOUS (WRONG):
    medication mentions insulin → units must be non-zero

  CORRECT:
    medication_recommendation may mention insulin as a REMINDER
    to take scheduled/prescribed insulin — this is NOT a correction dose.
    insulin_recommendation.units reflects CORRECTION dose only,
    based on glucose_at_meal_time dosing rules.

    These two are independent:
      - medication_recommendation = reminder alert (scheduled insulin)
      - insulin_recommendation.units = correction dose (glucose-based)

    DO NOT flag a violation if:
      - medication_recommendation mentions insulin
        AND insulin_recommendation.units = 0
        AND glucose_at_meal_time is 70–150 mg/dL
        (units=0 is CORRECT for in-range glucose — no correction needed)

    DO flag a violation if:
      - medication_recommendation mentions insulin
        AND insulin_recommendation.units = 0
        AND glucose_at_meal_time > 150
        (units=0 is WRONG for high glucose — correction dose required)

    DO flag a violation if:
      - insulin_recommendation.units is null    (always an error)
      - insulin_recommendation.timing is null   (always an error)
      - alerts or reminder for long-lasting insulin more than 1 hour away from current_time.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RULE 5 — DIET COMPLIANCE VALIDATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  IF diet = "Veg":
    → meal_recommendation MUST NOT contain:
      chicken, turkey, fish, salmon, tuna, shrimp, beef, pork,
      lamb, bacon, sausage, tilapia, cod, seafood
    → VIOLATION if any meat or seafood appears

  IF diet = "Vegan":
    → meal_recommendation MUST NOT contain:
      chicken, turkey, fish, salmon, shrimp, beef, pork, eggs,
      dairy, yogurt, paneer, cheese, butter, milk, whey
    → VIOLATION if any animal product appears

  IF diet = "Non-Veg":
    → No diet restrictions to enforce

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RULE 6 — LOGICAL CONSISTENCY VALIDATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  - Cannot recommend insulin AND hypoglycemia treatment simultaneously
  - Cannot recommend exercise AND hypoglycemia treatment simultaneously
  - Meal type and timing must be consistent:
    (e.g., cannot recommend breakfast at 7:00 PM)
  - If glucose_at_meal_time_source = "predicted":
    → insulin and meal recommendations must be based on glucose_at_meal_time
    → VIOLATION if recommendations appear to use current_glucose instead
      when glucose_at_meal_time differs significantly (>30 mg/dL difference)
  - meal_carbs_estimate consistency:
    → VIOLATION if meal explicitly says "no carbohydrates" AND
      meal_carbs_estimate = 0 (protein and veg always contribute some carbs)
    → VIOLATION if meal_carbs_estimate > 20g AND glucose > 150 AND
      no intentional carb course is listed
      (high estimate without a carb course suggests a calculation error)
    → NOT a violation if meal says "None (intentional)" AND meal_carbs_estimate is between 1–20g
      (this correctly reflects naturally occurring carbs)
  - exercise_recommendation.intensity must be consistent with glucose level
  - minutes_since_last_meal must be consistent with last_meal time and current_time

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
COMBINED SCENARIOS (CHECK IN THIS ORDER)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

If min_predicted_glucose < 70 AND max_predicted_glucose > 180:
  → Both hypo and hyper predicted
  → Prioritize hypoglycemia treatment first
  → Exercise must be "unsafe"
  → Insulin must be 0
  → Fast-acting carbs must be recommended

If current_glucose > 150 AND min_predicted_glucose < 70:
  → Currently high but will drop to hypo
  → DO NOT recommend insulin (glucose will drop on its own)
  → Light exercise only to help bring glucose down safely
  → Monitor closely — mention in safety_notes

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OUTPUT FORMAT (STRICTLY ENFORCED)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Return ONLY valid JSON. No markdown. No ```json fences. No extra text.

If SAFE:
{
  "safe": true,
  "violations": [],
  "safer_alternative": null
}

If NOT SAFE:
{
  "safe": false,
  "violations": [
    "RULE [number] — [RULE TYPE]: clear description of exactly what is wrong,
     which field is affected, and what value was found vs what was expected"
  ],
  "safer_alternative": "Exact corrections to apply. Specify EVERY field name
    and EXACT value to use. Example:
    Set insulin_recommendation to {\"units\": 2, \"timing\": \"before lunch\"}
    because glucose_at_meal_time=165 falls in 151-200 range → 2 units rule.
    Set exercise_recommendation.status to \"unsafe\" because
    min_predicted_glucose=65 < 70 threshold."
}

Rules for violations:
  - Always prefix with RULE number and type: "RULE 1 — INSULIN: ..."
  - Always state: field affected, value found, value expected
  - List every violation separately — do not combine multiple violations

Rules for safer_alternative:
  - Always specify the EXACT field name and EXACT value
  - Cover ALL violations in one safer_alternative string
  - Never be null when safe = false
  - Be specific enough that Main_agent applies the fix without ambiguity
"""
)

print("✅ SafetyAgent created.")

# ─── SECTION 10: VALIDATION DATA & PREDICTION MODEL ──────────────────────────

import numpy as np
import joblib
import random

VAL_DF_PATH  = "val_df.csv"
FEATURE_COLS = [
    'glucose', 'active_Kcal', 'percent_active',
    'intensity_num', 'activity_type_num', 'heart_rate', 'basal_dose',
    'insulin_kind', 'bolus_dose', 'carbs_g', 'prot_g', 'fat_g', 'fibre_g',
    'glucose_lag_1', 'carbs_g_lag_1', 'fat_g_lag_1', 'prot_g_lag_1',
    'fibre_g_lag_1', 'basal_dose_lag_1', 'bolus_dose_lag_1',
    'active_kcal_lag_1', 'glucose_lag_2', 'carbs_g_lag_2', 'fat_g_lag_2',
    'prot_g_lag_2', 'fibre_g_lag_2', 'basal_dose_lag_2', 'bolus_dose_lag_2',
    'active_kcal_lag_2', 'glucose_lag_3', 'carbs_g_lag_3', 'fat_g_lag_3',
    'prot_g_lag_3', 'fibre_g_lag_3', 'basal_dose_lag_3', 'bolus_dose_lag_3',
    'active_kcal_lag_3', 'glucose_lag_4', 'carbs_g_lag_4', 'fat_g_lag_4',
    'prot_g_lag_4', 'fibre_g_lag_4', 'basal_dose_lag_4', 'bolus_dose_lag_4',
    'active_kcal_lag_4', 'glucose_mean_1hr', 'carbs_sum_1hr', 'fat_sum_1hr',
    'prot_sum_1hr', 'fibre_sum_1hr', 'basal_dose_sum_1hr',
    'bolus_dose_sum_1hr', 'active_kcal_sum_1hr'
]

val_df = pd.read_csv(VAL_DF_PATH)
print(f"✅ Validation data loaded: {len(val_df)} rows, {len(FEATURE_COLS)} features")

real_model = joblib.load("model_2301.joblib")
print("✅ Prediction model loaded")


def interpolate_to_15min(current_glucose: float, predicted_glucose: float) -> list:
    """
    Interpolate between current glucose and 1-hour prediction
    into 4 values at 15-minute intervals using sigmoid curve.
    Returns: [+15min, +30min, +45min, +60min] in mg/dL
    """
    start = current_glucose
    end   = predicted_glucose
    delta = end - start

    def sigmoid_frac(t):
        return 1 / (1 + np.exp(-10 * (t - 0.5)))

    s0 = sigmoid_frac(0)
    s1 = sigmoid_frac(1)

    points = []
    for t in [0.25, 0.50, 0.75, 1.0]:
        fraction = (sigmoid_frac(t) - s0) / (s1 - s0)
        value    = start + delta * fraction
        value    = value + random.gauss(0, 2.5)    # ±2.5 mg/dL sensor noise
        value    = max(40, min(400, value))         # physiological bounds
        points.append(round(value, 1))

    return points   # [+15min, +30min, +45min, +60min]


# ─── SECTION 11: PREDICT GLUCOSE TOOL ────────────────────────────────────────

def predict_glucose(row_number: int) -> dict:
    """
    Real glucose prediction using a specific row from the validation dataset.

    Input:
        row_number: Integer row index (0-based) to select from val_df.

    Returns:
        current_glucose       : column C (glucose) value at row_number (mg/dL)
        future_cgm_4_points   : [+15min, +30min, +45min, +60min] in mg/dL
        min_pred              : min of future_cgm_4_points
        max_pred              : max of future_cgm_4_points
        prediction_interval   : "15min"
        prediction_horizon    : "60min"
        row_number_used       : confirms which row was used
    """
    max_row = len(val_df) - 1
    if not isinstance(row_number, int) or row_number < 0 or row_number > max_row:
        return {
            "error":       f"row_number {row_number} is out of range.",
            "valid_range": f"0 to {max_row}",
            "total_rows":  len(val_df)
        }

    row          = val_df.iloc[row_number]
    current_mgdl = round(float(row['glucose']), 1)
    features     = row[FEATURE_COLS].values.reshape(1, -1)
    pred_mgdl    = round(float(real_model.predict(features)[0]), 1)
    future_4pts  = interpolate_to_15min(current_mgdl, pred_mgdl)

    return {
        "current_glucose":      current_mgdl,
        "future_cgm_4_points":  future_4pts,
        "min_pred":             min(future_4pts),
        "max_pred":             max(future_4pts),
        "prediction_interval":  "15min",
        "prediction_horizon":   "60min",
        "row_number_used":      row_number + 1
    }

print("✅ predict_glucose defined — row_number in, current + 4 future points out (mg/dL)")


# ─── SECTION 12: MAIN AGENT ──────────────────────────────────────────────────

Main_agent = Agent(
    name="Orchestrator_Agent",
    model=Gemini(
        model="gemini-2.5-flash",
        output_key="main_output",
        retry_options=retry_config
    ),
    instruction="""
System Role

You are a Blood Glucose Coaching Orchestrator Agent that helps users with
diabetes maintain their blood glucose within the target range of 90–150 mg/dL.

You coordinate multiple specialized agents and tools to generate safe,
personalized recommendations. You do not guess medical information.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SAFETY FEEDBACK HANDLING (HIGHEST PRIORITY)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

If input contains a non-empty violations list:
  1. READ every violation carefully
  2. READ safer_alternative — apply it EXACTLY
  3. ALWAYS apply every correction from safer_alternative directly
  4. Do NOT repeat any listed violation
  5. Do NOT re-run tools — use previous_output as base, apply corrections only
  6. Regenerate full Output_Summary JSON with fixes applied

CRITICAL: If safer_alternative specifies a value, use that EXACT value.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
INPUT FORMAT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{
  "user_input": "...",
  "previous_output": {...} or null,
  "violations": [...] or [],
  "safer_alternative": "..." or null
}

- Extract fresh patient data from user_input
- If violations non-empty → apply fixes from safer_alternative to
  previous_output without re-running all tools
- If violations empty → run full workflow

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EXTRACT KEY INFORMATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

From user_input extract:
  - last_meal           (time and meal name)
  - current_time        (FULL value including day and time,
                          e.g. "Saturday, 6:30 PM ET")
  - current_day         (day of week extracted from current_time,
                          e.g. "Saturday")
  - current_clock_time  (time-of-day extracted from current_time,
                          e.g. "6:30 PM ET")
  - row_number
  - weight, height, diet
  - usual_meal_times    (breakfast, lunch, dinner)
  - oral_medication
  - insulin             (yes/no)
  - long_acting_insulin (value + preferred time)
  - glp1                (e.g. "weekly on Saturdays", "daily", "no")

  WEEKLY GLP-1 DAY MATCHING:
    IF glp1 contains "weekly":
      → Extract the scheduled day from glp1 value
        Examples:
          "weekly on Saturdays" → scheduled_day = "Saturday"
          "weekly on Mondays"   → scheduled_day = "Monday"
          "weekly on Fridays"   → scheduled_day = "Friday"
      → Compare scheduled_day to current_day (case-insensitive)
      → IF they match → glp1_due_today = True
      → IF they do not match → glp1_due_today = False
    IF glp1 = "daily": glp1_due_today = True
    IF glp1 = "no" or "none": glp1_due_today = False


Derive:
  - has_meal_taken_around_current_time:
      Compare last_meal, current_time, usual_meal_times.
      If user has NOT eaten at or near closest last or upcoming meal → False

  - minutes_since_last_meal:
      (current_time − last_meal_time) in minutes
      Example: last_meal=7:00 AM, current_time=1:30 PM → 390 min

  - closest_meal_name:
      Which of breakfast/lunch/dinner is closest to current_time

  ⚠️  CRITICAL — GLUCOSE SOURCE RULE:
      DO NOT use any glucose value from user_input for clinical decisions.
      The predict_glucose() tool returns a field called "current_glucose"
      — this is the ONLY authoritative glucose value for ALL
      recommendations in Steps 3–5 and the Output_Summary JSON.
      Use result["current_glucose"] everywhere after Step 2.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
GLUCOSE TO USE FOR RECOMMENDATIONS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

After Step 2, derive glucose_at_meal_time from result["current_glucose"]:

  IF current_time is BEFORE closest meal time:
    Count 15-min intervals until meal:
      ≤ 15 min → future_cgm_4_points[0]
      ≤ 30 min → future_cgm_4_points[1]
      ≤ 45 min → future_cgm_4_points[2]
      ≤ 60 min → future_cgm_4_points[3]
      > 60 min → result["current_glucose"]
    Source = "predicted"

  IF current_time is AT or AFTER closest meal time:
    glucose_at_meal_time = result["current_glucose"]
    Source = "current"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CARBOHYDRATE RULES (SIMPLE — READ BEFORE STEPS 3–5)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  IF glucose_at_meal_time > 150 AND has_meal_taken_around_current_time = False:
    → HIGH glucose: protein and vegetables ONLY
    → NO intentional carbohydrate course
    → Naturally occurring carbs from protein and vegetables (5–15g) acceptable
    → carb_rule = "HIGH"

  IF glucose_at_meal_time 70–150:
    → NORMAL glucose: balanced meal with less than 40g carbohydrates
    → Medication, insulin, and exercise are assumed to keep glucose
      within range — do NOT reduce carbs based on these factors
    → less than 40g carb target applies regardless of what medications
      or exercise are prescribed
    → carb_rule = "NORMAL"

  IF glucose_at_meal_time < 70:
    → LOW glucose: fast-acting carbohydrates REQUIRED immediately
    → carb_rule = "LOW"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WORKFLOW — FOLLOW THIS ORDER EVERY TIME
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

STEP 1 — MEDICATION ALERT

  Evaluate and call AlertAgent if ANY scenario applies:

  SCENARIO A — UPCOMING MEAL (within 60 min before meal):
    Condition:
      ANY of: oral_medication='pre-meal' OR insulin='yes'
              OR glp1 not 'no'
      AND current_time within 60 min BEFORE any usual_meal_time

  SCENARIO B — PAST MEAL, NOT TAKEN:
    Condition:
      ANY of: oral_medication='pre-meal' OR insulin='yes'
              OR glp1 not 'no'
      AND current_time AFTER closest usual_meal_time
      AND has_meal_taken_around_current_time = False

  LONG-ACTING INSULIN (independent):
    IF long_acting_insulin not 'No'
    AND current_time within 60 min of preferred time
    → Include in AlertAgent call or call separately

  ALWAYS pass to AlertAgent:
    "current_time: [current_time].
     current_day: [current_day].
     glp1_due_today: [true/false].
     alert_scenario: [upcoming_meal OR past_meal_not_taken].
     usual_meal_times: breakfast=[t], lunch=[t], dinner=[t].
     closest_meal: [name and time].
     last_meal: [last_meal].
     has_meal_taken_around_current_time: [true/false].
     oral_medication: [oral_medication].
     insulin: [insulin].
     long_acting_insulin: [long_acting_insulin].
     glp1: [glp1]."

  NO ALERT if:
    oral_medication='none' AND insulin='no'
    AND long_acting_insulin='no' AND glp1='no'

STEP 2 — PREDICT FUTURE GLUCOSE

  IF previous_output already has current_glucose and
  future_cgm_4_points → SKIP and reuse those exact values.
  Otherwise → call predict_glucose(row_number=<row_number>) EXACTLY ONCE.

  Tool returns these exact keys:
    "current_glucose"      ← ground-truth current glucose (mg/dL)
                              USE THIS EVERYWHERE in Steps 3–5
    "future_cgm_4_points"  ← [+15min, +30min, +45min, +60min] mg/dL
    "min_pred"             ← min of future values
    "max_pred"             ← max of future values
    "prediction_interval"  ← "15min"
    "prediction_horizon"   ← "60min"
    "row_number_used"      ← confirms which row was used

  If tool returns "error" key → return error to user, stop.
  Never call predict_glucose again in this workflow.

  After receiving result, store:
    current_glucose       = result["current_glucose"]
    future_cgm_4_points   = result["future_cgm_4_points"]
    min_predicted_glucose = result["min_pred"]
    max_predicted_glucose = result["max_pred"]

STEP 3 — INSULIN DOSAGE RECOMMENDATION
  IF the last meal has already been taken and the next meal is more than 1 hour away:
      → {units: 0, timing: "not required"}
  Condition: insulin='yes' AND has_meal_taken_around_current_time=False

  IF condition met:
    → Call InsulinRecommenderAgent
    → Pass glucose_at_meal_time (derived from current_glucose) as input
    → Extract number from dose string returned
    → Populate: insulin_recommendation: {units: <n>, timing: "before <meal>"}

  IF InsulinRecommenderAgent returns {}:
    → {units: 0, timing: "not required"}

  IF condition not met:
    → {units: 0, timing: "not required"}

  NEVER set units or timing to null.

STEP 4 — MEAL RECOMMENDATION

  Skip if user ate within last 1 hour (unless glucose < 70 mg/dL).
  Skip if the next meal is more 1 hour away (unless glucose < 70 mg/dL)

  IF meal needed:
    → Call MealAgent with:
       - glucose_at_meal_time  (use this, NOT current_glucose)
       - predicted glucose trajectory (full future_cgm_12_points)
       - diet preference
       - meal_type: closest_meal_name ("Breakfast" / "Lunch" / "Dinner")
       - glucose target range: 90–150 mg/dL

    After MealAgent responds:
    → Extract "Estimated Total Carbohydrates: XX grams" from response
    → Store as meal_carbs_estimate (integer or None if not found)
    → This is used in Step 5
    → Validate meal_carbs_estimate against carb_rule:
         If glucose_at_meal_time > 150 AND meal_carbs_estimate > 20:
           → This suggests MealAgent included intentional carbs — flag this
             in your output by setting meal_carbs_estimate_note =
             "WARNING: carb estimate exceeds expected natural carb range.
              Review meal recommendation."
         If glucose_at_meal_time > 150 AND meal_carbs_estimate <= 20:
           → This is expected and acceptable — naturally occurring carbs
             from protein and vegetables. No action needed.
         If glucose_at_meal_time <= 150:
           → Any carb estimate is acceptable provided it aligns with
             the meal content.

STEP 5 — EXERCISE RECOMMENDATION

  Safety override:
    IF current_glucose < 70:
      exercise_recommendation = {
        status: "unsafe",
        max_intensity: "Avoid",
        exercise_credit_mgdl: 0,
        safety_note: "No exercise. Treat hypoglycemia first."
      }
      SKIP ExerciseAgent call.

  Otherwise derive parameters:
    A) glucose_level           = current_glucose
                                 ← result["current_glucose"] from tool
                                 ← NOT glucose_at_meal_time
                                 (exercise safety = NOW, not meal time)
    B) minutes_since_last_meal = derived in Extract Key Information
    C) last_meal_carbs:
         IF has_meal_taken_around_current_time=True →
           extract from prior meal if mentioned, else None
         ELSE → None
    D) upcoming_meal_carbs:
         IF has_meal_taken_around_current_time=False
         AND meal_carbs_estimate exists → meal_carbs_estimate
         ELSE → None

  Call ExerciseAgent:
    "glucose_level: [current_glucose].
     minutes_since_last_meal: [B].
     last_meal_carbs: [C].
     upcoming_meal_carbs: [D].
     predicted_glucose_trend: [future_cgm_4_points].
     min_predicted_glucose: [min of future_cgm_4_points]."

  Store exercise_recommendation.exercise_credit_mgdl for
  use in Step 4 on any retry.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SAFETY RULES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Hypoglycemia (current_glucose < 70):
  1. Fast-acting carbs immediately
  2. Wait 15 min → recheck
  3. Repeat if still low
  4. NO exercise, NO insulin

Medication timing:
  Pre-meal oral: 15 min before meal
  Long-acting insulin: at scheduled preferred time

Exercise timing:
  Post-meal: ~2 hours after eating

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TOOL USAGE RULES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

- Never fabricate glucose values, insulin doses, or nutrition values
- Never retry a tool already called in this workflow
- AlertAgent {}               → success, proceed
- MealAgent {}                → success, proceed
- ExerciseAgent {}            → success, proceed
- InsulinRecommenderAgent {}  → units=0, timing="not required"
- Never set insulin units or timing to null

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OUTPUT FORMAT (STRICTLY ENFORCED)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Return ONLY valid JSON. No markdown. No ```json fences.

{
  "Output_Summary": {
    "user_information": {
      "weight": "...",
      "height": "...",
      "diet": "...",
      "usual_meal_times": {
        "breakfast": "...",
        "lunch": "...",
        "dinner": "..."
      },
      "oral_medication": "...",
      "insulin": "...",
      "long acting Insulin": "...",
      "glp1": "...",
      "row_number": <number from row_number_used>
    },
    "current_glucose": <number from result["current_glucose"]>,
    "glucose_at_meal_time": <number>,
    "glucose_at_meal_time_source": "predicted" or "current",
    "max_predicted_glucose": <number from result["max_pred"]>,
    "min_predicted_glucose": <number from result["min_pred"]>,
    "future_cgm_4_points": [<+15min>, <+30min>, <+45min>, <+60min>],
    "last_meal": "...",
    "current_time": "...",
    "minutes_since_last_meal": <number>,
    "has_meal_taken_around_current_time": true/false,
    "carb_rule": "HIGH" or "NORMAL" or "LOW",
    "meal_carbs_estimate": <number or null>,
    "meal_carbs_estimate_note": null,
    "glucose_outlook": "...",
    "medication_recommendation": "...",
    "meal_recommendation": "...",
    "insulin_recommendation": {
      "units": <number — never null>,
      "timing": "<string — never null>"
    },
    "exercise_recommendation": {
      "status": "ok" or "unsafe",
      "max_intensity": "...",
      "exercise_credit_mgdl": <number>,
      "intensity": "...",
      "duration": "...",
      "focus": "...",
      "suggested_exercises": "...",
      "pre_meal_strategy": "..." or null,
      "safety_note": "..."
    },
    "safety_notes": "..."
  }
}
""",
    tools=[
        AgentTool(AlertAgent),
        FunctionTool(predict_glucose),
        AgentTool(InsulinAgent),
        AgentTool(MealAgent),
        AgentTool(ExerciseAgent)
    ],
)

print("✅ Main_agent created.")

# ─── SECTION 13: FORMATTER AGENT ─────────────────────────────────────────────

FormatterAgent = Agent(
    name="FormatterAgent",
    model=Gemini(model="gemini-2.5-flash-lite", retry_options=retry_config),
    output_key="formatted_output",
    instruction="""
You receive a validated JSON glucose management summary under the key "validated_output".
Convert it into a clean, friendly, easy-to-read report for a diabetes patient.

Format it EXACTLY as shown below, replacing every [...] with the actual value.
Output plain text ONLY — no JSON, no markdown code blocks, no bullet symbols from JSON.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 GLUCOSE OUTLOOK
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Current Glucose       : [current_glucose] mg/dL
  Glucose at Meal Time  : [glucose_at_meal_time] mg/dL  ([glucose_at_meal_time_source])
  Predicted Range       : [min_predicted_glucose] – [max_predicted_glucose] mg/dL
  Last Meal             : [last_meal]
  Current Time          : [current_time]
  Time Since Last Meal  : [minutes_since_last_meal] minutes
  Meal Taken Recently   : [has_meal_taken_around_current_time — Yes or No]

  Predicted Glucose (next 60 min, every 15 min):
  [future_cgm_4_points — show as comma-separated numbers on one line]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
👤 USER INFORMATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Weight          : [weight]
  Height          : [height]
  Diet Preference : [diet]

  Usual Meal Times:
    Breakfast : [usual_meal_times.breakfast]
    Lunch     : [usual_meal_times.lunch]
    Dinner    : [usual_meal_times.dinner]

  Medications:
    Oral Medication      : [oral_medication]
    Short-acting Insulin : [insulin]
    Long-acting Insulin  : [long acting Insulin]
    GLP-1                : [glp1]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💊 MEDICATION REMINDER
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  [medication_recommendation — if empty or null, write "No medication due at this time."]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💉 INSULIN DOSAGE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Recommended Dose : [insulin_recommendation.units] units
  Timing           : [insulin_recommendation.timing]

  [If units = 0, add: "No short-acting insulin required at this time."]
  [If units > 0, add: "Please take [units] units of short-acting insulin
   [timing]. Your glucose at meal time is [glucose_at_meal_time] mg/dL."]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🍽️  MEAL RECOMMENDATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Glucose at Meal Time  : [glucose_at_meal_time] mg/dL
  Glucose Status        : [High / Normal / Low]

  Hydration:
  [hydration guidance from meal_recommendation]

  Protein:
  [protein item, quantity, serving size, protein_g, carbs_g, calories]

  Vegetables:
  [vegetable item, quantity, serving size, carbs_g, calories]

  Carbohydrates:
  [If glucose > 150: "None (intentional) — approximately [meal_carbs_estimate]g
   naturally occurring carbs from protein and vegetables."]
  [If glucose <= 150: carbohydrate food from tool]
  [If hypoglycemia: fast-acting carb — eat immediately]

  Estimated Total Carbohydrates : [meal_carbs_estimate]g

  [If meal_recommendation is empty or null, write:
   "No meal recommended at this time."]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🏃 EXERCISE RECOMMENDATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Status    : [exercise_recommendation.status]
  Intensity : [exercise_recommendation.intensity]
  Duration  : [exercise_recommendation.duration]
  Focus     : [exercise_recommendation.focus in plain English]

  Suggested Activities:
  [exercise_recommendation.suggested_exercises — top 3–5]

  [If pre_meal_strategy not null, add Pre-Meal Strategy section]

  [If status = "unsafe":
   ⚠️ Exercise is NOT recommended right now.
   [exercise_recommendation.safety_note]]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️  SAFETY NOTES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  [safety_notes — if empty or null: "No safety concerns at this time. Keep it up! 🎉"]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 SUMMARY SNAPSHOT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ✅ Take medication   : [Yes / No]
  ✅ Take insulin      : [Yes — X units before meal / No]
  ✅ Eat               : [Yes — Breakfast/Lunch/Dinner / No — ate recently]
  ✅ Exercise          : [Yes — intensity and duration / No — not safe now]
  ✅ Drink water       : [Yes — amount / No specific need]
  ✅ Next check-in     : [when to recheck glucose]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

FORMATTING RULES:
- Output plain text ONLY
- No JSON anywhere in the output
- No markdown code blocks
- Use simple, warm, supportive language
- Round all glucose values to nearest whole number
- Always end with an encouraging closing line such as:
  "You're doing great managing your health. Small steps every day make a big difference! 💪"
"""
)
print("✅ Formatter Agent created.")


# ─── SECTION 14: CONTROLLER ──────────────────────────────────────────────────

import json
import re
import csv
import os
import logging
from datetime import datetime
from google.adk.plugins.logging_plugin import LoggingPlugin
from google.adk.plugins import BasePlugin

# ── Token Counter Plugin ──────────────────────────────────────────────────────

class TokenCounterPlugin(BasePlugin):

    def __init__(self):
        super().__init__(name="token_counter")
        self.input_tokens  = 0
        self.output_tokens = 0

    def reset(self):
        self.input_tokens  = 0
        self.output_tokens = 0

    async def after_model_callback(self, *, callback_context, llm_response) -> None:
        meta = getattr(llm_response, "usage_metadata", None)
        if meta:
            self.input_tokens  += getattr(meta, "prompt_token_count",     0) or 0
            self.output_tokens += getattr(meta, "candidates_token_count", 0) or 0
        return None

token_counter = TokenCounterPlugin()

# ── CSV Logging ───────────────────────────────────────────────────────────────

CSV_LOG_FILE = "agent_runs.csv"
CSV_HEADERS  = [
    "timestamp",
    "duration_seconds",
    "input_tokens",
    "output_tokens",
    "is_safe",
    "attempts",
    "main_agent_output"
]

def init_csv_log():
    """Create CSV with headers if it doesn't exist yet."""
    if not os.path.exists(CSV_LOG_FILE):
        with open(CSV_LOG_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
            writer.writeheader()

def append_csv_log(timestamp, duration_seconds, input_tokens, output_tokens,
                   is_safe, attempts, main_agent_output):
    """Append one run's metrics to the CSV log."""
    with open(CSV_LOG_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        writer.writerow({
            "timestamp":         timestamp,
            "duration_seconds":  round(duration_seconds, 3),
            "input_tokens":      input_tokens,
            "output_tokens":     output_tokens,
            "is_safe":           is_safe,
            "attempts":          attempts,
            "main_agent_output": json.dumps(main_agent_output)
                                 if isinstance(main_agent_output, dict)
                                 else str(main_agent_output)
        })

init_csv_log()

# ── Helpers ───────────────────────────────────────────────────────────────────

def extract_text_from_debug(debug_result):
    try:
        if isinstance(debug_result, list):
            for event in reversed(debug_result):
                if hasattr(event, "content") and event.content:
                    return event.content.parts[0].text
        return str(debug_result)
    except Exception:
        return str(debug_result)

def extract_clean_summary(main_json):
    summary = main_json.get("Output_Summary", "")
    if not summary:
        return {}
    if isinstance(summary, dict):
        return summary
    summary = re.sub(r"```json|```", "", summary).strip()
    if summary.startswith("{"):
        try:
            inner = json.loads(summary)
            return inner.get("Output_Summary", inner)
        except Exception:
            pass
    return summary

# ── Main Controller ───────────────────────────────────────────────────────────

async def run_main_with_safety(user_input):
    MAX_RETRIES = 3
    SafetyAgentrunner    = InMemoryRunner(agent=SafetyAgent,    plugins=[LoggingPlugin(), token_counter])
    FormatterAgentRunner = InMemoryRunner(agent=FormatterAgent, plugins=[LoggingPlugin(), token_counter])

    token_counter.reset()
    run_timestamp = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    run_start     = datetime.utcnow()

    attempt                  = 0
    violations               = []
    corrected_recommendation = None
    clean_summary            = None
    final_is_safe            = False
    final_output             = None
    result                   = None

    while attempt < MAX_RETRIES:

        attempt += 1      # ← increment FIRST so attempt always reflects
                          #   the actual number of attempts made
        print(f"\n========== ATTEMPT {attempt} ==========")

        MainAgentrunner = InMemoryRunner(agent=Main_agent, plugins=[LoggingPlugin(), token_counter])

        main_payload = {
            "user_input":      user_input,
            "previous_output": clean_summary if attempt > 1 else None,
            "violations":      violations    if attempt > 1 else []
        }

        raw_response = await MainAgentrunner.run_debug(json.dumps(main_payload))
        main_text    = extract_text_from_debug(raw_response)

        try:
            main_json = json.loads(main_text)
        except Exception:
            main_json = {"Output_Summary": main_text}

        print("\n--- MAIN OUTPUT ---")
        print(json.dumps(main_json, indent=2))

        clean_summary = extract_clean_summary(main_json)
        final_output  = clean_summary

        print("\n--- CLEAN SUMMARY SENT TO SAFETY ---")
        print(json.dumps(clean_summary, indent=2) if isinstance(clean_summary, dict) else clean_summary)

        safety_payload = json.dumps({"Output_Summary": clean_summary})
        raw_safety     = await SafetyAgentrunner.run_debug(safety_payload)
        safety_text    = extract_text_from_debug(raw_safety)

        print("\n--- RAW SAFETY TEXT ---")
        print(safety_text)

        try:
            safety_text_clean = re.sub(r"```json|```", "", safety_text).strip()
            safety_result     = json.loads(safety_text_clean)
        except Exception:
            safety_result = {
                "safe":       False,
                "violations": ["Could not parse safety agent response"],
            }

        print("\n--- SAFETY OUTPUT ---")
        print(json.dumps(safety_result, indent=2))

        safe           = safety_result.get("safe", False)
        new_violations = safety_result.get("violations", [])

        # ── Check if violations are repeating (agent is stuck) ────────────────
        if not safe and new_violations == violations and attempt > 1:
            final_is_safe = False
            result = {
                "status":      "failed",
                "reason":      "Repeated violations — agent is stuck",
                "attempts":    attempt,    # ← always correct now
                "violations":  new_violations,
                "last_output": clean_summary
            }
            break

        violations = new_violations

        # ── Safe: run formatter and return ────────────────────────────────────
        if safe:
            fmt_payload = json.dumps({"validated_output": clean_summary})
            raw_fmt     = await FormatterAgentRunner.run_debug(fmt_payload)
            readable    = extract_text_from_debug(raw_fmt)

            final_is_safe = True
            result = {
                "status":            "safe",
                "attempts":          attempt,    # ← always correct now
                "readable_output":   readable,
                "structured_output": clean_summary
            }
            break

    # ── Max retries exhausted ─────────────────────────────────────────────────
    if result is None:
        final_is_safe = False
        result = {
            "status":      "failed",
            "reason":      "Max retries exceeded",
            "attempts":    attempt,        # ← correct: equals MAX_RETRIES
            "violations":  violations,
            "last_output": clean_summary
        }

    duration = (datetime.utcnow() - run_start).total_seconds()
    append_csv_log(
        timestamp         = run_timestamp,
        duration_seconds  = duration,
        input_tokens      = token_counter.input_tokens,
        output_tokens     = token_counter.output_tokens,
        is_safe           = final_is_safe,
        attempts          = result["attempts"],    # ← read from result dict
        main_agent_output = final_output
    )

    return result

# ─── SECTION 15: EXAMPLE USER INPUT & RUN ────────────────────────────────────

user_input = """
last_meal = Lunch at 1:00 PM ET
current_time = Saturday, 6:30 PM ET
row_number = 41
weight = 75 kg
height = 1.65 m
diet = Vegetarian
usual_meal_times:
  breakfast = 7:00 AM ET
  lunch = 12:30 PM ET
  dinner = 7:00 PM ET
oral_medication = pre-meal
insulin = yes
long_acting_insulin = Yes, every night 9PM ET
glp1 = weekly on Saturdays
"""

# ─── SECTION 16: RUN ─────────────────────────────────────────────────────────
# Uncomment to run:
#
# import asyncio
# import time
#
# MAX_RETRIES = 3
#
# async def main():
#     start_time = time.time()
#     result = await run_main_with_safety(user_input)
#     elapsed = time.time() - start_time
#     print(result)
#     print(f"✅ Completed in {elapsed:.2f} seconds.")

 #asyncio.run(main())

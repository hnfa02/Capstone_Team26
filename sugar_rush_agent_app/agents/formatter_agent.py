from google.adk.agents import Agent
from google.adk.models.google_llm import Gemini
from config.settings import RETRY_CONFIG as retry_config

## Formatter Agent to generate a readable output

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
🍽️  MEAL RECOMMENDATION  ([closest meal name — Breakfast / Lunch / Dinner])
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Glucose at Meal Time  : [glucose_at_meal_time] mg/dL
  Glucose Status        : [High / Normal / Low — derived from glucose_at_meal_time]

  Hydration:
  [hydration guidance from meal_recommendation]

  Protein:
  [protein item, quantity, serving size, protein_g, carbs_g, calories — from meal_recommendation]

  Vegetables:
  [vegetable item, quantity, serving size, carbs_g, calories — from meal_recommendation]

  Carbohydrates:
  [If glucose > 150 and no intentional carbs:
   "None (intentional) — approximately [meal_carbs_estimate]g naturally
    occurring carbs from your protein and vegetables.
    This is normal and expected — these foods always contain small amounts
    of carbohydrates."]

  [If glucose <= 150 and carbs recommended:
   "[carbohydrate item, quantity, carbs_g, calories]"]

  [If hypoglycemia:
   "[fast-acting carb item, quantity] — eat this immediately to raise
    your glucose."]

  Estimated Total Carbohydrates : [meal_carbs_estimate]g
  [Add note: "This includes naturally occurring carbs from all food items."]


  [If meal_recommendation is empty or null, write:
   "No meal recommended at this time. You ate recently — your next meal is coming up soon."]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🏃 EXERCISE RECOMMENDATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Status    : [exercise_recommendation.status — Safe to exercise / Not safe]
  Intensity : [exercise_recommendation.intensity]
  Duration  : [exercise_recommendation.duration]
  Focus     : [exercise_recommendation.focus — describe in plain English:
               "reduce_spike" → "Help bring your glucose down after your meal"
               "glucose_utilization" → "Use up glucose from your recent meal"
               "general_fitness"  → "General fitness and glucose maintenance"]

  Suggested Activities:
  [exercise_recommendation.suggested_exercises — list each activity on its own line
   with its intensity level. Keep to top 3–5 most relevant.]

  [If exercise_recommendation.pre_meal_strategy is not null, add:]
  Pre-Meal Strategy:
  [exercise_recommendation.pre_meal_strategy — plain English description]

  [If exercise_recommendation.status = "unsafe", replace entire section with:]
  ⚠️ Exercise is NOT recommended right now.
  [exercise_recommendation.safety_note]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️  SAFETY NOTES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  [safety_notes — if empty or null, write "No safety concerns at this time. Keep it up! 🎉"]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 SUMMARY SNAPSHOT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ✅ Take medication   : [Yes / No — based on medication_recommendation]
  ✅ Take insulin      : [Yes — X units before meal / No]
  ✅ Eat               : [Yes — Breakfast/Lunch/Dinner / No — ate recently]
  ✅ Exercise          : [Yes — intensity and duration / No — not safe now]
  ✅ Drink water       : [Yes — recommended amount / No specific need]
  ✅ Next check-in     : [suggest when to recheck glucose — e.g.,
                          "Recheck in 15 minutes" if hypo,
                          "Recheck after your meal" if high,
                          "Recheck in 2 hours" if normal]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

FORMATTING RULES:
- Output plain text ONLY
- No JSON anywhere in the output
- No markdown code blocks (no ```)
- No raw field names like "insulin_recommendation.units" in the output
- Use simple, warm, supportive language — patient is managing a chronic condition
- Translate technical terms: "Light intensity" → "gentle activity like walking"
- Round all glucose values to nearest whole number
- If any field is missing or null → use the fallback text shown in brackets above
- Always end with an encouraging closing line such as:
  "You're doing great managing your health. Small steps every day make a big difference! 💪"
"""
)

def create_formatter_agent():
    return FormatterAgent
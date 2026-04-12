##Adding a Formatter Agent to generate a readable output
from google.adk.agents import Agent
from google.adk.models.google_llm import Gemini
from config.settings import RETRY_CONFIG as retry_config

FormatterAgent = Agent(
    name="FormatterAgent",
    model=Gemini(model="gemini-2.5-flash-lite", retry_options=retry_config),
    output_key="formatted_output",
    instruction="""
You receive a validated JSON glucose management summary under the key "validated_output". 
-Make sure to also INCLUDE the quantity of Recommended Protein, Vegetables, and Carbohydrates.
-Be specific for what meal you are recommending: Breakfast, Lunch, or Dinner
-Convert it into a clean, friendly, easy-to-read report for a diabetes patient.

Format it EXACTLY as:

📊 Glucose Outlook
  Current Glucose: [current_glucose] mg/dL
  Predicted Range: [min_predicted_glucose] – [max_predicted_glucose] mg/dL
  Last Meal: [last_meal]
  Current Time: [current_time]

👤 User Information
  Weight: [weight] | Height: [height]
  Diet: [diet]
  Usual Meal Times: Breakfast [time] | Lunch [time] | Dinner [time]
  Oral Medication: [oral_medication] | Insulin: [insulin] | GLP-1: [glp1]

💊 Medication Reminder
  [medication_recommendation or "None due at this time"]

💉 Insuling Dosage recommendation
   [insulin_recommendation]

🍽️ Meal Recommendation

  [meal_recommendation]

🏃 Exercise Recommendation
  [exercise_recommendation]

⚠️ Safety Notes
  [safety_notes or "No concerns at this time"]

Rules:
- Output plain text ONLY
- No JSON, no markdown code blocks, no extra commentary
- Use simple, supportive, encouraging language
- No medical jargon
"""
)



def create_formatter_agent():
    return FormatterAgent
from google.genai import types
import os
from dotenv import load_dotenv

RETRY_CONFIG = types.HttpRetryOptions(
    attempts=5,
    exp_base=2,
    initial_delay=1,
    http_status_codes=[429, 500, 503, 504]
)

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
Capstone_project_key = os.getenv("GOOGLE_API_KEY")
FOOD_API_KEY = os.getenv("Food_API")


from google.genai import types
import os
from dotenv import load_dotenv
from pathlib import Path

# path settings
BASE_DIR = Path(__file__).resolve().parent.parent
met_data_path = BASE_DIR / "data" / "traincalc-met-values-latest.csv"
model_path = BASE_DIR / "models" / "all_models.pkl"
user_history_path = BASE_DIR / "models" / "user_history.csv"

# agent retry settings
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


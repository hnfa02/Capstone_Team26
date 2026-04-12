from .alert_agent import create_alert_agent
from .insulin_agent import create_insulin_agent
from .meal_agent import create_meal_agent
from .exercise_agent import create_exercise_agent
from .main_agent import create_main_agent
from .safety_agent import create_safety_agent
from .formatter_agent import create_formatter_agent
from tools.prediction_tool import predict_glucose
from google.adk.tools import AgentTool, FunctionTool

from config.settings import RETRY_CONFIG


def initialize_agents():
    alert = create_alert_agent()
    insulin = create_insulin_agent()
    meal = create_meal_agent()
    exercise = create_exercise_agent()
    safety = create_safety_agent()
    formatter = create_formatter_agent()

    main = create_main_agent(
        RETRY_CONFIG,
        tools = [AgentTool(alert), FunctionTool(predict_glucose), AgentTool(insulin), AgentTool(meal), AgentTool(exercise)],
    )

    return {
        "alert": alert,
        "insulin": insulin,
        "meal": meal,
        "exercise": exercise,
        "main": main,
        "safety": safety,
        "formatter": formatter,
    }


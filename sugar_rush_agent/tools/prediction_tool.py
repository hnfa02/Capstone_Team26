# prediction tool for the Main agent
import joblib
# Gen AI Tools (ChatGPT used)
import pandas as pd
from sklearn.linear_model import LinearRegression
from models.cgm_model import DummyCGMModel
import numpy as np
import random

def predict_glucose(min_past,max_past):

    model = joblib.load("models/dummy_cgm_model.joblib")
    prediction = model.predict(min_past, max_past) # min max of past 24 values

    return prediction

# ─── INTERPOLATION: to create reading for every 15 min using the current and 1 hour prediction glucose ────────────────────────────────────────────────────────────

def interpolate_to_15min(current_glucose: float, predicted_glucose: float) -> list:
    """
    Interpolate between current glucose and 1-hour prediction
    into 4 values at 15-minute intervals using sigmoid curve.

    All values already in mg/dL — no conversion needed.

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
        value    = value + random.gauss(0, 2.5)     # ±2.5 mg/dL sensor noise
        value    = max(40, min(400, value))          # physiological bounds
        points.append(round(value, 1))

    return points   # [+15min, +30min, +45min, +60min]

def predict_glucose(user_input, history_path="models/user_history.csv", model_path="models/all_models.pkl", user_id='2405'):
    """
    AI Agent Tool: Predict glucose for next 60 minutes.

    Inputs:
        model_dict   : dict of trained models
        user_input   : list[dict] (single latest event)
        user_history : pd.DataFrame (last 4 timesteps, most recent first)
        user_id      : str

    Returns:
        dict with:
            current_glucose
            future_cgm_4_points
            min_pred
            max_pred
            prediction_interval
            prediction_horizon
            source
    """
    model_dict = joblib.load(model_path)  # Load the dictionary of models from the specified path
    user_history = pd.read_csv(history_path)  # Load user history from the specified path
    # ────────────────────────────────────────────────────────────────────────
    # 1. Input validation
    # ────────────────────────────────────────────────────────────────────────
    if user_id not in model_dict:
        return {"error": f"Model for user_id '{user_id}' not found."}

    if not isinstance(user_input, list) or len(user_input) == 0:
        return {"error": "user_input must be a non-empty list of dicts."}

    required_history_cols = [
        'glucose','carbs_g','fat_g','prot_g','fibre_g',
        'basal_dose','bolus_dose','active_cal'
    ]

    for col in required_history_cols:
        if col not in user_history.columns:
            return {"error": f"user_history missing column: {col}"}

    if len(user_history) < 4:
        return {"error": "user_history must contain at least 4 rows."}

    # ────────────────────────────────────────────────────────────────────────
    # 2. Ensure correct ordering (most recent first)
    # ────────────────────────────────────────────────────────────────────────
    user_history = user_history.copy().reset_index(drop=True)

    # ────────────────────────────────────────────────────────────────────────
    # 3. Build feature dataframe
    # ────────────────────────────────────────────────────────────────────────
    df = pd.DataFrame(user_input)
    df = df.drop(columns=['id','meal_tag','meal_type'], errors='ignore')

    model = model_dict[user_id]

    # Initialize aggregates
    agg_cols = [
        'glucose_mean_1hr','carbs_sum_1hr','fat_sum_1hr',
        'prot_sum_1hr','fibre_sum_1hr',
        'basal_dose_sum_1hr','bolus_dose_sum_1hr','active_cal_sum_1hr'
    ]
    for col in agg_cols:
        df[col] = 0

    # Lags + aggregation
    for i in range(4):
        row = user_history.iloc[i]

        df[f'glucose_lag_{i+1}'] = row['glucose']
        df[f'carbs_g_lag_{i+1}'] = row['carbs_g']
        df[f'fat_g_lag_{i+1}'] = row['fat_g']
        df[f'prot_g_lag_{i+1}'] = row['prot_g']
        df[f'fibre_g_lag_{i+1}'] = row['fibre_g']
        df[f'basal_dose_lag_{i+1}'] = row['basal_dose']
        df[f'bolus_dose_lag_{i+1}'] = row['bolus_dose']
        df[f'active_cal_lag_{i+1}'] = row['active_cal']

        df['glucose_mean_1hr'] += row['glucose']
        df['carbs_sum_1hr'] += row['carbs_g']
        df['fat_sum_1hr'] += row['fat_g']
        df['prot_sum_1hr'] += row['prot_g']
        df['fibre_sum_1hr'] += row['fibre_g']
        df['basal_dose_sum_1hr'] += row['basal_dose']
        df['bolus_dose_sum_1hr'] += row['bolus_dose']
        df['active_cal_sum_1hr'] += row['active_cal']

    df['glucose_mean_1hr'] /= 4

    # ────────────────────────────────────────────────────────────────────────
    # 4. Align features with model
    # ────────────────────────────────────────────────────────────────────────
    try:
        df = df[model.feature_cols]
    except Exception as e:
        return {"error": f"Feature alignment failed: {str(e)}"}

    # ────────────────────────────────────────────────────────────────────────
    # 5. Predict
    # ────────────────────────────────────────────────────────────────────────
    try:
        pred_mgdl = float(model.predict(df)[0])
        pred_mgdl = round(pred_mgdl, 1)
    except Exception as e:
        return {"error": f"Model prediction failed: {str(e)}"}

    # ────────────────────────────────────────────────────────────────────────
    # 6. Current glucose (latest)
    # ────────────────────────────────────────────────────────────────────────
    current_mgdl = float(user_input[0]['glucose'])
    current_mgdl = round(current_mgdl, 1)

    # ────────────────────────────────────────────────────────────────────────
    # 7. Interpolation (must exist)
    # ────────────────────────────────────────────────────────────────────────
    try:
        future_4pts = interpolate_to_15min(current_mgdl, pred_mgdl)
    except Exception as e:
        return {"error": f"Interpolation failed: {str(e)}"}

    # ────────────────────────────────────────────────────────────────────────
    # 8. Final structured output
    # ────────────────────────────────────────────────────────────────────────
    return {
        "current_glucose": current_mgdl,
        "future_cgm_4_points": future_4pts,
        "min_pred": min(future_4pts),
        "max_pred": max(future_4pts),
        "prediction_interval": "15min",
        "prediction_horizon": "60min",
        "source": "user_input"
    }
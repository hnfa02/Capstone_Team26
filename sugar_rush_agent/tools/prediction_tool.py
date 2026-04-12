# prediction tool for the Main agent
import joblib
from models.cgm_model import DummyCGMModel
def predict_glucose(min_past,max_past):

    model = joblib.load("models/dummy_cgm_model.joblib")
    prediction = model.predict(min_past, max_past) # min max of past 24 values

    return prediction
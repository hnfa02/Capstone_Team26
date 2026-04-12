import joblib
from models.cgm_model import DummyCGMModel  # must be in separate file

model = DummyCGMModel()

joblib.dump(model, "models/dummy_cgm_model.joblib")

print("Model saved correctly")
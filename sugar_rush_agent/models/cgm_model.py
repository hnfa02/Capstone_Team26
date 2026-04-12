## Creating a dummy prediction model
# input: <min_past and max_past that automatically create random 24 past CGM data points within min & max range
# output: <min_pred, max_pred and randomly generated 12 future CGM data points within min and max range

import random

class DummyCGMModel:

    def predict(self, min_past, max_past):

        # Generate 24 past CGM values
        past_cgm = [random.randint(min_past, max_past) for _ in range(24)]

        # Define prediction range
        min_pred = min(past_cgm) - random.randint(5, 15)
        max_pred = max(past_cgm) + random.randint(5, 15)

        # Generate 12 future predictions
        future_cgm = [random.randint(min_pred, max_pred) for _ in range(12)]
        min_pred = min(future_cgm)
        max_pred = max(future_cgm)

        return {
            "past_cgm_24_points": past_cgm,
            "min_pred": min_pred,
            "max_pred": max_pred,
            "future_cgm_12_points": future_cgm
        }

# Save the model with joblib
import joblib

model = DummyCGMModel()

joblib.dump(model, "dummy_cgm_model.joblib")

print(" ✅ Model saved!")


#Insulin Agent Tools
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
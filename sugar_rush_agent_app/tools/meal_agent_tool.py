# Tool: Food API
import os
import requests

# Meal Agent Tools

FOOD_API_KEY = os.getenv("Food_API")

def search_food_by_carbs(food_name: str, max_carbs: float):

    url = "https://api.nal.usda.gov/fdc/v1/foods/search"

    params = {
        "query": food_name,
        "pageSize": 20,
        "api_key": FOOD_API_KEY
    }

    r = requests.get(url, params=params).json()

    foods = []

    for food in r["foods"]:
        nutrients = food.get("foodNutrients", [])
        nutrient_map = {n["nutrientName"]: n["value"] for n in nutrients}

        carbs = nutrient_map.get("Carbohydrate, by difference")
        protein = nutrient_map.get("Protein")
        calories = nutrient_map.get("Energy (kcal)") or nutrient_map.get("Energy")

        calories_from_carbs = carbs * 4 if carbs is not None else None

        if carbs is not None and carbs <= max_carbs:
            foods.append({
                "name": food["description"],
                "carbs_g": carbs,
                "protein_g": protein,
                "calories_kcal": calories,
                "calories_from_carbs": calories_from_carbs,
                "serving_size": food.get("servingSize"),
                "serving_unit": food.get("servingSizeUnit")
            })
    #MealAgent_logger.info(f"Tool result count: {len(foods)} foods returned")


    return foods


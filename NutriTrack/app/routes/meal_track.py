from flask import Blueprint, render_template, request, jsonify, current_app
from flask_login import login_required, current_user
from app import db
from app.models.record import Plate, DetectionRecord, DietRecord
from app.models.food import NutritionFacts, Dish, DishIngredient, Ingredient
from datetime import datetime
import os
import json

meal_track_bp = Blueprint('meal_track', __name__)

# Global model variable
model = None

def get_model():
    global model
    if model is None:
        try:
            from ultralytics import YOLO
            model_path = current_app.config['YOLO_MODEL_PATH']
            if os.path.exists(model_path):
                model = YOLO(model_path)
            else:
                print(f"Model file not found at {model_path}")
        except Exception as e:
            print(f"Error loading model: {e}")
    return model

@meal_track_bp.route('/meal_track')
@login_required
def index():
    plate = Plate.query.filter_by(user_id=current_user.id, bind_status=1).first()
    return render_template('meal_track.html', plate=plate)

@meal_track_bp.route('/calculate_nutrition', methods=['POST'])
@login_required
def calculate_nutrition():
    data = request.get_json()
    dishes = data.get('dishes', [])
    
    total_nutrition = {
        'calories': 0,
        'protein': 0,
        'fat': 0,
        'carb': 0
    }
    
    details = []
    
    for dish_input in dishes:
        dish_name = dish_input.get('dish_name')
        actual_weight = float(dish_input.get('weight', 0))
        
        dish_details = {
            'dish_name': dish_name,
            'calories': 0,
            'protein': 0,
            'fat': 0,
            'carb': 0,
            'ingredients': []
        }
        
        # 1. Get Dish
        dish = Dish.query.filter_by(name=dish_name).first()
        if dish:
            # 2. Get Recipe (DishIngredients)
            recipe_items = DishIngredient.query.filter_by(dish_id=dish.dish_id).all()
            
            # Calculate Total Recipe Weight
            recipe_total_weight = sum(item.amount_g for item in recipe_items)
            
            if recipe_total_weight > 0:
                # 3. Calculate Scaling Ratio
                ratio = actual_weight / recipe_total_weight
                
                # 4. Calculate Contribution of each ingredient
                for item in recipe_items:
                    ingredient = Ingredient.query.get(item.ingredient_id)
                    nutrition = NutritionFacts.query.get(item.ingredient_id)
                    
                    if ingredient and nutrition:
                        # Actual ingredient amount in this portion
                        actual_ing_amount = item.amount_g * ratio
                        
                        # Contribution = (Per 100g * Actual Amount) / 100
                        # which simplifies to: Per 100g * (Actual Amount / 100)
                        factor = actual_ing_amount / 100.0
                        
                        ing_cal = nutrition.energy_kcal * factor
                        ing_prot = nutrition.protein_g * factor
                        ing_fat = nutrition.fat_g * factor
                        ing_carb = nutrition.carb_g * factor
                        
                        # Add to dish total
                        dish_details['calories'] += ing_cal
                        dish_details['protein'] += ing_prot
                        dish_details['fat'] += ing_fat
                        dish_details['carb'] += ing_carb
                        
                        dish_details['ingredients'].append({
                            'name': ingredient.ingredient_name,
                            'amount': round(actual_ing_amount, 1),
                            'calories': round(ing_cal, 1)
                        })
        
        # Add dish totals to grand total
        total_nutrition['calories'] += dish_details['calories']
        total_nutrition['protein'] += dish_details['protein']
        total_nutrition['fat'] += dish_details['fat']
        total_nutrition['carb'] += dish_details['carb']
        
        # Round dish details
        dish_details['calories'] = round(dish_details['calories'], 1)
        dish_details['protein'] = round(dish_details['protein'], 1)
        dish_details['fat'] = round(dish_details['fat'], 1)
        dish_details['carb'] = round(dish_details['carb'], 1)
        
        details.append(dish_details)
        
    return jsonify({
        'status': 'success',
        'total': total_nutrition,
        'details': details
    })


@meal_track_bp.route('/bind_plate', methods=['POST'])
@login_required
def bind_plate():
    plate_id = request.form.get('plate_id')
    action = request.form.get('action') # bind or unbind
    
    plate = Plate.query.filter_by(plate_id=plate_id).first()
    
    if action == 'bind':
        if not plate:
            plate = Plate(plate_id=plate_id)
            db.session.add(plate)
        
        plate.user_id = current_user.id
        plate.bind_time = datetime.now()
        plate.bind_status = 1
        db.session.commit()
        return jsonify({'status': 'success', 'message': 'Plate bound successfully'})
        
    elif action == 'unbind':
        if plate and plate.user_id == current_user.id:
            plate.bind_status = 0
            plate.user_id = None
            db.session.commit()
            return jsonify({'status': 'success', 'message': 'Plate unbound successfully'})
            
    return jsonify({'status': 'error', 'message': 'Invalid operation'})

@meal_track_bp.route('/weight_log', methods=['POST'])
def weight_log():
    # Hardware interface
    data = request.get_json()
    plate_id = data.get('plate_id')
    weight = data.get('weight')
    
    plate = Plate.query.filter_by(plate_id=plate_id).first()
    if plate and plate.bind_status == 1:
        plate.current_weight = weight
        
        # Log to detection records if needed, or just update real-time state
        # For this example, we might create a record or append to an existing active session
        # Simplified: just update plate current weight
        db.session.commit()
        return jsonify({'status': 'success'})
        
    return jsonify({'status': 'error', 'message': 'Plate not found or not bound'})

@meal_track_bp.route('/get_weight_data')
@login_required
def get_weight_data():
    plate = Plate.query.filter_by(user_id=current_user.id, bind_status=1).first()
    if plate:
        return jsonify({'weight': plate.current_weight})
    return jsonify({'weight': 0})

@meal_track_bp.route('/detect_dish', methods=['POST'])
@login_required
def detect_dish():
    if 'image' not in request.files:
        return jsonify({'status': 'error', 'message': 'No image uploaded'})
        
    file = request.files['image']
    if file.filename == '':
        return jsonify({'status': 'error', 'message': 'No selected file'})

    # Save temp file
    temp_path = os.path.join(current_app.static_folder, 'temp_detect.jpg')
    file.save(temp_path)
    
    model = get_model()
    detected_dishes = []
    
    if model:
        try:
            results = model(temp_path)
            # Parse results
            # Assuming model returns class names that match Dish names
            # This is a simplification. In real world, we need class_id to Dish mapping.
            # Mocking the result parsing for now based on YOLO structure
            for r in results:
                for box in r.boxes:
                    cls_id = int(box.cls[0])
                    conf = float(box.conf[0])
                    class_name = model.names[cls_id]
                    
                    # Find dish in DB
                    # dish = Dish.query.filter_by(name=class_name).first()
                    # For demo purposes, returning the class name
                    detected_dishes.append({
                        'dish_name': class_name,
                        'confidence': round(conf, 2),
                        'weight': 100 # Mock weight estimation or need input
                    })
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)})
    else:
        # Mock response if model is missing
        # Using real dish names from DB for demonstration of nutrition calculation
        detected_dishes = [
            {'dish_name': 'Kung Pao Chicken', 'confidence': 0.95, 'weight': 250},
            {'dish_name': 'Mapo Tofu', 'confidence': 0.88, 'weight': 250}
        ]
        
    return jsonify({'status': 'success', 'results': detected_dishes})

@meal_track_bp.route('/calculate_nutrition', methods=['POST'])
@login_required
def calculate_nutrition():
    data = request.get_json()
    dishes = data.get('dishes', [])
    
    total_nutrition = {'calories': 0, 'protein': 0, 'fat': 0, 'carb': 0}
    detailed_nutrition = []
    
    for item in dishes:
        dish_name = item.get('dish_name')
        weight = float(item.get('weight', 0))
        
        # Logic to fetch nutrition based on dish_name and weight
        # This requires complex mapping between Dish -> Ingredients -> Nutrition
        # Simplified: Random/Mock data or simple lookup if data existed
        
        # Mock calculation
        nut = {
            'calories': weight * 1.5,
            'protein': weight * 0.1,
            'fat': weight * 0.05,
            'carb': weight * 0.2
        }
        
        total_nutrition['calories'] += nut['calories']
        total_nutrition['protein'] += nut['protein']
        total_nutrition['fat'] += nut['fat']
        total_nutrition['carb'] += nut['carb']
        
        detailed_nutrition.append({
            'dish_name': dish_name,
            'weight': weight,
            **nut
        })
        
    return jsonify({
        'status': 'success',
        'total': total_nutrition,
        'details': detailed_nutrition
    })

@meal_track_bp.route('/save_meal_record', methods=['POST'])
@login_required
def save_meal_record():
    data = request.get_json()
    meal_type = data.get('meal_type')
    dish_list = data.get('dish_list') # List of dishes
    totals = data.get('totals')
    
    record = DietRecord(
        user_id=current_user.id,
        meal_type=meal_type,
        total_calorie=totals.get('calories'),
        total_protein=totals.get('protein'),
        total_fat=totals.get('fat'),
        total_carb=totals.get('carb')
    )
    record.set_dish_list(dish_list)
    
    db.session.add(record)
    db.session.commit()
    
    return jsonify({'status': 'success', 'message': 'Record saved'})

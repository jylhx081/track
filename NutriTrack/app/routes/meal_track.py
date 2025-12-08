from flask import Blueprint, render_template, request, jsonify, current_app
from flask_login import login_required, current_user
from datetime import datetime
from sqlalchemy import func
import json
import os
from ultralytics import YOLO
from app.models.record import Plate, DetectionRecord, DietRecord
from app.models.food import NutritionFacts, Dish, DishIngredient, Ingredient
from app import db

# 创建蓝图
meal_track_bp = Blueprint('meal_track', __name__)


# ====================== 用餐追踪首页 ======================
@meal_track_bp.route('/')
@meal_track_bp.route('/index')
@login_required
def index():
    """用餐追踪页面"""
    return render_template('meal_track.html')


# ====================== 菜品识别接口 ======================
@meal_track_bp.route('/detect_dish', methods=['POST'])
@login_required
def detect_dish():
    if 'image' not in request.files:
        return jsonify({'status': 'error', 'message': '未上传图片'})

    file = request.files['image']
    if file.filename == '':
        return jsonify({'status': 'error', 'message': '未选择文件'})

    upload_dir = os.path.join(current_app.static_folder, 'uploads')
    os.makedirs(upload_dir, exist_ok=True)
    filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename.replace(' ', '_')}"
    save_path = os.path.join(upload_dir, filename)

    try:
        from PIL import Image
        img = Image.open(file)
        img = img.convert('RGB')
        img.save(save_path, format='JPEG')
    except Exception:
        file.save(save_path)

    image_url = f"/static/uploads/{filename}"

    model_path = os.path.join(current_app.static_folder, 'best.pt')
    if not os.path.exists(model_path):
        return jsonify({
            'status': 'error',
            'message': f'模型文件不存在：{model_path}',
            'image_url': image_url
        })

    try:
        model = YOLO(model_path)
        results = model(save_path, conf=0.3)
        detected_items = []

        for box in results[0].boxes:
            cls_id = int(box.cls[0])
            conf = round(float(box.conf[0]), 2)
            class_name = model.names[cls_id]

            target_name = class_name.strip().lower()
            dish = Dish.query.filter(
                func.lower(func.trim(Dish.name)) == target_name
            ).first()

            detected_items.append({
                'dish_name': class_name,
                'confidence': conf,
                'weight': 100,
                'has_db_data': True if dish else False
            })

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'识别失败：{str(e)}',
            'image_url': image_url
        })

    new_record = DetectionRecord(
        user_id=current_user.id,
        detected_objects=json.dumps(detected_items),
        detect_time=datetime.now()
    )
    db.session.add(new_record)
    db.session.commit()

    return jsonify({
        'status': 'success',
        'results': detected_items,
        'image_url': image_url
    })


# ====================== 营养计算接口（核心修复） ======================
@meal_track_bp.route('/calculate_nutrition', methods=['POST'])
# @login_required
def calculate_nutrition():
    data = request.get_json()
    dishes = data.get('dishes', [])

    total_nutrition = {
        'calories': 0.0,
        'protein': 0.0,
        'fat': 0.0,
        'carb': 0.0
    }
    dish_details = []

    for dish_input in dishes:
        dish_name = dish_input.get('dish_name', '')
        actual_weight = float(dish_input.get('weight', 0))

        single_dish = {
            'dish_name': dish_name,
            'calories': 0.0,
            'protein': 0.0,
            'fat': 0.0,
            'carb': 0.0,
            'weight': actual_weight
        }

        target_name = dish_name.strip().lower()
        dish = Dish.query.filter(
            func.lower(func.trim(Dish.name)) == target_name
        ).first()

        if not dish:
            dish_details.append(single_dish)
            continue

        recipe_items = DishIngredient.query.filter_by(dish_id=dish.dish_id).all()
        if not recipe_items:
            dish_details.append(single_dish)
            continue

        recipe_total_weight = sum(item.amount_g for item in recipe_items)
        if recipe_total_weight <= 0:
            dish_details.append(single_dish)
            continue

        scale_ratio = actual_weight / recipe_total_weight

        for item in recipe_items:
            ingredient = Ingredient.query.get(item.ingredient_id)
            nutrition = NutritionFacts.query.get(item.ingredient_id)

            if not ingredient or not nutrition:
                continue

            actual_ing_weight = item.amount_g * scale_ratio
            factor = actual_ing_weight / 100

            single_dish['calories'] += nutrition.energy_kcal * factor
            single_dish['protein'] += nutrition.protein_g * factor
            single_dish['fat'] += nutrition.fat_g * factor
            single_dish['carb'] += nutrition.carb_g * factor

        # 四舍五入保留1位小数
        single_dish['calories'] = round(single_dish['calories'], 1)
        single_dish['protein'] = round(single_dish['protein'], 1)
        single_dish['fat'] = round(single_dish['fat'], 1)
        single_dish['carb'] = round(single_dish['carb'], 1)

        total_nutrition['calories'] += single_dish['calories']
        total_nutrition['protein'] += single_dish['protein']
        total_nutrition['fat'] += single_dish['fat']
        total_nutrition['carb'] += single_dish['carb']

        dish_details.append(single_dish)

    total_nutrition['calories'] = round(total_nutrition['calories'], 1)
    total_nutrition['protein'] = round(total_nutrition['protein'], 1)
    total_nutrition['fat'] = round(total_nutrition['fat'], 1)
    total_nutrition['carb'] = round(total_nutrition['carb'], 1)

    return jsonify({
        'status': 'success',
        'total': total_nutrition,
        'details': dish_details
    })


# ====================== 保存用餐记录接口 ======================
@meal_track_bp.route('/save_meal_record', methods=['POST'])
@login_required
def save_meal_record():
    data = request.get_json()
    meal_type = data.get('meal_type')
    dish_list = data.get('dish_list', [])
    totals = data.get('totals', {})

    new_record = DietRecord(
        user_id=current_user.id,
        meal_type=meal_type,
        dish_list=json.dumps(dish_list),
        total_calorie=totals.get('calories', 0),
        total_protein=totals.get('protein', 0),
        total_fat=totals.get('fat', 0),
        total_carb=totals.get('carb', 0),
        create_time=datetime.now()
    )

    db.session.add(new_record)
    db.session.commit()

    return jsonify({'status': 'success', 'message': '记录保存成功'})
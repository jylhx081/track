from flask import Blueprint, render_template, request, jsonify, current_app
from flask_login import login_required, current_user
from app import db
from app.models.record import Plate, DetectionRecord, DietRecord
from app.models.food import NutritionFacts, Dish, DishIngredient, Ingredient
from datetime import datetime
import os
import json
from ultralytics import YOLO
from sqlalchemy import func

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
    dishes = data.get('dishes', [])  # 从前端获取识别的菜品及重量

    total_nutrition = {
        'calories': 0,
        'protein': 0,
        'fat': 0,
        'carb': 0
    }
    details = []  # 存储每个菜品的详细营养成分

    for dish_input in dishes:
        dish_name = dish_input.get('dish_name')
        actual_weight = float(dish_input.get('weight', 0))  # 菜品实际重量（g）
        dish_details = {
            'dish_name': dish_name,
            'calories': 0,
            'protein': 0,
            'fat': 0,
            'carb': 0,
            'ingredients': []  # 记录该菜品包含的食材及营养贡献
        }

        # 1. 查询数据库中的菜品信息
        dish = Dish.query.filter_by(name=dish_name).first()
        if not dish:
            # 若菜品未在数据库中，跳过计算（可添加提示逻辑）
            details.append(dish_details)
            continue

        # 2. 获取菜品配方（食材及标准用量）
        recipe_items = DishIngredient.query.filter_by(dish_id=dish.dish_id).all()
        if not recipe_items:
            details.append(dish_details)
            continue

        # 3. 计算配方总重量（用于缩放）
        recipe_total_weight = sum(item.amount_g for item in recipe_items)
        if recipe_total_weight <= 0:
            details.append(dish_details)
            continue

        # 4. 计算缩放比例（实际重量 ÷ 配方总重量）
        scale_ratio = actual_weight / recipe_total_weight

        # 5. 按比例计算每种食材的实际用量及营养贡献
        for item in recipe_items:
            # 查询食材及营养数据
            ingredient = Ingredient.query.get(item.ingredient_id)
            nutrition = NutritionFacts.query.get(item.ingredient_id)
            if not ingredient or not nutrition:
                continue

            # 食材实际用量 = 标准用量 × 缩放比例
            actual_ingredient_weight = item.amount_g * scale_ratio

            # 营养成分计算：(每100g含量 × 实际用量) ÷ 100
            factor = actual_ingredient_weight / 100
            ing_cal = nutrition.energy_kcal * factor  # 热量（kcal）
            ing_prot = nutrition.protein_g * factor  # 蛋白质（g）
            ing_fat = nutrition.fat_g * factor  # 脂肪（g）
            ing_carb = nutrition.carb_g * factor  # 碳水（g）

            # 累加至菜品总营养
            dish_details['calories'] += ing_cal
            dish_details['protein'] += ing_prot
            dish_details['fat'] += ing_fat
            dish_details['carb'] += ing_carb

            # 记录该食材的贡献（用于前端展示明细）
            dish_details['ingredients'].append({
                'name': ingredient.ingredient_name,
                'amount': round(actual_ingredient_weight, 1),  # 实际用量（g）
                'calories': round(ing_cal, 1)
            })

        # 6. 四舍五入菜品营养数据
        dish_details['calories'] = round(dish_details['calories'], 1)
        dish_details['protein'] = round(dish_details['protein'], 1)
        dish_details['fat'] = round(dish_details['fat'], 1)
        dish_details['carb'] = round(dish_details['carb'], 1)

        # 7. 累加至总营养
        total_nutrition['calories'] += dish_details['calories']
        total_nutrition['protein'] += dish_details['protein']
        total_nutrition['fat'] += dish_details['fat']
        total_nutrition['carb'] += dish_details['carb']

        details.append(dish_details)

    return jsonify({
        'status': 'success',
        'total': total_nutrition,  # 所有菜品总营养
        'details': details  # 每个菜品的详细营养
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
    # 1. 检查文件上传
    if 'image' not in request.files:
        return jsonify({'status': 'error', 'message': '未上传图片'})

    file = request.files['image']
    if file.filename == '':
        return jsonify({'status': 'error', 'message': '未选择文件'})

    # 2. 保存上传的图片（确保路径可写）
    upload_dir = os.path.join(current_app.static_folder, 'uploads')
    os.makedirs(upload_dir, exist_ok=True)  # 简化创建目录的逻辑

    # 生成唯一文件名，避免重复
    filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename.replace(' ', '_')}"
    save_path = os.path.join(upload_dir, filename)

    # 强制转换为JPG格式（避免模型不支持的格式）
    try:
        from PIL import Image
        img = Image.open(file)
        img = img.convert('RGB')  # 去除透明通道
        img.save(save_path, format='JPEG')
    except Exception as e:
        # 兼容非图片文件的情况
        file.save(save_path)

    # 前端访问图片的URL
    image_url = f"/static/uploads/{filename}"

    # 3. 直接加载模型（跳过get_model，避免全局变量问题）
    model_path = os.path.join(current_app.static_folder, 'best.pt')
    if not os.path.exists(model_path):
        return jsonify({
            'status': 'error',
            'message': f'模型文件不存在：{model_path}',
            'image_url': image_url
        })

    try:
        model = YOLO(model_path)
        # 4. 执行识别（使用和测试代码相同的置信度阈值）
        results = model(save_path, conf=0.3)  # 阈值和测试代码一致
        detected_items = []

        # 5. 解析识别结果（和测试代码逻辑完全一致）
        print(f"模型识别到 {len(results[0].boxes)} 个目标")  # 终端打印，方便调试
        for box in results[0].boxes:
            cls_id = int(box.cls[0])
            conf = round(float(box.conf[0]), 2)
            class_name = model.names[cls_id]

            # 6. 数据库匹配（兼容大小写/空格）
            target_name = class_name.strip().lower()
            # 2. 数据库字段用func.lower/func.trim处理
            dish = Dish.query.filter(
                func.lower(func.trim(Dish.name)) == target_name
            ).first()

            # 即使数据库没有匹配，也先返回识别结果（避免前端无数据）
            detected_items.append({
                'dish_name': class_name,
                'confidence': conf,
                'weight': 100,
                'has_db_data': True if dish else False  # 标记是否有数据库数据
            })

    except Exception as e:
        print(f"识别出错：{str(e)}")  # 终端打印错误
        return jsonify({
            'status': 'error',
            'message': f'识别失败：{str(e)}',
            'image_url': image_url
        })

    # 7. 保存检测记录（即使无数据库匹配，也保存原始识别结果）
    new_record = DetectionRecord(
        user_id=current_user.id,
        detected_objects=json.dumps(detected_items),
        detect_time=datetime.now()
    )
    db.session.add(new_record)
    db.session.commit()

    # 8. 返回结果（确保results不为空）
    return jsonify({
        'status': 'success',
        'results': detected_items,
        'image_url': image_url
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

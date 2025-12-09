from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from app import db
from app.models.record import DietRecord
from app.models.user import User
from datetime import datetime, date, timedelta

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/')
@dashboard_bp.route('/dashboard')
@login_required
def index():
    # 获取请求的日期参数，默认为今天
    date_str = request.args.get('date')
    if date_str:
        try:
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            target_date = date.today()
    else:
        target_date = date.today()

    # BMI Calculation
    bmi = 0
    if current_user.height and current_user.weight:
        height_m = current_user.height / 100
        bmi = round(current_user.weight / (height_m * height_m), 1)

    # BMR Calculation (使用用户模型中已计算的BMR)
    bmr = current_user.bmr if current_user.bmr else 0

    # 计算每日所需营养素
    nutrition_needs = calculate_daily_nutrition(bmr, current_user.health_goal)

    # 获取指定日期的记录
    records = DietRecord.query.filter(
        DietRecord.user_id == current_user.id,
        db.func.date(DietRecord.create_time) == target_date
    ).all()

    today_nutrition = {
        'calories': 0,
        'protein': 0,
        'fat': 0,
        'carb': 0
    }

    meals = {1: [], 2: [], 3: []}  # Breakfast, Lunch, Dinner

    for record in records:
        today_nutrition['calories'] += record.total_calorie or 0
        today_nutrition['protein'] += record.total_protein or 0
        today_nutrition['fat'] += record.total_fat or 0
        today_nutrition['carb'] += record.total_carb or 0

        if record.meal_type in meals:
            meals[record.meal_type].append(record)

    # 计算营养缺口
    nutrition_gaps = {
        'calories': max(0, nutrition_needs['calories'] - today_nutrition['calories']),
        'protein': max(0, nutrition_needs['protein'] - today_nutrition['protein']),
        'fat': max(0, nutrition_needs['fat'] - today_nutrition['fat']),
        'carb': max(0, nutrition_needs['carb'] - today_nutrition['carb'])
    }

    # 获取前后几天的日期用于导航
    prev_date = target_date - timedelta(days=1)
    next_date = target_date + timedelta(days=1)

    def safe_percent(actual, target):
        if not target or target <= 0:
            return 0
        return min(100, int((actual / target) * 100))

    nutrition_percents = {
        'protein': safe_percent(today_nutrition['protein'], nutrition_needs['protein']),
        'fat': safe_percent(today_nutrition['fat'], nutrition_needs['fat']),
        'carb': safe_percent(today_nutrition['carb'], nutrition_needs['carb']),
        'calories': safe_percent(today_nutrition['calories'], nutrition_needs['calories']),
    }

    return render_template('dashboard.html',
                           bmi=bmi,
                           bmr=bmr,
                           nutrition_needs=nutrition_needs,
                           nutrition_gaps=nutrition_gaps,
                           today_nutrition=today_nutrition,
                           nutrition_percents=nutrition_percents,
                           meals=meals,
                           target_date=target_date,
                           prev_date=prev_date,
                           next_date=next_date,
                           today_date=target_date.strftime('%Y-%m-%d'))


def calculate_daily_nutrition(bmr, health_goal):
    """根据BMR和健康目标计算每日所需营养素"""
    # 基础热量需求
    calories = bmr

    # 根据健康目标调整热量需求
    if health_goal == '减脂':
        calories = int(bmr * 0.8)  # 减少20%热量摄入
    elif health_goal == '增肌':
        calories = int(bmr * 1.2)  # 增加20%热量摄入
    elif health_goal == '更健康':
        calories = bmr  # 维持当前热量摄入
    elif health_goal == '维持体重':
        calories = bmr  # 维持当前热量摄入

    # 计算宏量营养素分配（默认比例）
    protein_ratio = 0.25  # 蛋白质占25%
    fat_ratio = 0.25      # 脂肪占25%
    carb_ratio = 0.50     # 碳水化合物占50%

    # 根据健康目标调整宏量营养素比例
    if health_goal == '增肌':
        protein_ratio = 0.30  # 增加蛋白质比例
        fat_ratio = 0.20
        carb_ratio = 0.50
    elif health_goal == '减脂':
        protein_ratio = 0.35  # 增加蛋白质比例帮助保持肌肉
        fat_ratio = 0.25
        carb_ratio = 0.40

    protein = int((calories * protein_ratio) / 4)  # 每克蛋白质4千卡
    fat = int((calories * fat_ratio) / 9)          # 每克脂肪9千卡
    carb = int((calories * carb_ratio) / 4)        # 每克碳水化合物4千卡

    return {
        'calories': calories,
        'protein': protein,
        'fat': fat,
        'carb': carb
    }


@dashboard_bp.route('/update_health_goal', methods=['POST'])
@login_required
def update_health_goal():
    goal = request.form.get('health_goal')
    current_user.health_goal = goal
    db.session.commit()
    flash('健康目标更新成功！', 'success')
    return redirect(url_for('dashboard.index'))

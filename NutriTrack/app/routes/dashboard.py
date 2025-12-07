from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from app import db
from app.models.record import DietRecord
from datetime import datetime, date

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/')
@dashboard_bp.route('/dashboard')
@login_required
def index():
    # BMI Calculation
    bmi = 0
    if current_user.height and current_user.weight:
        height_m = current_user.height / 100
        bmi = round(current_user.weight / (height_m * height_m), 1)
    
    # BMR Calculation
    bmr = 0
    if current_user.weight and current_user.height and current_user.age and current_user.gender:
        if current_user.gender == 'Male':
            bmr = 10 * current_user.weight + 6.25 * current_user.height - 5 * current_user.age + 5
        else:
            bmr = 10 * current_user.weight + 6.25 * current_user.height - 5 * current_user.age - 161
    bmr = int(bmr)

    # Today's records
    today = date.today()
    records = DietRecord.query.filter(
        DietRecord.user_id == current_user.id,
        db.func.date(DietRecord.create_time) == today
    ).all()
    
    today_nutrition = {
        'calories': 0,
        'protein': 0,
        'fat': 0,
        'carb': 0
    }
    
    meals = {1: [], 2: [], 3: []} # Breakfast, Lunch, Dinner
    
    for record in records:
        today_nutrition['calories'] += record.total_calorie or 0
        today_nutrition['protein'] += record.total_protein or 0
        today_nutrition['fat'] += record.total_fat or 0
        today_nutrition['carb'] += record.total_carb or 0
        
        if record.meal_type in meals:
            meals[record.meal_type].append(record)

    return render_template('dashboard.html', 
                           bmi=bmi, 
                           bmr=bmr, 
                           today_nutrition=today_nutrition,
                           meals=meals,
                           today_date=today.strftime('%Y-%m-%d'))

@dashboard_bp.route('/update_health_goal', methods=['POST'])
@login_required
def update_health_goal():
    goal = request.form.get('health_goal')
    current_user.health_goal = goal
    db.session.commit()
    flash('Health goal updated!', 'success')
    return redirect(url_for('dashboard.index'))

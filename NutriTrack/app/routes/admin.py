from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
from app import db
from app.models.user import User
from app.models.record import DetectionRecord
from functools import wraps
from datetime import datetime, timedelta

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.is_admin != 1:
            flash('Access denied. Admin privileges required.', 'danger')
            return redirect(url_for('dashboard.index'))
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    total_users = User.query.count()
    active_users = User.query.filter_by(status=1).count()
    detection_count = DetectionRecord.query.count()
    admin_count = User.query.filter_by(is_admin=1).count()
    
    return render_template('admin_dashboard.html',
                           total_users=total_users,
                           active_users=active_users,
                           detection_count=detection_count,
                           admin_count=admin_count)

@admin_bp.route('/user_manage')
@login_required
@admin_required
def user_manage():
    page = request.args.get('page', 1, type=int)
    users = User.query.paginate(page=page, per_page=10)
    return render_template('admin_user_manage.html', users=users)

@admin_bp.route('/update_user', methods=['POST'])
@login_required
@admin_required
def update_user():
    user_id = request.form.get('user_id')
    action = request.form.get('action')
    
    user = User.query.get(user_id)
    if user:
        if action == 'toggle_status':
            user.status = 1 if user.status == 0 else 0
        elif action == 'toggle_admin':
            user.is_admin = 1 if user.is_admin == 0 else 0
        elif action == 'delete':
            db.session.delete(user)
            
        db.session.commit()
        flash('User updated successfully', 'success')
    else:
        flash('User not found', 'danger')
        
    return redirect(url_for('admin.user_manage'))

@admin_bp.route('/detection_records')
@login_required
@admin_required
def detection_records():
    page = request.args.get('page', 1, type=int)
    records = DetectionRecord.query.order_by(DetectionRecord.detect_time.desc()).paginate(page=page, per_page=10)
    return render_template('admin_detection_records.html', records=records)

@admin_bp.route('/statistics')
@login_required
@admin_required
def statistics():
    # Last 7 days detection counts
    end_date = datetime.now()
    start_date = end_date - timedelta(days=6)
    
    dates = []
    counts = []
    
    current = start_date
    while current <= end_date:
        d_str = current.strftime('%Y-%m-%d')
        dates.append(d_str)
        
        count = DetectionRecord.query.filter(
            db.func.date(DetectionRecord.detect_time) == current.date()
        ).count()
        counts.append(count)
        
        current += timedelta(days=1)
        
    return jsonify({
        'labels': dates,
        'data': counts
    })

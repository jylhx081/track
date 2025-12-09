from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db, login_manager
from datetime import datetime


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    height = db.Column(db.Float)
    weight = db.Column(db.Float)
    age = db.Column(db.Integer)
    gender = db.Column(db.String(10))
    health_goal = db.Column(db.String(100))  # 健康目标（减脂、增肌、更健康等）

    # 个人信息扩展字段
    bmi = db.Column(db.Float)  # BMI指数
    bmi_category = db.Column(db.String(20))  # BMI分类
    bmr = db.Column(db.Integer)  # 基础代谢率

    # 饮食习惯相关字段
    dietary_preference = db.Column(db.String(100))  # 饮食偏好
    allergies = db.Column(db.String(255))  # 过敏食物
    favorite_foods = db.Column(db.String(255))  # 喜爱的食物

    # 运动习惯相关字段（运动频率移到这里）
    exercise_frequency = db.Column(db.String(50))  # 运动频率
    exercise_level = db.Column(db.String(20))  # 运动强度

    # 健康目标相关字段
    target_weight = db.Column(db.Float)  # 目标体重
    goal_deadline = db.Column(db.DateTime)  # 目标期限

    is_admin = db.Column(db.Integer, default=0)  # 0 = User, 1 = Admin
    register_time = db.Column(db.DateTime, default=datetime.now)
    last_login_time = db.Column(db.DateTime)
    status = db.Column(db.Integer, default=1)  # 0 = Disabled, 1 = Active

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def password(self):
        raise AttributeError('password is not a readable attribute')

    @password.setter
    def password(self, password):
        self.set_password(password)

    def __repr__(self):
        return f'<User {self.username}>'


@login_manager.user_loader
def load_user(id):
    return User.query.get(int(id))

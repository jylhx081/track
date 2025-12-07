from app import db
from datetime import datetime
import json

class Plate(db.Model):
    __tablename__ = 'plate'
    plate_id = db.Column(db.String(50), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    bind_time = db.Column(db.DateTime)
    current_weight = db.Column(db.Float, default=0.0)
    bind_status = db.Column(db.Integer, default=0) # 0 = Unbound, 1 = Bound

class DetectionRecord(db.Model):
    __tablename__ = 'detection_records'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    plate_id = db.Column(db.String(50), db.ForeignKey('plate.plate_id'))
    bind_time = db.Column(db.DateTime)
    current_weight = db.Column(db.Float)
    weight_log = db.Column(db.Text) # JSON format
    detected_objects = db.Column(db.Text) # JSON format
    detect_time = db.Column(db.DateTime, default=datetime.now)

    def set_weight_log(self, data):
        self.weight_log = json.dumps(data)

    def get_weight_log(self):
        return json.loads(self.weight_log) if self.weight_log else []

    def set_detected_objects(self, data):
        self.detected_objects = json.dumps(data)

    def get_detected_objects(self):
        return json.loads(self.detected_objects) if self.detected_objects else []

class DietRecord(db.Model):
    __tablename__ = 'diet_records'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    meal_type = db.Column(db.Integer) # 1 = Breakfast, 2 = Lunch, 3 = Dinner
    dish_list = db.Column(db.Text) # JSON
    total_calorie = db.Column(db.Float)
    total_protein = db.Column(db.Float)
    total_fat = db.Column(db.Float)
    total_carb = db.Column(db.Float)
    create_time = db.Column(db.DateTime, default=datetime.now)

    def set_dish_list(self, data):
        self.dish_list = json.dumps(data)

    def get_dish_list(self):
        return json.loads(self.dish_list) if self.dish_list else []

class DietHabit(db.Model):
    __tablename__ = 'diet_habits'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    habit_content = db.Column(db.Text)
    create_time = db.Column(db.DateTime, default=datetime.now)

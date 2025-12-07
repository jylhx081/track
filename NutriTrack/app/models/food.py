from app import db

class Canteen(db.Model):
    __tablename__ = 'canteens'
    canteen_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)

class Dish(db.Model):
    __tablename__ = 'dishes'
    dish_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    canteen_id = db.Column(db.Integer, db.ForeignKey('canteens.canteen_id'))

class Ingredient(db.Model):
    __tablename__ = 'ingredients'
    ingredient_id = db.Column(db.Integer, primary_key=True)
    ingredient_name = db.Column(db.String(100), nullable=False)

class DishIngredient(db.Model):
    __tablename__ = 'dish_ingredients'
    dish_id = db.Column(db.Integer, db.ForeignKey('dishes.dish_id'), primary_key=True)
    ingredient_id = db.Column(db.Integer, db.ForeignKey('ingredients.ingredient_id'), primary_key=True)
    amount_g = db.Column(db.Float, nullable=False)

class NutritionFacts(db.Model):
    __tablename__ = 'nutrition_facts'
    ingredient_id = db.Column(db.Integer, db.ForeignKey('ingredients.ingredient_id'), primary_key=True)
    energy_kcal = db.Column(db.Float, nullable=False)
    protein_g = db.Column(db.Float, nullable=False)
    fat_g = db.Column(db.Float, nullable=False)
    carb_g = db.Column(db.Float, nullable=False)

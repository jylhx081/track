import os

class Config:
    # Database configuration
    SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://root:123456@localhost/monisys?charset=utf8mb4'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Secret key for session management
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-nutritrack'
    
    # YOLO Model Path
    YOLO_MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app', 'static', 'best.pt')

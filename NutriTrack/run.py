from app import create_app, db
from app.models.user import User

app = create_app()

if __name__ == '__main__':
    with app.app_context():
        # Create tables if they don't exist
        db.create_all()
        
        # Create default admin if not exists
        if not User.query.filter_by(username='admin').first():
            print("Creating default admin user...")
            admin = User(username='admin', email='admin@example.com', is_admin=1)
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
            print("Admin created: admin / admin123")
            
    app.run(debug=True)

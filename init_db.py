# init_db.py
from movie_lottery import create_app, db

app = create_app()
with app.app_context():
    db.create_all()
    print("✅ Tables created")

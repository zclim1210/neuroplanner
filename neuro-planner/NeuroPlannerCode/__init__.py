from flask import Flask, send_from_directory
from flask_bcrypt import Bcrypt
from pymongo import MongoClient
from dotenv import load_dotenv
import os
from certifi import where
from datetime import timedelta

bcrypt = Bcrypt()

def create_app():
    load_dotenv()
    
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)  # Keep session for 7 days

    print(f"SECRET_KEY: {app.config['SECRET_KEY']}")
    
    # MongoDB setup
    mongo_uri = os.getenv('MONGO_URI')
    print(f"MONGO_URI: {mongo_uri}")
    
    try:
        client = MongoClient(mongo_uri, tlsCAFile=where())
        app.db = client['NeoroPlanner']
        print("MongoDB connection successful.")
        app.db.users.create_index([("email", 1)], unique=True)
    except Exception as e:
        print(f"MongoDB connection failed: {e}")
        raise

    bcrypt.init_app(app)

    with app.app_context():
        from .auth import auth_blueprint
        from .views import views_blueprint

        app.register_blueprint(auth_blueprint, url_prefix='/auth')
        app.register_blueprint(views_blueprint, url_prefix='/')

    # Route to serve static React files
    @app.route('/dist/<path:path>')
    def serve_static(path):
        return send_from_directory('dist', path)

    return app

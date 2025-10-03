import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from werkzeug.middleware.proxy_fix import ProxyFix

from .diagnostic_middleware import start_diagnostics, checkpoint, finish_diagnostics

_diag = start_diagnostics()
db = SQLAlchemy()


def create_app():
    """
    Factory function for creating and configuring a Flask application instance.
    """
    checkpoint("create_app() started")
    
    app = Flask(__name__, instance_relative_config=True)
    checkpoint("Flask instance created")

    app.config.from_object('movie_lottery.config.Config')
    checkpoint("Config loaded")
    
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
    checkpoint("ProxyFix configured")

    db.init_app(app)
    checkpoint("SQLAlchemy initialized")
    
    Migrate(app, db)
    checkpoint("Flask-Migrate initialized")

    from . import models
    checkpoint("Models imported")
    
    from .routes.main_routes import main_bp
    checkpoint("main_routes imported")
    
    from .routes.api_routes import api_bp
    checkpoint("api_routes imported")
    
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp)
    checkpoint("Blueprints registered")
    
    finish_diagnostics()
    return app
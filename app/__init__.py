import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db, migrate


def create_app(test_config=None):
    load_dotenv()
    app = Flask(__name__)
    app.config.from_mapping(
        APP_ENV=os.getenv("APP_ENV", "development"),
        SECRET_KEY=os.getenv("SECRET_KEY"),
        SQLALCHEMY_DATABASE_URI=os.getenv("DATABASE_URL") or "sqlite:///lost_found.sqlite3",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        S3_BUCKET=os.getenv("S3_BUCKET"),
        AWS_DEFAULT_REGION=os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
        DEBUG=False,
    )
    if test_config:
        app.config.update(test_config)
    if app.config["APP_ENV"] == "production":
        if not app.config["SECRET_KEY"] or len(app.config["SECRET_KEY"]) < 32:
            raise ValueError("Production requires a generated SECRET_KEY of at least 32 characters.")
        database = make_url(app.config["SQLALCHEMY_DATABASE_URI"])
        if database.get_backend_name() == "sqlite":
            if not database.database or not Path(database.database).is_absolute():
                raise ValueError("Production SQLite needs an absolute path on persistent storage.")
        app.config.update(DEBUG=False, SESSION_COOKIE_SECURE=True)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    # Import models before migrations inspect the metadata.
    from app import models
    migrate.init_app(app, db, render_as_batch=True)

    from app.posts.routes import posts_bp
    from app.profiles.routes import profiles_bp
    from app.reports.routes import reports_bp

    app.register_blueprint(posts_bp)
    app.register_blueprint(profiles_bp)
    app.register_blueprint(reports_bp)

    @app.get("/healthz")
    def health():
        """Deployment readiness check; exposes no users, posts, or credentials."""
        try:
            # Unlike SELECT 1, this also verifies the initial migration was applied.
            db.session.execute(text("SELECT id FROM users LIMIT 1"))
        except SQLAlchemyError:
            db.session.rollback()
            return jsonify(status="unavailable"), 503
        return jsonify(status="ok"), 200

    return app

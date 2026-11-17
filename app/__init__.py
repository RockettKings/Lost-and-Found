import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, redirect, render_template, request, url_for
from flask_login import current_user
from flask_wtf.csrf import CSRFError
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.middleware.proxy_fix import ProxyFix

from app.extensions import csrf, db, limiter, login_manager, migrate


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
        MAX_CONTENT_LENGTH=11 * 1024 * 1024,
        DEBUG=False,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        PERMANENT_SESSION_LIFETIME=timedelta(hours=2),
        SESSION_REFRESH_EACH_REQUEST=True,
        REMEMBER_COOKIE_DURATION=timedelta(days=14),
        REMEMBER_COOKIE_HTTPONLY=True,
        REMEMBER_COOKIE_SAMESITE="Lax",
        RATELIMIT_STORAGE_URI=os.getenv("RATELIMIT_STORAGE_URI", "memory://"),
        RATELIMIT_HEADERS_ENABLED=True,
        # Open posts older than this are marked resolved automatically.
        POST_AUTO_CLOSE_DAYS=60,
        # Number of reverse proxies in front of the app (Render has one). Only trusted
        # in production, so a local client can't fake X-Forwarded-For to dodge limits.
        TRUSTED_PROXY_COUNT=int(os.getenv("TRUSTED_PROXY_COUNT", "1")),
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
        app.config.update(DEBUG=False, SESSION_COOKIE_SECURE=True, REMEMBER_COOKIE_SECURE=True)
        if app.config["TRUSTED_PROXY_COUNT"] > 0:
            # Behind Render's proxy every request comes from the proxy's IP; read the
            # real client IP so rate limits apply per user, not to everyone at once.
            app.wsgi_app = ProxyFix(app.wsgi_app, x_for=app.config["TRUSTED_PROXY_COUNT"],
                                    x_proto=1)

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)
    # Per-route limits are checked when the view runs, after CSRF; requests with no
    # valid token are refused by CSRF first and can't log in or post anyway.
    limiter.init_app(app)
    csrf.init_app(app)

    # Import models before migrations inspect the metadata.
    from app import models  # noqa: F401
    migrate.init_app(app, db, render_as_batch=True)

    from app.auth.routes import auth_bp
    from app.pages.routes import pages_bp
    from app.posts.routes import posts_bp
    from app.profiles.routes import profiles_bp
    from app.reports.routes import reports_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(pages_bp)
    app.register_blueprint(posts_bp)
    app.register_blueprint(profiles_bp)
    app.register_blueprint(reports_bp)

    from app.cli import register_cli
    from app.posts.expiry import maybe_close_expired_posts
    register_cli(app)

    @app.get("/")
    def index():
        # The browser loads post data from GET /posts/ using JavaScript.
        return render_template("index.html")

    @app.errorhandler(CSRFError)
    def handle_csrf_error(error):
        if request.path.startswith("/posts"):
            return jsonify(error="CSRF validation failed. Refresh the page and try again."), 400
        return render_template("403.html"), 400

    @app.errorhandler(429)
    def too_many_requests(_error):
        message = "Too many requests. Please wait a minute and try again."
        if request.path.startswith("/api/"):
            return jsonify(error=message), 429
        return render_template("429.html", message=message), 429

    # Everything except these needs a logged-in user. Unknown URLs (endpoint None)
    # fall through to the normal 404 page, which shows no post data.
    public_endpoints = {"auth.login", "auth.register", "static", "health", None}

    @app.before_request
    def require_login():
        if current_user.is_authenticated or request.endpoint in public_endpoints:
            return None
        if request.path.startswith("/api/"):
            return jsonify(error="Authentication required."), 401
        # Send visitors to the login page, then back to where they were going.
        target = request.full_path if request.query_string else request.path
        next_url = None if target == "/" else target
        return redirect(url_for("auth.login", next=next_url))

    @app.before_request
    def auto_close_old_posts():
        # Render's SQLite disk is attached to this web service only, so a separate cron
        # job can't reach it; the app closes expired posts itself, at most hourly.
        if request.endpoint in (None, "static", "health"):
            return
        maybe_close_expired_posts(app)

    @app.errorhandler(404)
    def page_not_found(_error):
        if request.path.startswith("/posts"):
            return jsonify(error="Post or endpoint not found."), 404
        return render_template("404.html"), 404

    @app.errorhandler(403)
    def forbidden(_error):
        if request.path.startswith("/posts"):
            return jsonify(error="You are not allowed to perform this action."), 403
        return render_template("403.html"), 403

    @app.get("/healthz")
    def health():
        """Deployment readiness check; exposes no users, posts, or credentials."""
        try:
            db.session.execute(text("SELECT id FROM users LIMIT 1"))
        except SQLAlchemyError:
            db.session.rollback()
            return jsonify(status="unavailable"), 503
        return jsonify(status="ok"), 200

    return app

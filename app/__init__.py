from flask import Flask

def create_app():
    app = Flask(__name__)

    from app.posts.routes import posts_bp
    from app.profiles.routes import profiles_bp
    from app.reports.routes import reports_bp

    app.register_blueprint(posts_bp)
    app.register_blueprint(profiles_bp)
    app.register_blueprint(reports_bp)


    return app
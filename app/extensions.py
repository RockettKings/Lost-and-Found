"""Shared extension objects used by every teammate's routes."""

import sqlite3

from flask_login import LoginManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect
from sqlalchemy import event
from sqlalchemy.engine import Engine

db = SQLAlchemy()
migrate = Migrate()
csrf = CSRFProtect()

login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "Please log in to continue."
login_manager.login_message_category = "info"
# Invalidates the session if the user's IP/browser fingerprint changes mid-session.
login_manager.session_protection = "strong"


@event.listens_for(Engine, "connect")
def enable_foreign_keys(connection, _record):
    # SQLite requires this on every connection to enforce user/item relationships.
    if isinstance(connection, sqlite3.Connection):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()

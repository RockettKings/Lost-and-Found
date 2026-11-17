"""Profile editing. Flask-WTF adds the CSRF token."""

from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField
from wtforms.validators import Length, Optional


def strip_text(value):
    return value.strip() if isinstance(value, str) else value


class ProfileForm(FlaskForm):
    display_name = StringField("Display name", filters=[strip_text],
                               validators=[Optional(), Length(max=80)])
    bio = TextAreaField("Bio (optional)", filters=[strip_text],
                        validators=[Optional(), Length(max=500)])

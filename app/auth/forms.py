"""Server-side validation for account forms. Flask-WTF also adds a CSRF token."""

from flask_wtf import FlaskForm
from wtforms import BooleanField, EmailField, PasswordField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError

# A short blocklist of the most common passwords. Extend as needed.
COMMON_PASSWORDS = {
    "password", "password1", "password123", "12345678", "123456789", "1234567890",
    "qwerty123", "qwertyuiop", "iloveyou", "letmein1", "welcome1", "abc12345",
    "11111111", "00000000", "baseball", "football", "sunshine", "princess",
}


def _strip(value):
    return value.strip() if isinstance(value, str) else value


class RegistrationForm(FlaskForm):
    email = EmailField("Email", filters=[_strip], validators=[
        DataRequired(), Length(max=254), Email(check_deliverability=False),
    ])
    # The 128 maximum stops someone from sending a huge string to slow down hashing.
    password = PasswordField("Password", validators=[
        DataRequired(),
        Length(min=10, max=128, message="Password must be 10–128 characters."),
    ])
    confirm = PasswordField("Confirm password", validators=[
        DataRequired(), EqualTo("password", message="Passwords must match."),
    ])

    def validate_password(self, field):
        if field.data.lower() in COMMON_PASSWORDS:
            raise ValidationError("That password is too common. Choose another.")
        if self.email.data and field.data.lower() == self.email.data.strip().lower():
            raise ValidationError("Password cannot be your email address.")


class LoginForm(FlaskForm):
    email = EmailField("Email", filters=[_strip], validators=[DataRequired(), Length(max=254)])
    password = PasswordField("Password", validators=[DataRequired(), Length(max=128)])
    remember = BooleanField("Keep me logged in")


class LogoutForm(FlaskForm):
    """Empty form: logout is a POST so it carries a CSRF token."""

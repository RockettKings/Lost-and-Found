"""Forms for creating and editing a lost or found post."""

from datetime import date

from flask_wtf import FlaskForm
from flask_wtf.file import FileField
from wtforms import DateField, SelectField, StringField, TextAreaField
from wtforms.fields.choices import SelectChoice
from wtforms.validators import DataRequired, Length


def _strip(value):
    return value.strip() if isinstance(value, str) else value


class ItemForm(FlaskForm):
    title = StringField("Title", filters=[_strip], validators=[
        DataRequired(), Length(max=120),
    ])
    description = TextAreaField("Description", filters=[_strip], validators=[
        DataRequired(), Length(max=2000),
    ])
    category = StringField("Category", filters=[_strip], validators=[
        DataRequired(), Length(max=80),
    ])
    listing_type = SelectField("Lost or found", choices=[
        SelectChoice("lost", "Lost"),
        SelectChoice("found", "Found"),
    ], validators=[DataRequired()])
    general_location = StringField("Location", filters=[_strip], validators=[
        DataRequired(), Length(max=200),
    ])
    date_reported = DateField("Date reported", default=date.today, validators=[DataRequired()])
    photo = FileField("Photo")


class PostActionForm(FlaskForm):
    """Empty form so delete and resolve carry a CSRF token."""

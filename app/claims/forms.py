"""Use the app's existing Flask-WTF validation and CSRF protection."""

from flask_wtf import FlaskForm
from flask import request
from wtforms import FieldList, HiddenField, StringField, TextAreaField
from wtforms.validators import AnyOf, DataRequired, Length, Optional, ValidationError


def strip_text(value):
    return value.strip() if isinstance(value, str) else value


class QuestionsForm(FlaskForm):
    questions = FieldList(StringField("Question", filters=[strip_text], validators=[
        Optional(), Length(max=200),
    ]), min_entries=3, max_entries=3)

    def validate_questions(self, field):
        if sum(key.startswith("questions-") for key in request.form) > 3:
            raise ValidationError("Use at most three ownership questions.")
        if not any(entry.data for entry in field):
            raise ValidationError("Enter at least one ownership question.")


class ClaimForm(FlaskForm):
    questions_version = HiddenField(validators=[DataRequired(), Length(max=64)])
    answers = FieldList(TextAreaField("Answer", filters=[strip_text], validators=[
        DataRequired(), Length(max=1000),
    ]), max_entries=3)
    supporting_details = TextAreaField("Additional details (optional)", filters=[strip_text],
                                      validators=[Optional(), Length(max=2000)])

    def validate_answers(self, field):
        submitted = sum(key.startswith("answers-") for key in request.form)
        if len(field) != self.expected_answers or submitted != self.expected_answers:
            raise ValidationError("Answer every ownership question.")


class ReviewForm(FlaskForm):
    # The two buttons submit this field; accept only the supported final decisions.
    decision = StringField("Decision", validators=[DataRequired(), AnyOf(["approved", "denied"])])

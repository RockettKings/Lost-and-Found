"""Terminal commands. Admin rights can only be changed here, not from the website."""

import click

from app.extensions import db
from app.models import User


def _set_admin(email, value):
    user = db.session.execute(
        db.select(User).filter_by(email=email.strip().lower())
    ).scalar_one_or_none()
    if user is None:
        raise click.ClickException(f"No account found for {email}.")
    user.is_admin = value
    db.session.commit()
    return user


def register_cli(app):
    @app.cli.command("make-admin")
    @click.argument("email")
    def make_admin(email):
        """Give an existing account admin rights."""
        _set_admin(email, True)
        click.echo(f"{email} is now an admin.")

    @app.cli.command("close-old-posts")
    def close_old_posts():
        """Mark open posts older than POST_AUTO_CLOSE_DAYS as resolved."""
        from app.posts.expiry import close_expired_posts
        closed = close_expired_posts()
        click.echo(f"Closed {closed} post(s) older than {app.config['POST_AUTO_CLOSE_DAYS']} days.")

    @app.cli.command("remove-admin")
    @click.argument("email")
    def remove_admin(email):
        """Take admin rights away from an account."""
        _set_admin(email, False)
        click.echo(f"{email} is no longer an admin.")

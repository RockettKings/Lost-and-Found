# FoundIt

FoundIt is a lost and found web app for EECS 581. Users post items they lost or found, search the posts, and claim items that belong to them. When someone posts a photo, the app guesses the item's category from it.

Built with Flask, SQLAlchemy, and Flask-Migrate. Photos are stored in Amazon S3.

## Team

Jaycob Campos, Khang Phan, Andrew Kruckemyer, Nick Heyer, Jonathan Kazmaier, Lydia Peng

## Setup

You need Python 3.12.

```bash
git clone https://github.com/RockettKings/Lost-and-Found.git
cd Lost-and-Found
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env
```

Fill in `.env`, then create the database:

```bash
flask --app run db upgrade
```

## Environment variables

Never commit `.env`.

| Variable | What it is |
|---|---|
| `APP_ENV` | `development` locally, `production` on the host |
| `SECRET_KEY` | Flask secret key. Make one with `python -c "import secrets; print(secrets.token_hex(32))"` |
| `DATABASE_URL` | Database URL. Leave it blank to use a local SQLite file |
| `S3_BUCKET` | Private S3 bucket for item photos |
| `AWS_DEFAULT_REGION` | AWS region, default `us-east-1` |
| `AWS_ACCESS_KEY_ID` | AWS key for a limited IAM user |
| `AWS_SECRET_ACCESS_KEY` | AWS secret for that user |
| `AWS_SESSION_TOKEN` | Only needed with temporary credentials |

## Run the app

```bash
flask --app run run --debug
```

Then open http://127.0.0.1:5000.

## Run the tests

```bash
pytest
```

The tests use their own database, so they don't touch your local data.

## Admin commands

Admin rights can only be given from the terminal, never from the website.

```bash
flask --app run make-admin you@example.com
flask --app run remove-admin you@example.com
flask --app run close-old-posts
```

## Hosting

The hosted site is at TBD. `render.yaml` holds the deploy settings.

## Project docs

Requirements, architecture, sprint plans, and the hour log are in the `documents` folder.

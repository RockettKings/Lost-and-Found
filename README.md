# FoundIt

A lost-and-found web app for a campus. People post an item they lost or found,
browse and search what others posted, and mark a post resolved once the item is
back with its owner. When a poster attaches a photo, an image model trained on
our own labeled dataset guesses the item's category and prefills the field.

EECS 581 Group 14. Flask with SQLAlchemy and SQLite, server-rendered Jinja pages
that fetch their data from a JSON API, and a fine-tuned ResNet18 for the category
guess. Python 3.12.

The design is in [documents/architecture.md](documents/architecture.md), the
schedule in [documents/sprint-plan.md](documents/sprint-plan.md), and what counts
as done for each Sprint 2 requirement in
[documents/sprint-2-requirements.md](documents/sprint-2-requirements.md).

## Team

Jaycob Campos, Khang Phan, Andrew Kruckemyer, Nick Heyer, Jonathan Kazmaier, Lydia Peng

## Setup

Everything below runs from the project directory.

**1. Create and activate a Python 3.12 virtual environment.**

```sh
# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
```

```powershell
# Windows PowerShell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
```

**2. Install the dependencies.** `requirements-dev.txt` pulls in
`requirements.txt` and adds pytest.

```sh
python -m pip install -r requirements-dev.txt
```

This installs torch and torchvision, which `app/model.py` needs to build the
network and preprocess photos. They are the largest dependencies by far; expect
a few hundred MB.

**3. Create your `.env`.**

```sh
cp .env.example .env            # Copy-Item .env.example .env on Windows
python -c "import secrets; print(secrets.token_hex(32))"
```

Put the generated value in `.env` as `SECRET_KEY`. Everything else in the file
can stay blank for local work: the database falls back to
`instance/lost_found.sqlite3`, the model falls back to the checkpoint in the
project root, and photo uploads only need AWS values once you are testing
against a real bucket.

**4. Check that the model weights are present.** `best_weights_resnet18_base.pt`
is committed at the project root, 44.8 MB, and a normal `git clone` brings it
down with everything else. Nothing is downloaded at runtime.

```sh
ls -l best_weights_resnet18_base.pt
```

If it is missing, the app still runs and posts still work - the category field
is simply never prefilled. See [The category guess](#the-category-guess) below.

**5. Create the database tables and start the server.**

```sh
python -m flask --app run db upgrade
python -m flask --app run run --debug
```

Visit <http://127.0.0.1:5000/healthz>. `{"status":"ok"}` means the database is
ready; 503 means it is unavailable or not migrated. Use `--debug` locally only.

## Environment variables

Read from `.env` by `create_app()`. [`.env.example`](.env.example) is the
template; never commit your own `.env`.

| Variable | Required | Default if blank | What it does |
| --- | --- | --- | --- |
| `APP_ENV` | no | `development` | `production` enforces a 32-character `SECRET_KEY`, an absolute SQLite path, and secure cookie flags |
| `SECRET_KEY` | yes | none | Signs sessions and CSRF tokens. Generate one per environment and never share it |
| `DATABASE_URL` | no | `sqlite:///lost_found.sqlite3` under `instance/` | SQLAlchemy database URL |
| `MODEL_WEIGHTS_PATH` | no | `best_weights_resnet18_base.pt` in the project root | The checkpoint `app/model.py` serves. Set it only to run a different one, such as a newer checkpoint kept outside the repository |
| `S3_BUCKET` | for photos | none | Private bucket holding item photos. Blank until the team connects cloud storage |
| `AWS_DEFAULT_REGION` | for photos | `us-east-1` | Region of that bucket |
| `AWS_ACCESS_KEY_ID` | for photos | none | Prefer an IAM role on AWS; otherwise a dedicated, limited IAM user |
| `AWS_SECRET_ACCESS_KEY` | for photos | none | Pairs with the key ID above |
| `AWS_SESSION_TOKEN` | no | none | Only needed with temporary credentials |

## Running the tests

```sh
python -m pytest              # 264 tests
python -m pytest -q tests/test_category_guess.py
```

Each database test builds a fresh migrated SQLite file under pytest's temp
directory, so the tests never touch `instance/`. AWS is always replaced with a
fake - no test uploads anything. Tests that need the real checkpoint skip
themselves when it is absent, so a teammate without it still gets a green run.

`tests/sample_photos/` holds 93 held-out photos, three per category, for the
Req 13 category tests. Its
[README](tests/sample_photos/README.md) covers where they came from and how to
use them.

## The category guess

`app/model.py` is the only machine-learning code inside `app/`. It exposes
`predict(image_bytes)`, which returns a `(category, confidence)` pair, and
`guess_for_form()`, which returns the category only when confidence reaches
`CONFIDENCE_THRESHOLD` (0.60). The post form calls
`POST /api/posts/category-guess` and prefills the field from the answer.

The guess is always a suggestion. The poster can change it, and the category
they submit is the one saved. A low-confidence guess, an unreadable photo, or a
missing weights file all leave the field blank rather than blocking the post.

The model code reports 81.1% accuracy on the held-out test split. The experiment
logs and model decision documents are not present in this checkout, so that
accuracy has not been independently verified here. The training pipeline is
`cnn.py` and `data_pipeline.py` at the project root, which read a labeled dataset
that is deliberately not in the repository.

## Project layout

| Path | What is there |
| --- | --- |
| `app/__init__.py` | App factory, configuration, error handlers, `/` and `/healthz` |
| `app/models.py` | Users, items, claims, messages, and notifications |
| `app/auth/` | Register, log in, log out |
| `app/posts/` | Posts JSON API under `/api/posts`, photo handling, category guess |
| `app/posts/pages.py`, `app/profiles/pages.py` | Post and profile HTML pages |
| `app/claims/`, `app/messages/`, `app/notifications/` | Private claims, messages, and notifications |
| `app/photo_pipeline/` | Validate an upload, strip EXIF and GPS, re-encode as JPEG |
| `app/storage.py` | S3 upload, presigned viewing URLs, delete |
| `app/model.py` | Category guess from a photo |
| `app/static/`, `app/templates/` | All styling, front-end behavior, and layout |
| `migrations/` | Alembic migration history |
| `tests/` | pytest suite and fixtures |
| `documents/` | Architecture, sprint plans, requirements, meeting logs, and hour log |
| `cnn.py`, `data_pipeline.py`, `ensemble.py` | Model training, the dataset split, and checkpoint ensembling |
| `render.yaml`, `deploy/` | Hosting blueprint and the S3 IAM policy |

## Admin commands

Admin rights are managed from the terminal:

```sh
python -m flask --app run make-admin you@example.com
python -m flask --app run remove-admin you@example.com
python -m flask --app run close-old-posts
```

## Hosting

The hosted site URL is TBD. `render.yaml` contains the deployment settings.

## Sprint checkpoint

The Sprint 2 checkpoint passes 264 automated tests. Some acceptance criteria
remain unfinished; see the checkpoint status in
[the Sprint 2 requirements](documents/sprint-2-requirements.md).
[Sprint 3 requirements](documents/sprint-3-requirements.md) and the latest
[hour log](documents/hour-log.md) are also preserved in `documents/`.

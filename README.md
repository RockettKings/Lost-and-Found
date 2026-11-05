# Lost and Found — Sprint 1 database / DevOps

This branch contains C's database and hosting foundation. B/D still own account and
post routes/security; E owns image processing; F owns application workflow tests.

| Sprint 1 responsibility | Implementation |
| --- | --- |
| Save accounts and posts (#2) | SQLite, `User` and `Item` models, migrations |
| Host online (#4) | `render.yaml`: Gunicorn, HTTPS hosting, persistent database disk |
| Store/display cloud photos (#31) | `app/storage.py` and private S3 setup below |
| Supporting configuration/relationships (#23 / part of #38) | Environment variables and `Item.user_id` foreign key |

**This is a foundation, not a completed live app.** Hosting needs a team account;
photo storage needs a bucket and E/B's integration. Existing post/profile/report
routes are unchanged placeholders. No claims, messages, notifications, resolved-item
workflow, or admin features are implemented. Coordinate later tables for #38 with
the developers implementing those features. Full claim features are not Sprint 1.

## The files you need to understand

- `app/models.py`: account and item tables.
- `app/extensions.py`: shared database connection and SQLite foreign-key enforcement.
- `app/__init__.py`: connects Flask, configuration, database, and existing routes.
- `app/storage.py`: saves processed photos and generates viewing URLs.
- `migrations/`: database history; generated files, not a separate application.
- `render.yaml`: online hosting settings; `deploy/s3-policy.example.json`: storage permissions.
- `tests/`: a small set of database/storage checks using temporary files and mocked AWS.

Dependencies, `.env.example`, `.python-version`, and `.gitignore` support setup.

## Run locally

From the project directory, create and activate a Python 3.12 virtual environment:

```sh
# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
cp .env.example .env
```

```powershell
# Windows PowerShell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
Copy-Item .env.example .env
```

Then, on either platform:

```sh
python -m pip install -r requirements-dev.txt
python -c "import secrets; print(secrets.token_hex(32))"
```

Put the generated value in `.env` as `SECRET_KEY`. Leave `DATABASE_URL` blank to
use `instance/lost_found.sqlite3`; AWS values can stay blank until integrating photos.

```sh
python -m flask --app run db upgrade
python -m flask --app run run --debug
```

Visit <http://127.0.0.1:5000/healthz>: `{"status":"ok"}` means the database is ready.
It returns 503 if the database is unavailable or not migrated. The home page and
business routes still need B's work. Use `--debug` only locally.

View the database from the terminal:

```sh
sqlite3 -readonly instance/lost_found.sqlite3 '.dump'
```

Run the isolated checks with `python -m pytest -q`. They never edit the real database
or contact AWS. They do not test the team's not-yet-implemented account/post routes.

## Tables and team handoff

`users`: `id`, unique normalized `email`, `password_hash`, `created_at`.
`items`: `id`, `user_id`, `title`, `description`, `category`, `listing_type`,
`general_location`, `date_reported`, `created_at`, optional `photo_key`.

One user can have many items. `Item.user_id` references `User.id`. This preserves
posts across restarts and connects them to their poster. User deletion is restricted
while posts reference the account. Timestamps are UTC; `listing_type` is `lost` or
`found`. `photo_key` is needed to retrieve the photo from cloud storage.

B imports `db` from `app.extensions` and `User` / `Item` from `app.models`, then uses
`db.session.add(record)` and `db.session.commit()` in their validated routes. D's
account code must hash passwords with Werkzeug before setting `password_hash`,
validate inputs, and derive ownership from the authenticated user. Routes must
explicitly select permitted fields and exclude password hashes/private information.
Database constraints do not replace authorization or request validation.

For later model changes: run `python -m flask --app run db migrate -m "Description"`,
review the generated migration, then `python -m flask --app run db upgrade`. Commit
the model and migration together. Teammates only run `db upgrade` after pulling.
Do not rerun `db init` or edit a migration already shared with teammates.

## Host online (#4)

1. Push the reviewed code through the team's normal process. In Render, create a
   Blueprint from the repository and choose the intended branch.
2. Review `render.yaml` before applying it: **this uses paid compute and a disk**.
   It generates the secret and uses `/var/data/lost_found.sqlite3` on persistent storage.
3. Deploy, then visit the service's HTTPS `/healthz` URL. The start command applies
   migrations before Gunicorn. Automatic Git-triggered deploys are disabled.
4. Once B/D integrate the app, create an account/post, redeploy, and confirm both
   survive. A healthy database alone does not complete the browser app requirement.

Render's ordinary filesystem is temporary; its [persistent disk](https://render.com/docs/disks)
requires paid compute. This configuration uses one service instance and has brief
downtime during deploys. Production disables configured debug mode and requires a
secret of at least 32 characters plus an absolute SQLite path. Never run the Flask
development server in production. See [Render's Flask guide](https://render.com/docs/deploy-flask).

Before schema changes, use SQLite's `.backup` command to a new protected filename
and keep a copy off the host. Database files, backups, and `.env` must stay out of Git.

## Connect cloud photos (#31)

1. Create a private S3 bucket in the team's AWS account. Keep **Block all public
   access** and default encryption enabled; use **Bucket owner enforced** ownership.
2. Replace the bucket placeholder in `deploy/s3-policy.example.json` and attach that
   policy to a dedicated app IAM identity. It only permits access to `items/*`.
3. Set `S3_BUCKET`, `AWS_DEFAULT_REGION`, and the app identity's AWS credentials in
   local `.env` / Render's secret environment settings. Never use root account keys.
   An AWS-hosted app can use an IAM role instead. Storage and requests may cost money.
4. E/B connect the existing photo pipeline to the helper inside their authenticated
   posting route, after validating the request:

```python
from app.storage import save_photo, photo_url, delete_photo

clean_jpeg = process_photo(uploaded_file)  # E validates, strips GPS, and encodes JPEG
key = save_photo(clean_jpeg)              # assign key to Item.photo_key, then commit
url = photo_url(key)                      # include URL when displaying that item
```

Helpers need a Flask app/request context. S3 uses random filenames; the private
viewing URL expires after 15 minutes. Store the key, not the URL. If the database
commit fails after upload, roll back and use `delete_photo(key)` to remove the
unused photo. Routes must handle AWS failures with safe errors and never accept
client-supplied keys for deletion. These helpers do not implement upload routes or
replace E's image validation. See [AWS's presigned URL guide](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/s3-presigned-urls.html).

Finally, test an actual upload/display and a redeploy in the configured team account.
The local tests mock S3; no real hosting or storage has been provisioned here.

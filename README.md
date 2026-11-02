# Lost-and-Found
## Running tests

Create and activate a virtual environment:
```sh
python3 -m venv .venv
source .venv/bin/activate
```

Install dependencies and run:

```sh
python -m pip install -r requirements-dev.txt
python -m pytest
```

Current status: 1 passed, 9 skipped. App/client fixtures and a smoke
test are implemented. Database isolation, registration, login, and
logout tests are skeletons pending the database and account implementation.
Req 40 is not yet complete.

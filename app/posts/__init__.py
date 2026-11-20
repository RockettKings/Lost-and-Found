# Req 5f (Jaycob): importing guess registers POST /api/posts/category-guess on
# posts_bp. This file was empty, so nothing here was displaced. Python executes
# app/posts/routes.py on demand from this import, so posts_bp exists by the time
# guess.py asks for it, and routes.py is already in sys.modules when
# app/__init__.py imports it a moment later.
from app.posts import guess  # noqa: F401

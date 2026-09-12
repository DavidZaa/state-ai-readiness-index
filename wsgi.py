"""WSGI entrypoint.

Vercel's Python runtime looks for an `app` object in one of a small set of
root filenames — app.py, index.py, server.py, main.py, wsgi.py, asgi.py. The
package here is already called `app`, which makes `app.py` ambiguous, so this
is `wsgi.py`: the conventional name, and the one least likely to collide.

It only re-exports the application built in app/server.py. Gunicorn can use the
same object, so Render and Vercel run identical code.
"""

from app.server import app

__all__ = ["app"]

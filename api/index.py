"""Vercel entry point.

Vercel's Python runtime looks for a WSGI or ASGI callable named `app` inside
api/, and routes every request to it via the rewrite in vercel.json. Flask's
application object is already a WSGI callable, so this only has to hand the
existing one over — there is no second copy of the app.

The root is resolved from this file rather than the working directory, because
a serverless invocation does not run from the project root and the committed
data files are found relative to the repository.
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.server import create_app  # noqa: E402

app = create_app(ROOT)

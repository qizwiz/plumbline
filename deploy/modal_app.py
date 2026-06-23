"""
Modal deployment of the plumbline /verification demo.

Serves deploy/app.py (a self-contained Flask app over PRECOMPUTED audit runs — no LLM,
no halmos, no keys at request time) as a public web endpoint.

    modal deploy deploy/modal_app.py      # → public https://<...>.modal.run URL

Scales to zero ($0 when idle); cold start is a few seconds for this tiny image.
"""
import modal
from pathlib import Path

HERE = Path(__file__).parent

# mount app.py + audit-runs/ at runtime (NOT copy=True — a runtime mount is re-uploaded each
# deploy, so edits to app.py always ship; a baked copy layer gets cached and goes stale)
image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install("flask>=3.0")
    .add_local_dir(HERE.as_posix(), remote_path="/app")
)

app = modal.App("plumbline-verification")


@app.function(image=image)
@modal.wsgi_app()
def web():
    import sys
    sys.path.insert(0, "/app")
    from app import app as flask_app   # the Flask instance in deploy/app.py
    return flask_app

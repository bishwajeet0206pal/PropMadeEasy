import sys
import os

# Ensure the repository root is in sys.path so agents, core, config, and connectors can be imported
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

# Import the FastAPI application instance
from api.server import app

# Vercel's Python runtime looks for `app` in `api/index.py`

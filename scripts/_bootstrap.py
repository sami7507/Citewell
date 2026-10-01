"""Make the backend package importable when a script is run directly."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = str(ROOT / "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

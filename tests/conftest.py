import sys
from pathlib import Path

import pytest

# Add server source to path so `from config import settings` works
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "observal-server"))

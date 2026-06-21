import os
import sys

# Ensure the worker package root is importable when running pytest.
sys.path.insert(0, os.path.dirname(__file__))

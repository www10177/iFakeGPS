import os
import sys

# Ensure the project root (parent of scripts/) is on the python path so `src` imports work
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from src.main import main

if __name__ == "__main__":
    main()

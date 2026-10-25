"""Root passthrough for main.py."""
import os
import runpy
import sys

base_dir = os.path.dirname(os.path.abspath(__file__))
suite_dir = os.path.join(base_dir, "deadlock-suite")
if suite_dir not in sys.path:
    sys.path.insert(0, suite_dir)

target_script = os.path.join(suite_dir, "main.py")

if __name__ == "__main__":
    runpy.run_path(target_script, run_name="__main__")

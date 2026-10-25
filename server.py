"""Root passthrough for server.py."""
import importlib.util
import os
import sys

base_dir = os.path.dirname(os.path.abspath(__file__))
suite_dir = os.path.join(base_dir, "deadlock-suite")
if suite_dir not in sys.path:
    sys.path.insert(0, suite_dir)

# Load the actual server app from deadlock-suite/server.py
suite_server_file = os.path.join(suite_dir, "server.py")
spec = importlib.util.spec_from_file_location("deadlock_suite_server", suite_server_file)
suite_server_mod = importlib.util.module_from_spec(spec)
sys.modules["deadlock_suite_server"] = suite_server_mod
spec.loader.exec_module(suite_server_mod)

app = suite_server_mod.app

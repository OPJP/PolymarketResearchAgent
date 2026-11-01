import sys, os
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
TOOLS = os.path.join(ROOT, 'research', 'reverse_engineering', 'tools')
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)
CACHE = os.path.join(ROOT, '.cache', 're', 'dbdd-inplay-taker')
os.makedirs(CACHE, exist_ok=True)

"""Run this before the workshop:  python check_setup.py"""
import sys
import time

print(f"Python {sys.version.split()[0]}")
if sys.version_info < (3, 11):
    sys.exit("✘ PedNStream needs Python 3.11 or newer.")

missing = []
for mod in ["pednstream", "yaml", "pandas", "matplotlib", "ipywidgets"]:
    try:
        __import__(mod)
    except ImportError:
        missing.append(mod)
if missing:
    sys.exit(f"✘ Missing packages: {', '.join(missing)}  ->  pip install -r requirements.txt")

import matplotlib
matplotlib.use("Agg")
from workshop_tools import run

t0 = time.time()
k = run().kpis()
print(f"✔ Simulation ran in {time.time() - t0:.2f}s; "
      f"{k['reached Platform X'] + k['reached City Exit Y']} people reached a destination.")
print("✔ All good. See you at the workshop!")

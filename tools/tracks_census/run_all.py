"""Run the track census pipeline (scripts/01..60) in order. Outputs land in this folder."""
import glob
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
for script in sorted(glob.glob(os.path.join(HERE, "scripts", "[0-9][0-9]_*.py"))):
    print("==", os.path.basename(script), flush=True)
    subprocess.run([sys.executable, script], cwd=os.path.join(HERE, "scripts"), check=True)

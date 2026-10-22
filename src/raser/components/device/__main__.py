import subprocess
import sys
from pathlib import Path

device = sys.argv[1]
command = Path(__file__).with_name(device + ".py")
subprocess.run([sys.executable, str(command)], check=True)

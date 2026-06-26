import subprocess
import sys
from pathlib import Path

device = sys.argv[1]
command = Path(__file__).with_name(device + ".py")
subprocess.run(["python3 " + str(command)], shell=True, executable='/bin/bash')

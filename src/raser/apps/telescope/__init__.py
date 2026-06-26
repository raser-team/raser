import sys
import os
import time
import subprocess

import ROOT
ROOT.gROOT.SetBatch(True)

def main(kwargs):
    label = kwargs['label']
    if label == "-h":
        print("taichu_v1:   ","first version of telescope simulation")
        print("taichu_v2:   ","second version of telescope simulation")
    elif label.startswith("taichu_v1"):
        from . import telescope_signal as tlcp
        tlcp.main()  
    elif label.startswith("taichu_v2"):
        from . import telescope_signal as tlcp
        tlcp.taichu_v2(label)
    elif label.startswith("acts_v1"):
        from . import telescope_acts as tlcp_acts
        tlcp_acts.main()
    elif label.startswith("g4"):
        from . import telescope_g4
        telescope_g4.main()
    else:
        raise NameError(label)
    

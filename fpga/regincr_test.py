#=========================================================================
# RegIncr_test
#=========================================================================

import pymtl3 as mtl
from pymtl3.stdlib.test_utils import config_model_with_cmdline_opts

from .regincr import RegIncr

# In pytest, unit tests are simply functions that begin with a "test_"
# prefix. PyMTL3 is setup to collect command line options. Simply specify
# "cmdline_opts" as an argument to your unit test source code,
# and then you can dump VCD by adding --dump-vcd option to pytest
# invocation from the command line.

def test_basic(cmdline_opts):

    # Create the model

    model = RegIncr()

    # Config the model

    model = config_model_with_cmdline_opts(model,cmdline_opts,duts=[])

    # Create and reset simulator

    model.apply(mtl.DefaultPassGroup(linetrace=True))
    model.sim_reset()

    # Helper function

    def t(in_,out):

        # Write input value to input port

        model.in_ @= in_

        # Ensure that all combinational concurrent blocks are calles

        model.sim_eval_combinational()

        # If reference output is not '?', verify value read from output port

        if out != '?':
            assert model.out == out
        
        # Tick simulator one cycle

        model.sim_tick()

    t(0x00,'?')
    t(0x13,0x01)
    t(0x27,0x14)
    t(0x00,0x28)
    t(0x00,0x01)
    t(0x00,0x01)

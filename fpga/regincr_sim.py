#!/usr/bin/env python
#=========================================================================
# regincr-sim <input-values>
#=========================================================================

import pymtl3 as mtl
import os
from .regincr import RegIncr

def main():

    # Get list of input values from command line

    input_values = [0x01,0x13,0x25,0x37]

    # Add three zero values to end of list of input values

    input_values.extend([0]*3)
    print(input_values)

    # Instantiate and elaborate the model

    model = RegIncr()
    model.elaborate()

    # Applying the default pass group to add simulation facilities

    if not os.access('output/fpga', os.F_OK):
        os.makedirs('output/fpga', exist_ok=True) 
    model.apply( mtl.DefaultPassGroup(textwave=True, linetrace=True,vcdwave='output/fpga/regincr_sim') )
    print('vcd file has been saved in output/fpga/regincr_sim')

    # Reset simulator

    model.sim_reset()

    # Apply input values and display output values

    for input_value in input_values:

        # Write input value to input port

        model.in_ @= input_value
        model.sim_eval_combinational()

        # Display input and output ports

        print(f" cycle = {model.sim_cycle_count()}: in = {model.in_}, out = {model.out}")

        # Tick simulator one cycle

        model.sim_tick()
    model.print_textwave()
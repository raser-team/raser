#=========================================================================
# RegIncr2stage
#=========================================================================
# Two-stage registered incrementer that uses structural composition to
# instantiate and connect two instances of the single-stage registered
# incrementer.

import pymtl3 as mtl
from .regincr import RegIncr

class RegIncr2stage( mtl.Component ):
# Constructor
  def construct( s ):
    # Port-based interface
    s.in_ = mtl.InPort (8)
    s.out = mtl.OutPort(8)
    # First stage
    s.reg_incr_0 = RegIncr()
    mtl.connect( s.in_, s.reg_incr_0.in_ )
    # Second stage
    s.reg_incr_1 = RegIncr()
    s.reg_incr_0.out //= s.reg_incr_1.in_
    s.reg_incr_1.out //= s.out
    # Line Tracing
  def line_trace( s ):
    return "{} ({}|{}) {}".format(
      s.in_,
      s.reg_incr_0.line_trace(),
      s.reg_incr_1.line_trace(),
      s.out
    )

def create_path(path):
  import os
  """ If the path does not exit, create the path"""
  if not os.access(path, os.F_OK):
    os.makedirs(path, exist_ok=True) 
  
def main():
  input_values = [ 0x01, 0x13, 0x25, 0x37, 0xff ]
  # Add three zero values to end of list of input values
  input_values.extend( [0]*3 )
  print(input_values)
  # Instantiate and elaborate the model 
  model = RegIncr2stage()
  model.elaborate()
  create_path("output/asic/")
  model.apply( mtl.DefaultPassGroup(textwave=True, linetrace=True, vcdwave='output/asic/regincr2stage-sim') )
  # Reset simulator
  model.sim_reset()
  # Apply input values and display output values
  for input_value in input_values:
    # Write input value to input port 
    model.in_ @= input_value 
    model.sim_eval_combinational() 
    # Display input and output ports
    print( f" cycle = {model.sim_cycle_count()}: in = {model.in_}, out = {model.out}" ) 
    # Tick simulator one cycle 
    model.sim_tick()
  model.print_textwave()
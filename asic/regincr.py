#=========================================================================
# regincr-sim <input-values>
#=========================================================================

import pymtl3 as mtl

class RegIncr( mtl.Component ):
  def construct( s ):
    # Port-based interface
    s.in_ = mtl.InPort ( mtl.Bits8 )
    s.out = mtl.OutPort( mtl.Bits8 )

    # Sequential logic
    s.reg_out = mtl.Wire( 8 ) #

    @mtl.update_ff
    def block1():
      if s.reset:
        s.reg_out <<= 0
      else:
        s.reg_out <<= s.in_
    
    @mtl.update
    def block2():
      s.out @= s.reg_out + 1

  def line_trace( s ):
    return f"{s.in_} ({s.reg_out}) {s.out}"

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
  model = RegIncr()
  model.elaborate()
  create_path("output/asic/")
  model.apply( mtl.DefaultPassGroup(textwave=True, linetrace=True, vcdwave='output/asic/regincr-sim') )
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

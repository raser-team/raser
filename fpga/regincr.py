#=========================================================================
# RegIncr
#=========================================================================
# This is a simple model for a registered incrementer. An eight-bit value
# is read from the input port, registered, incremented by one, and
# finally written to the output port.

import pymtl3 as mtl

class RegIncr(mtl.Component):
    def construct(s):
        # Port-based interface
        s.in_ = mtl.InPort (mtl.Bits8)
        s.out = mtl.OutPort(mtl.Bits8)

        # update_ff block modeling register

        s.reg_out = mtl.Wire(8)

        @mtl.update_ff
        def block1():
            if s.reset:
                s.reg_out <<= 0
            else:
                s.reg_out <<= s.in_

        # update block modeling incrementer

        @mtl.update
        def block2():
            s.out @= s.reg_out + 1

    def line_trace(s):
        return "{}({}){}".format(s.in_,s.reg_out,s.out)

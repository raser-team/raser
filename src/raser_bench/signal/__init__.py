"""
Description:  signal/__init__.py
@Date       : 2025
@Author     : Xin Shi, Chenxi Fu, Jian Feng
@version    : 2.0
"""

from raser.stages import chain


class Signal(chain.Chain):
    name = "signal"
    help = "single signal simulation"
    components = ("raser_bench/signal",)


WORKFLOW = Signal.workflow()

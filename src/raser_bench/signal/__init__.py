"""
Description:  signal/__init__.py
@Date       : 2025
@Author     : Xin Shi, Chenxi Fu, Jian Feng
@version    : 2.0
"""

from raser.lifecycle.workflow import Workflow
from raser.stages import chain


WORKFLOW = Workflow(
    name="signal",
    keys=chain.KEYS,
    defaults=chain.DEFAULTS,
    components=chain.COMPONENTS,
    readers=chain.READERS,
    in_file=chain.IN_FILE,
    slices=chain.SLICES,
    exclusive=chain.EXCLUSIVE,
    command=chain.job_command,
    analysis=chain.analyse,
)


def register(subparsers):
    parser = subparsers.add_parser("signal", help="single signal simulation")
    chain.add_arguments(parser)
    WORKFLOW.attach(parser)
    parser.set_defaults(_project="det_name", _components=("raser_bench/signal",))

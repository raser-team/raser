"""Beam monitor: the pulses that the bunches of a beam leave in one detector.

An event is one bunch: a source whose "particles" are fired together in
every event. The slices are those of the signal app; the default source is
the bunch in components/source of this app.
"""

from raser.stages import chain


class Bmos(chain.Chain):
    name = "bmos"
    help = "Beam Monitor Online System"
    components = ("raser_app/bmos",)
    defaults = {"deposit.source": "bunch", "deposit.plots": 0, "current.plots": 0, "digitizer.plots": 0}


WORKFLOW = Bmos.workflow()

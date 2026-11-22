"""The one place where the random generators of a job are seeded."""

from __future__ import annotations

import hashlib
import random

import ROOT

_job_seed: int | None = None
_streams: dict[str, ROOT.TRandom3] = {}


def seed_generators(seed: int) -> None:
    """Seed Python's and ROOT's generators and start every stream anew."""
    global _job_seed
    _job_seed = int(seed)
    random.seed(_job_seed)
    ROOT.gRandom.SetSeed(_job_seed)
    _streams.clear()


def stream(name: str) -> ROOT.TRandom3:
    """The generator of `name`; its seed is a hash of the job seed and the name.

    Successive draws form one sequence fixed by the job seed.  Before
    `seed_generators` is called the stream is seeded by ROOT at random.
    """
    if name not in _streams:
        seed = 0
        if _job_seed is not None:
            digest = hashlib.sha256(f"{_job_seed}/{name}".encode()).digest()
            seed = 1 + int.from_bytes(digest[:8], "big") % (2**31 - 1)
        _streams[name] = ROOT.TRandom3(seed)
    return _streams[name]

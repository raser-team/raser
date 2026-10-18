"""Explicit UMFPACK configuration for memory-limited 3D field solves."""

from __future__ import annotations

from typing import Any, Callable

import math

import devsim


def memory_bounded_umfpack_callback() -> Callable[..., dict[str, Any]]:
    # This backend is optional on MKL platforms; importing umfshim selects it.
    from devsim.umfpack import umfpack_loader
    from devsim.umfpack.umfshim import local_solver_callback

    def callback(**arguments):
        if arguments["action"] == "factor":
            solver = arguments["solver_object"]
            # The previous factor has already served its solve. The upstream
            # assignment otherwise keeps it alive until its replacement exists.
            solver.numeric = None
            if not arguments["is_same_symbolic"]:
                solver.symbolic = None
            if solver.umf_control is None:
                kind = "complex" if arguments["is_complex"] else "real"
                solver.umf_control = umfpack_loader.umf_control(solver.gdata, kind)
                # Symmetric graph ordering also applies to nonsymmetric PDE
                # Jacobians; UMFPACK still performs its numerical pivot checks.
                solver.umf_control.Control[umfpack_loader.UMFPACK_STRATEGY] = 3
                # UMFPACK 5.1 controls: ALLOC_INIT=6, SYM_PIVOT_TOLERANCE=15,
                # FRONT_ALLOC_INIT=17. Start with smaller workspaces; the library
                # grows them when needed. Diagonal preference controls fill only;
                # every solution must still pass its native backward-error test.
                solver.umf_control.Control[6] = 0.1
                solver.umf_control.Control[17] = 0.1
                solver.umf_control.Control[15] = 0.0
        result = local_solver_callback(**arguments)
        if arguments["action"] == "solve":
            # OMEGA1 and OMEGA2 are UMFPACK's sparse backward-error estimates.
            control = arguments["solver_object"].umf_control
            errors = [float(control.Info[index]) for index in (82, 83)]
            if (
                not all(math.isfinite(value) and value >= 0 for value in errors)
                or sum(errors) > 1e-8
            ):
                raise RuntimeError(f"UMFPACK backward-error check failed: {errors}")
        return result

    return callback


def configure_linear_solver(backend: str | None) -> None:
    if backend is None:
        return
    if backend != "umfpack_memory_bounded":
        raise ValueError(f"Unsupported linear solver: {backend}")
    callback = memory_bounded_umfpack_callback()
    devsim.set_parameter(name="direct_solver", value="custom")
    devsim.set_parameter(name="solver_callback", value=callback)
    print(
        "UMFPACK: symmetric graph ordering; release old factors before replacement",
        flush=True,
    )

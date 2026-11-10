"""PedNStream OD-weights workshop.

    from pednstream_workshop import run, compare
    res = run(od={"0_5": 3, "0_6": 1, "1_5": 1, "1_6": 1})
    res.dashboard()
"""

from .tools import (
    CORRIDORS,
    DEFAULT_NETWORK,
    NODE_NAMES,
    Result,
    compare,
    compare_maps,
    playground,
    ramp,
    run,
    switch,
)

__version__ = "1.0.0"

__all__ = [
    "CORRIDORS",
    "DEFAULT_NETWORK",
    "NODE_NAMES",
    "Result",
    "compare",
    "compare_maps",
    "playground",
    "ramp",
    "run",
    "switch",
]

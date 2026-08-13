# Copyright © 2017-2026 Elizabeth Ashford.
# This file is part of the taillight project. See LICENSE in the root
# directory for licensing information.


"""The top level module contains a few constants needed throughout taillight,
the base exception for all taillight errors (for easier catching by handlers),
and aliases for two important classes: :py:class:`~taillight.signal.Signal`,
and :py:class:`~taillight.slot.Slot`."""

from __future__ import annotations

# pylint: disable=cyclic-import, wrong-import-position,invalid-name


__all__ = ["ANY", "Signal", "Slot", "TaillightException", "signal", "slot"]


class TaillightException(Exception):
    """The base class for all taillight exceptions."""


class _AnyObject:
    __slots__ = []

    def __eq__(self, _: object) -> bool:
        return True

    def __ne__(self, _: object) -> bool:
        return False

    def __hash__(self) -> int:
        # Supposed to be a singleton, so this is fine.
        return id(ANY)

    def __repr__(self) -> str:
        return "<ANY>"


ANY: _AnyObject = _AnyObject()
"""The predicate for signalling any slot."""


# Important aliases
from taillight.signal import Signal
from taillight.slot import Slot

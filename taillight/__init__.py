# Copyright © 2015 Elizabeth Myers. All rights reserved.
# This file is part of the taillight project. See LICENSE in the root
# directory for licensing information.


"""Several constants are defined here."""


__all__ = ["signal", "slot"]


class TaillightException(Exception):
    """The base class for all taillight exceptions."""


class _AnyObject:
    __slots__ = []

    def __eq__(self, _):
        return True

    def __ne__(self, _):
        return False

    def __hash__(self):
        # Supposed to be a singleton, so this is fine.
        return id(ANY)


ANY = _AnyObject()
"""The predicate for signalling any slot"""


# Important aliases
from taillight.signal import Signal
from taillight.slot import Slot

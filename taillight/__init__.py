# Copyright © 2015 Elizabeth Myers. All rights reserved.
# This file is part of the taillight project. See LICENSE in the root
# directory for licensing information.


__all__ = ["signal", "slot"]


class TaillightException(Exception):
    """The base class for all taillight exceptions."""


# Important aliases
from taillight.signal import Signal
from taillight.slot import Slot


class _AnyObject:
    __slots__ = []

    def __eq__(self, _):
        return True

    def __ne__(self, _):
        return False


ANY = _AnyObject()
"""The predicate for signalling any slot"""

# Copyright © 2015 Elizabeth Myers. All rights reserved.
# This file is part of the taillight project. See LICENSE in the root
# directory for licensing information.


# Important aliases
from taillight.signal import Signal
from taillight.slot import Slot


__all__ = ["signal", "slot"]


class TaillightException(Exception):
    """The base class for all taillight exceptions."""

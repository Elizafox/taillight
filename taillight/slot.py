# Copyright © 2015 Elizabeth Myers. All rights reserved.
# This file is part of the taillight project. See LICENSE in the root
# directory for licensing information.

from collections import namedtuple

from taillight import TaillightException


class SlotError(TaillightException):
    """The base class for all slot errors."""


class SlotNotFoundError(SlotError):
    """Raised when a given slot is not found."""


Slot = namedtuple("Slot", "priority uid function")
"""The slot object used by the library.

:ivar priority:
    Priority of the slot.

:ivar uid:
    UID of the slot. Assigned by
    :py:class::`~taillight.signal.Signal.add_priority`.

:ivar function:
    Function called when the signal is run.
"""

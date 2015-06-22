# Copyright © 2015 Elizabeth Myers. All rights reserved.
# This file is part of the taillight project. See LICENSE in the root
# directory for licensing information.

from functools import update_wrapper

from taillight import TaillightException


class SlotError(TaillightException):
    """The base class for all slot errors."""


class SlotNotFoundError(SlotError):
    """Raised when a given slot is not found."""


class Slot:
    """A slot in a given signal. This is also callable."""

    def __init__(self, priority, uid, function):
        """Initalise the Slot object

        :param priority:
            Priority of the slot.

        :param uid:
            UID of the slot. Assigned by
            :py:meth::`~taillight.signal.Signal.add_priority`.

        :param function:
            Function called when the signal is run.
        """

        self.priority = priority
        self.uid = uid
        self.function = function

        update_wrapper(self, function)

    def __call__(self, caller, *args, **kwargs):
        return self.function(caller, *args, **kwargs)

    def __repr__(self):
        return "Slot(priority={}, uid={}, function={})".format(
            self.priority, self.uid, self.function)

    def __lt__(self, other):
        return (self.priority, self.uid) < (other.priority, other.uid)

    def __le__(self, other):
        return (self.priority, self.uid) <= (other.priority, other.uid)

    def __gt__(self, other):
        return (self.priority, self.uid) > (other.priority, other.uid)

    def __ge__(self, other):
        return (self.priority, self.uid) >= (other.priority, other.uid)

    def __eq__(self, other):
        return (self.priority, self.uid) == (other.priority, other.uid)

    def __ne__(self, other):
        return (self.priority, self.uid) != (other.priority, other.uid)


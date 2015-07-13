# -*- coding: utf-8 -*-
# Copyright © 2015 Elizabeth Myers. All rights reserved.
# This file is part of the taillight project. See LICENSE in the root
# directory for licensing information.

"""This module contains the Slot class and slot-related exceptions."""


from functools import update_wrapper

from taillight import TaillightException


class SlotError(TaillightException):
    """The base class for all slot errors."""


class SlotNotFoundError(SlotError):
    """Raised when a given slot is not found."""


class Slot:
    """A slot in a given signal.

    This is also callable, for purposes of enabling decorator usage.

    You probably do not want to instantiate this yourself. You should use
    :py:meth:`~taillight.signal.Signal.add`.

    """

    def __init__(self, signal, priority, uid, function, listener):
        """Initalise the Slot object.

        :param signal:
            A backreference to our :py:class:`~taillight.signal.Signal`.

        :param priority:
            Priority of the slot.

        :param uid:
            UID of the slot. Assigned by
            :py:meth:`~taillight.signal.Signal.add`.

        :param function:
            Function called when the signal is run.

        :param listener:
            The listener this object listens on.

        """
        self.signal = signal
        self.priority = priority
        self.uid = uid
        self.function = function
        self.listener = listener

        update_wrapper(self, function)

    def __call__(self, caller, *args, **kwargs):
        return self.function(caller, *args, **kwargs)

    def __hash__(self):
        h = hash((self.priority, self.uid, self.function, self.listener))

    def __repr__(self):
        return "Slot(priority={}, uid={}, function={}, listener={})".format(
            self.priority, self.uid, self.function, self.listener)

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

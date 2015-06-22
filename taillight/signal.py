# Copyright © 2015 Elizabeth Myers. All rights reserved.
# This file is part of the taillight project. See LICENSE in the root
# directory for licensing information.

from bisect import insort_left, insort_right
from collections.abc import Iterable
from threading import Lock, RLock

from taillight import ANY, TaillightException
from taillight.slot import Slot, SlotNotFoundError


class SignalException(TaillightException):
    """The base for all signal exceptions."""


class SignalStop(SignalException):
    """The exception raised when a signal needs to be stopped."""


class SignalDefer(SignalException):
    """The exception raised when a signal needs to be deferred. The next call
    will resume where it left off."""


class SignalError(SignalException):
    """The base exception for signal errors."""


class SignalDeferralSetError(SignalException):
    """Raised if an operation cannot complete because a deferral point is
    set."""


class Signal:
    """A signal is an object that keeps a list of functions for calling later.

    These functions are referred to as slots. Each slot in taillight has
    several attributes: a priority, a UID (a monotonically increasing number
    based on the number of slot objects that have existed), a function, and
    arguments to call the function with.

    This is conceptually similar to the concept of signals and slots, but with
    greater emphasis on priorities and having a well-defined order that the
    slots are called with. In addition, execution of slots may be stopped by
    raising :py:class::`~taillight.signal.SignalStop`, and deferred by raising
    :py:class::`~taillight.signal.SignalDefer`, where the signal will resume
    calling where it left off.

    When the signal is in a deferred state, adding or deleting slots is not
    allowed, as this would lead to inconsistencies in how the new slots should
    be called and how the deleted slots should be handled. However, a simple
    call to :py:meth::`~taillight.signal.Signal.reset_defer` resets the
    signal.

    By default, the slots are ordered by lowest priority first (0, 1, 2...).
    This is in line with the Unix style of priorities, and is rather intuitive
    from the programming perspective. When ``prio_descend`` is set to
    ``False``, higher priority slots are run first.

    When two slots have the same priority, their UID (computed at the time the
    slot is created) is used. The ordering follows the behaviour as described
    above with priorities.

    No two slots within a Signal instance can share the same UID. Forcing two
    slots to share a UID will result in undefined behaviour.

    Slots should not be transferred to other signals; instead, create another
    slot separately.

    This class is thread-safe and all operations may be performed by multiple
    threads at once.

    By default, when a function associated with a slot becomes garbage
    collected, it will be removed from the slots. The functions are kept
    as weak references.
    """

    # lol
    __slots__ = ["name", "_slots_lock", "_uid", "_uid_lock", "_defer",
                 "prio_descend", "slots"]

    def __init__(self, name=None, prio_descend=True):
        """Create the Signal object.

        :param name:
            The name of the signal. Presently not used for much, but may be
            used as a unique identifier for signals in the future.

        :param prio_descend:
            Determines the behaviour of slot list insertion. By default, slots
            with lower priority values are run first. This may be changed by
            setting prio_descend to ``False``.
        """
        self.name = name

        self._slots_lock = RLock()  # The GIL shouldn't be relied on!

        self._uid = 0
        self._uid_lock = Lock()

        self._defer = None  # Used in deferral

        self.prio_descend = prio_descend

        self.slots = list()

    def find_function(self, function):
        """Find the given :py:class::`~taillight.slot.Slot` instance(s), given
        a function.

        Since a function may be registered multiple times, this function
        returns a list of functions found.

        If a slot with the given function is not found, then a
        :py:class::`~taillight.slot.SlotNotFoundError` is raised.
        """
        ret = []
        with self._slots_lock:
            for slot in self.slots:
                if slot.function is function:
                    ret.append(function)

        if ret:
            return ret
        else:
            raise SlotNotFoundError("Slot not found: {}".format(
                repr(function)))

    def find_uid(self, uid):
        """Find the given :py:class::`~taillight.slot.Slot` instance(s), given
        a uid.

        Since only one :py:class:`~taillight.slot.Slot` can exist at one time
        with the given UID, only one slot is returned.

        If a slot with the given UID is not found, then a
        :py:class::`~taillight.slot.SlotNotFoundError` is raised.
        """
        with self._slots_lock:
            for slot in self.slots:
                if slot.uid == uid:
                    return slot

        raise SlotNotFoundError("Signal UID not found: {}".format(uid))

    def add(self, function, listener=ANY):
        """Add a given slot function to the signal with unspecified priority.

        ..note::
            This is an exact equivalent to (and wrapper for)
            :py:meth::`~taillight.signal.Signal.add_priority`(0, ...)

        :param function:
            The given function to add to the slot.

        :param listener:
            The sender this slot listens for.

        :returns:
            A :py:class::`~taillight.slot.Slot` object that can be used to
            delete the slot later.
        """
        return self.add_priority(function, priority, sender)

    def add_priority(self, priority, function, listener=ANY):
        """Add a given slot function to the signal with a given priority.

        :param priority:
            Priority of the slot, which determines its call order.

        :param function:
            The given function to add to the slot.

        :param listener:
            The sender this slot listens for.

        :returns:
            A :py:class::`~taillight.slot.Slot` object that can be used to
            delete the slot later.
        """
        with self._uid_lock:
            uid = self._uid
            self._uid += 1

        s = Slot(priority, uid, function, listener)

        with self._slots_lock:
            if self._defer is not None:
                # Requires lock to avoid racing with call
                raise SignalDeferralSetError("Cannot add due to deferral "
                                             "point being set")

            if self.prio_descend:
                insort_right(self.slots, s)
            else:
                insort_left(self.slots, s)

        return s

    def delete(self, slot):
        """Delete a slot from the signal.

        :param slot:
            The :py:class::`~taillight.slot.Slot` object to delete.
        """
        with self._slots_lock:
            if self._defer is not None:
                # Requires lock to avoid racing with call
                raise SignalDeferralSetError("Cannot delete due to deferral "
                                             "point being set")

            if isinstance(slot, Slot):
                self.slots.remove(slot)
            elif isinstance(slot, Iterable):
                slots = slot
                for slot in slots:
                    if not isinstance(slot, Slot):
                        raise TypeError("Expected Slot, got {}".format(
                            type(slot).__name__))

                    self.delete(slot)
            else:
                raise TypeError("Expected Slot or Iterable, got {}".format(
                    type(slot).__name__))

    def delete_uid(self, uid):
        """Delete the slot with the given UID from the signal.

        :param uid:
            The uid of the :py:class::`~taillight.slot.Slot` object to delete.
        """
        with self._slots_lock:
            self.delete(self.find_uid(uid))

    def reset_defer(self):
        """Reset the deferred status of the signal, causing the deferred point
        to be reset."""
        with self._slots_lock:
            # Requires lock to avoid racing with call
            self._defer = None

    def reset_call(self, sender, *args, **kwargs):
        """Call the signal, running all the slots, but reset the deferred
        status before running the functions.

        All arguments and keywords are passed to the slots when run.

        This is needed in threaded programs to avoid race conditions when
        calling reset_defer then call sequentially without some other form of
        locking outside taillight.

        Exceptions are propagated to the caller, except for
        :py:class::`~taillight.signal.SignalStop` and
        :py:class::`~taillight.signal.SignalDefer`.

        :param sender:
            The sender on this slot.

        :returns:
            A list of return values from the callbacks.
        """
        with self._slots_lock:
            self.reset_defer()
            return self.call(sender, *args, **kwargs)

    def call(self, sender, *args, **kwargs):
        """Call the signal.

        All arguments and keywords are passed to the slots when run.

        Exceptions are propagated to the caller, except for
        :py:class::`~taillight.signal.SignalStop` and
        :py:class::`~taillight.signal.SignalDefer`.

        :param sender:
            The sender on this slot.

        :returns:
            A list of return values from the callbacks.
        """
        ret = []

        with self._slots_lock:
            if self.defer is None:
                slots = iter(self.slots)
            else:
                slots = self._defer

            for slot in slots:
                if slot.sender is ANY or slot.listener == slot.sender:
                    # Run the slot
                    try:
                        ret.append(slot(sender, *args, **kwargs))
                    except SignalStop as e:
                        self.reset_defer()
                        return ret
                    except SignalDefer as e:
                        self._defer = slots
                        return ret

            self.reset_defer()

        return ret

    def __repr__(self):
        return "Signal(name={}, prio_descend={}, slots={}".format(
            self.name, self.prio_descend, self.slots)

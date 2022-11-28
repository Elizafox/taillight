# -*- coding: utf-8 -*-
# Copyright © 2017-2019 Elizabeth Myers. All rights reserved.
# This file is part of the taillight project. See LICENSE in the root
# directory for licensing information.

"This module contains the Signal class and exceptions related to signals."

import asyncio
from enum import Enum, IntEnum
from bisect import insort_right
from collections import deque, namedtuple
from collections.abc import Iterable
from inspect import iscoroutinefunction
from operator import attrgetter
from threading import Lock, RLock
from weakref import WeakValueDictionary

from taillight import ANY, TaillightException
from taillight.slot import Slot, SlotNotFoundError


# Detect if we should use a deque instead of a list for improved insertion
# performance
# pylint: disable=invalid-name
_SlotType = deque if hasattr(deque, "insert") else list


class SignalException(TaillightException):
    """The base for all signal exceptions."""


class SignalControl(SignalException):
    """The base for all signal control exceptions."""


class SignalStop(SignalControl):
    """The exception raised when a signal needs to be stopped."""


class SignalDefer(SignalControl):
    """The exception raised when a signal needs to be deferred."""


class SignalError(SignalException):
    """The base exception for signal errors."""


class SignalDeferralSetError(SignalError):
    """Raised if an operation cannot complete because a deferral point is
    set."""


class SignalDeferralSenderError(SignalError):
    """Raised if the operation cannot complete because the sender is
    incorrect."""


class SignalNotFoundError(SignalError):
    """The given signal was not found."""


class SignalStatus(Enum):
    """Constants for the state of signals."""

    STATUS_DONE = 1
    """All events executed during last invocation of call/call_async"""

    STATUS_STOP = 2
    """Events were terminated during last invocation of call/call_async"""

    STATUS_DEFER = 3
    """Events were paused during last invocation of call/call_async"""


class SignalPriority(IntEnum):
    """Constants for signal priority."""

    PRIORITY_NORMAL = 0
    """The normal priority point - this does not change even if
    ``prio_descend`` is in effect."""


# pylint: disable=too-many-instance-attributes
class Signal:
    """A signal is an object that keeps a list of functions for calling later
    based on events they listen for.

    These functions are referred to as slots. Each slot in taillight has
    several attributes: a priority, a UID (a monotonically increasing number
    based on the number of slot objects that have existed), a function, and
    arguments to call the function with.

    This is essentially the signals and slots pattern, but with support for
    slot priorities and having a well-defined order that the slots are called
    in. In addition, execution of slots may be stopped by raising
    :py:class:`~taillight.signal.SignalStop`. Signals may also be paused by
    raising :py:class:`~taillight.signal.SignalDefer`, where the signal will
    resume calling where it left off (preserving the arguments last called
    with, if none are passed in).

    When the signal is in a deferred state, adding or deleting slots is not
    allowed, as this would lead to inconsistencies in how the new slots should
    be called and how the deleted slots should be handled. However, a simple
    call to :py:meth:`~taillight.signal.Signal.reset_defer` resets the
    signal's deferred state; however, the calls will not pick up where they
    left off, and will restart from the beginning.

    Only one listener may be deferred at a time.

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

    Like blinker, two signals with the same name will have shared slots. Weak
    references are kept around to each signal internally, so you will need to
    keep a strong reference around to each signal (or use the class
    :py:class:`~taillight.signal.StrongSignal`).

    Due to the fact that all signals with the same name will share a slot,
    ``prio_descend`` cannot be changed once it has been decided for a slot,
    until all strong references to the signal are freed.

    However, unlike blinker, all references to functions in the slots are
    strong. The complexity of weak references to methods, and especially
    decorated functions, aren't considered worth it. This also allows for
    things such as slots using ``lambda``. If such functionality is required,
    it is easily implemented by using weakref proxies independently.

    :ivar slots:
        The slots associated with this signal.

    :ivar last_status:
        The results of the last invocation of call/call_async.
    """

    _DeferType = namedtuple("_DeferType", "iterator sender args kwargs")

    _sigcreate_lock = Lock()  # Locking for the below dict
    _signals = WeakValueDictionary()
    _siginit_lock = Lock()  # Locking for calls to __init__

    # pylint: disable=unused-argument
    def __new__(cls, name=None, prio_descend=True):
        if name is None:
            return super().__new__(cls)

        with Signal._sigcreate_lock:
            signal = cls._signals.get(name, super().__new__(cls))

            # This doesn't really hurt if we do it twice.
            cls._signals[name] = signal

            return signal

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
        with Signal._siginit_lock:
            # __new__ will result in the __init__ method being called, so
            # ensure we're not completely reset.
            if not hasattr(self, "slots"):
                self.slots = _SlotType()

        if name is None:
            name = "<anonymous>"

        self.name = name

        self._slots_lock = RLock()  # The GIL shouldn't be relied on!

        self._uid = 0
        self._uid_lock = Lock()

        self._defer = None  # Used in deferral
        self.last_status = None  # Last status of call()

        self.prio_descend = prio_descend

    def priority_higher(self, *args, boost=1):
        """Return a priority value above the slots specified in the
        arguments.

        This respects the value of ``prio_descend``.

        :param boost:
            Boost the priority by this amount.

        """
        if not args:
            args = self.slots

        attr = attrgetter("priority")
        if self.prio_descend:
            # Lower numbers = higher priority
            return attr(min(args, key=attr)) - boost

        # Higher numbers = higher priority
        return attr(max(args, key=attr)) + boost

    def priority_lower(self, *args, boost=1):
        """Return a priority value below the slots specified in the
        arguments.

        This respects the value of ``prio_descend``.

        :param boost:
            Boost the priority by this amount.

        """
        if not args:
            args = self.slots

        attr = attrgetter("priority")
        if self.prio_descend:
            # Higher numbers = lower priority
            return attr(max(args, key=attr)) + boost

        # Lower numbers = lower priority
        return attr(min(args, key=attr)) - boost

    def find_function(self, function):
        """Find the given :py:class:`~taillight.slot.Slot` instance(s), given
        a function.

        Since a function may be registered multiple times, this function
        returns a list of functions found.

        If a slot with the given function is not found, then a
        :py:class:`~taillight.slot.SlotNotFoundError` is raised.
        """
        ret = []
        with self._slots_lock:
            for slot in self.slots:
                if slot.function is function:
                    ret.append(slot)

        if ret:
            return ret

        raise SlotNotFoundError("Function not found: {}".format(
            repr(function)))

    def find_uid(self, uid):
        """Find the given :py:class:`~taillight.slot.Slot` instance(s), given
        a uid.

        Since only one :py:class:`~taillight.slot.Slot` can exist at one time
        with the given UID, only one slot is returned.

        If a slot with the given UID is not found, then a
        :py:class:`~taillight.slot.SlotNotFoundError` is raised.
        """
        with self._slots_lock:
            for slot in self.slots:
                if slot.uid == uid:
                    return slot

        raise SlotNotFoundError("Signal UID not found: {}".format(uid))

    def find_listener(self, listener):
        """Find the given :py:class:`~taillight.slot.Slot` instance(s) that
        are listening on the given listener.

        This returns a list of slots.

        If a slot with the given function is not found, then a
        :py:class:`~taillight.slot.SlotNotFoundError` is raised.
        """
        ret = []
        with self._slots_lock:
            for slot in self.slots:
                if slot.listener is listener:
                    ret.append(slot)

        if ret:
            return ret

        raise SlotNotFoundError("Listener not found: {}".format(
            repr(listener)))

    def __contains__(self, slot):
        return slot in self.slots

    def add(self, function=None, priority=SignalPriority.PRIORITY_NORMAL,
            listener=ANY):
        """Add a given slot function to the signal with a given priority.

        :param function:
            The given function to add to the slot. If set to None, this will
            be treated as a decorator.

        :param priority:
            Priority of the slot, which determines its call order.

        :param listener:
            The sender this slot listens for. This must be a hashable object.

        :returns:
            A :py:class:`~taillight.slot.Slot` object that can be used to
            delete the slot later.

        """
        if function is None:
            return self.add_wraps(priority, listener)

        with self._uid_lock:
            uid = self._uid
            self._uid += 1

        slot = Slot(self, priority, uid, function, listener)

        with self._slots_lock:
            if self._defer is not None:
                # Requires lock to avoid racing with call
                raise SignalDeferralSetError("Cannot add due to deferral "
                                             "point being set")

            insort_right(self.slots, slot)

        return slot

    def add_wraps(self, priority=SignalPriority.PRIORITY_NORMAL, listener=ANY):
        """Similar to :py:meth:`~taillight.signal.Signal.add`, but
        is for use as a decorator.

        Use this when :py:meth:`~tailight.signal.Signal.add` is not sufficient
        as a decorator (e.g. you need to set the args).

        :param priority:
            Priority of the slot, which determines its call order.

        :param listener:
            The sender this slot listens for.

        :returns:
            A :py:class:`~taillight.slot.Slot` object that can be used to
            delete the slot later.
        """
        def decorator(function):
            return self.add(function, priority, listener)

        return decorator

    def delete(self, target):
        """Delete a slot from the signal.

        :param target:
            The :py:class:`~taillight.slot.Slot` object(s) to delete.

        """
        with self._slots_lock:
            if self._defer is not None:
                # Requires lock to avoid racing with call
                raise SignalDeferralSetError("Cannot delete due to deferral "
                                             "point being set")

            if isinstance(target, Slot):
                self.slots.remove(target)
            elif isinstance(target, Iterable):
                for slot in target:
                    if not isinstance(slot, Slot):
                        raise TypeError("Expected Slot, got {}".format(
                            type(slot).__name__))

                    self.delete(slot)
            else:
                raise TypeError("Expected Slot or Iterable, got {}".format(
                    type(target).__name__))

    def delete_function(self, function):
        """Delete a function from the signal.

        This will delete every slot that contains this signal.

        :param function:
            The function to remove.

        """
        with self._slots_lock:
            self.delete(self.find_function(function))

    def delete_uid(self, uid):
        """Delete the slot with the given UID from the signal.

        :param uid:
            The uid of the :py:class:`~taillight.slot.Slot` object to delete.

        """
        with self._slots_lock:
            if self._defer is not None:
                # Requires lock to avoid racing with call
                raise SignalDeferralSetError("Cannot delete due to deferral "
                                             "point being set")

            for i, slot in enumerate(self.slots):
                if uid == slot.uid:
                    del self.slots[i]
                    return

        raise SlotNotFoundError("Signal UID not found: {}".format(uid))

    def clear(self):
        """Clear the slot of all signals."""
        with self._slots_lock:
            self.slots.clear()

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
        :py:class:`~taillight.signal.SignalStop` and
        :py:class:`~taillight.signal.SignalDefer`.

        :param sender:
            The sender on this slot.

        :returns:
            A list of return values from the callbacks.

        """
        with self._slots_lock:
            self.reset_defer()
            return self.call(sender, *args, **kwargs)

    def yield_slots(self, sender):
        """Yield slots from the slots list.

        This is useful for advanced usage;
        :py:meth:`~taillight.signal.Signal.call` also makes use of this.

        :param sender:
            The sender on this call.
        """
        with self._slots_lock:
            # Use reverse iterator if prio_descend is False (ascending order)
            slots = self.slots if self.prio_descend else reversed(self.slots)
            for slot in slots:
                if slot.listener is ANY or sender == slot.listener:
                    yield slot

    def defer_set_args(self, args=None, kwargs=None):
        """Set the arguments when the signal is deferred. If both arguments
        are None, the arguments are unset.

        This function should only be directly used if you need to manually
        unset the arguments before resuming a deferred call.
        """
        if args is None and kwargs is None:
            # Unset args
            args = ()
            kwargs = {}

        with self._slots_lock:
            if self._defer is None:
                return

            if args is None:
                args = self._defer.args

            if kwargs is None:
                kwargs = self._defer.kwargs

            iterator = self._defer.iterator
            sender = self._defer.sender

            self._defer = self._DeferType(iterator, sender, args, kwargs)

    # pylint: disable=inconsistent-return-statements
    def resume(self, sender):
        """Resume a deferred call.

        If the signal is not in a deferred state, this returns None; else it
        returns the results of the remaining calls.

        This is a wrapper around :py:meth:`~taillight.signal.Signal.call`, but
        it also includes checking if the signal is deferred. Otherwise, it
        shares all the semantics of ``call``.

        .. note::
            If any slot functions are awaitables, use
            :py:meth:`~taillight.signal.Signal.resume_async` instead.

        """
        with self._slots_lock:
            if self._defer is None:
                return

            return self.call(sender)

    def call(self, sender, *args, **kwargs):
        """Call the signal's slots.

        All arguments and keywords are passed to the slots when run. If a
        callback is resuming, the arguments from last time are deleted if any
        arguments are passed in, otherwise they're kept.

        Exceptions are propagated to the caller, except for
        :py:class:`~taillight.signal.SignalStop` and
        :py:class:`~taillight.signal.SignalDefer`.

        .. note::
            If any slot functions are awaitables, use
            :py:meth:`~taillight.signal.Signal.call_async` instead.

        :param sender:
            The sender on this call.

        :returns:
            A list of return values from the callbacks.

        """
        ret = []

        self.last_status = SignalStatus.STATUS_DONE

        with self._slots_lock:
            if self._defer is None:
                slots = self.yield_slots(sender)
            else:
                if sender is not None and sender != self._defer.sender:
                    raise SignalDeferralSenderError("deferred signal sender "
                                                    "unexpectedly changed")

                slots = self._defer.iterator

                if args or kwargs:
                    # Reset args
                    self.defer_set_args(args, kwargs)

                args = self._defer.args
                kwargs = self._defer.kwargs

            for slot in slots:
                # Run the slot
                try:
                    ret.append(slot(sender, *args, **kwargs))
                except SignalStop:
                    self.last_status = SignalStatus.STATUS_STOP
                    break
                except SignalDefer:
                    self.last_status = SignalStatus.STATUS_DEFER
                    self._defer = self._DeferType(slots, sender, args, kwargs)
                    return ret

            self.reset_defer()

        return ret

    async def call_async(self, sender, *args, **kwargs):
        """Call the signal's slots asynchronously.

        All functions which are really coroutines are yielded from;
        otherwise, they are simply called.

        This function is an awaitable.

        All arguments and keywords are passed to the slots when run. If a
        callback is resuming, the arguments from last time are deleted if
        any arguments are passed in, otherwise they're kept.

        Exceptions are propagated to the caller, except for
        :py:class:`~taillight.signal.SignalStop` and
        :py:class:`~taillight.signal.SignalDefer`.

        :param sender:
            The sender on this call.

        :returns:
            A list of return values from the callbacks.
        """

        ret = []
        slot_args = args
        slot_kwargs = kwargs

        self.last_status = SignalStatus.STATUS_DONE

        with self._slots_lock:
            if self._defer is None:
                slots = self.yield_slots(sender)
            else:
                # FIXME: allow multiple pending deferrals
                if sender is not None and sender != self._defer.sender:
                    raise SignalDeferralSenderError("deferred signal "
                                                    "sender unexpectedly "
                                                    "changed")

                slots = self._defer.iterator

                if args or kwargs:
                    # Reset args
                    self.defer_set_args(args, kwargs)

                slot_args = self._defer.args
                slot_kwargs = self._defer.kwargs

            for slot in slots:
                # Run the slot
                try:
                    s_ret = slot(sender, *slot_args, **slot_kwargs)
                    if iscoroutinefunction(slot.function):
                        s_ret = yield from s_ret

                    ret.append(s_ret)
                except SignalStop:
                    self.last_status = SignalStatus.STATUS_STOP
                    break
                except SignalDefer:
                    self.last_status = SignalStatus.STATUS_DEFER
                    self._defer = self._DeferType(slots, sender, args,
                                                  kwargs)
                    return ret

            self.reset_defer()

        return ret

    # pylint: disable=inconsistent-return-statements
    async def resume_async(self, sender):
        """Resume a deferred asynchronous call.

        If the signal is not in a deferred state, this returns None; else
        it returns the results of the remaining calls.

        This is a wrapper around
        :py:meth:`~taillight.signal.Signal.call_async`, but it also
        includes checking if the signal is deferred. Otherwise, it shares
        all the semantics of ``call_async``.
        """
        with self._slots_lock:
            if self._defer is None:
                return

            ret = yield from self.call_async(sender)
            return ret

    def __len__(self):
        return len(self.slots)

    def __repr__(self):
        return "Signal(name={}, prio_descend={}, slots={})".format(
            self.name, self.prio_descend, self.slots)


class StrongSignal(Signal):
    """Like a :py:class:`~taillight.signal.Signal`, but strong references are
    kept to the signals (so you don't have to keep a reference around).

    Signals will stick around (and all StrongSignals instantiated with the
    same name will return the same signal) until removed with
    :py:class:`~taillight.signal.StrongSignal.delete_signal`.
    """

    # Use separate locks than above...
    _sigcreate_lock = Lock()  # Locking for the below dict
    _signals = dict()
    _siginit_lock = Lock()  # Locking for calls to __init__

    @classmethod
    def delete_signal(cls, signal):
        """Delete a signal.

        This function is needed, as strong references are kept around
        indefinitely, until this function is called to remove the signal.

        If the signal is not found, a
        :py:class:`~taillight.signal.SignalNotFoundError` exception is raised.

        .. warning::
            Use care when using this function, as it is easy to introduce
            subtle errors when you have a reference kept around to the
            original signal, but it's not stored here.

        :param signal:
            Name of the signal to remove.
        """
        try:
            del cls._signals[signal]
        except ValueError:
            raise SignalNotFoundError("Signal not found: {}".format(signal))

    def __repr__(self):
        return "StrongSignal(name={}, prio_descend={}, slots={})".format(
            self.name, self.prio_descend, self.slots)


class UnsharedSignal(Signal):
    """Like a :py:class:`~taillight.signal.Signal`, but multiple calls with
    the same name do not return the same signal.

    This works just like an anonymous signal semantically, but can be tagged
    with a name.
    """

    # We can use the default implementation
    # pylint: disable=arguments-differ,unused-argument
    def __new__(cls, *args, **kwargs):
        return object.__new__(cls)

    def __repr__(self):
        return "UnsharedSignal(name={}, prio_descend={}, slots={})".format(
            self.name, self.prio_descend, self.slots)

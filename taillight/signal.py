# -*- coding: utf-8 -*-
# Copyright © 2015 Elizabeth Myers. All rights reserved.
# This file is part of the taillight project. See LICENSE in the root
# directory for licensing information.

"This module contains the Signal class and exceptions related to signals."

from warnings import warn

try:
    import asyncio
except ImportError:
    warn("Could not import asyncio, Signal.call_async will not work!",
         ImportWarning)
    asyncio = None

from bisect import insort_left, insort_right
from collections import namedtuple
from collections.abc import Iterable
from operator import attrgetter
from threading import Lock, RLock
from weakref import WeakValueDictionary

from taillight import ANY, TaillightException
from taillight.slot import Slot, SlotNotFoundError


class SignalException(TaillightException):
    """The base for all signal exceptions."""


class SignalStop(SignalException):
    """The exception raised when a signal needs to be stopped."""


class SignalDefer(SignalException):
    """The exception raised when a signal needs to be deferred."""


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

    Like blinker, two signals with the same name will have shared slots. This
    does have an important implication: ``prio_descend`` cannot be changed
    once it has been decided for a slot, until all strong references to the
    signal are freed.

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

    STATUS_DONE = 0
    """All events executed during last invocation of call/call_async"""

    STATUS_STOP = 1
    """Events were terminated during last invocation of call/call_async"""

    STATUS_DEFER = 2
    """Events were paused during last invocation of call/call_async"""

    PRIORITY_NORMAL = 0
    """The normal priority point - this does not change even if
    ``prio_descend`` is in effect."""

    _DeferType = namedtuple("_DeferType", "iterator args kwargs")

    _sigcreate_lock = Lock()  # Locking for the below dict
    _signals = WeakValueDictionary()
    _siginit_lock = Lock()  # Locking for calls to __init__

    def __new__(cls, name=None, prio_descend=True):
        if name is None:
            return super().__new__(cls)

        with Signal._sigcreate_lock:
            signal = Signal._signals.get(name, super().__new__(cls))

            # This doesn't really hurt if we do it twice.
            Signal._signals[name] = signal

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
            if hasattr(self, "slots"):
                return
            else:
                self.slots = list()

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
        else:
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
        else:
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
        else:
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
        else:
            raise SlotNotFoundError("Listener not found: {}".format(
                repr(listener)))

    def __contains__(self, slot):
        return slot in self.slots

    def add(self, function=None, priority=PRIORITY_NORMAL, listener=ANY):
        """Add a given slot function to the signal with a given priority.

        :param function:
            The given function to add to the slot. If set to None, this will
            be treated as a decorator.

        :param priority:
            Priority of the slot, which determines its call order.

        :param listener:
            The sender this slot listens for.

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

    def add_wraps(self, priority=PRIORITY_NORMAL, listener=ANY):
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

    def delete(self, slot):
        """Delete a slot from the signal.

        :param slot:
            The :py:class:`~taillight.slot.Slot` object to delete.

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
        if (args, kwargs) is (None, None):
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

            self._defer = self._DeferType(self._defer.iterator, args, kwargs)

    def resume(self, sender):
        """Resume a deferred call.

        If the signal is not in a deferred state, this returns None; else it
        returns the results of the remaining calls.

        This is a wrapper around :py:meth:`~taillight.signal.Signal.call`, but
        it also includes checking if the signal is deferred. Otherwise, it
        shares all the semantics of ``call``.

        .. note::
            If any slot functions are asyncio coroutines, use
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
            If any slot functions are asyncio coroutines, use
            :py:meth:`~taillight.signal.Signal.call_async` instead.

        :param sender:
            The sender on this call.

        :returns:
            A list of return values from the callbacks.

        """
        ret = []

        self.last_status = self.STATUS_DONE

        with self._slots_lock:
            if self._defer is None:
                slots = self.yield_slots(sender)
            else:
                # XXX ignores sender
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
                except SignalStop as e:
                    self.last_status = self.STATUS_STOP
                    break
                except SignalDefer as e:
                    self.last_status = self.STATUS_DEFER
                    self._defer = self._DeferType(slots, args, kwargs)
                    return ret

            self.reset_defer()

        return ret

    if asyncio is not None:
        @asyncio.coroutine
        def call_async(self, sender, *args, **kwargs):
            """Call the signal's slots asynchronously.

            All functions which are really coroutines are yielded from;
            otherwise, they are simply called.

            This function is an asyncio coroutine - in Python 3.5, this is
            subject to become an awaitable.

            All arguments and keywords are passed to the slots when run. If a
            callback is resuming, the arguments from last time are deleted if
            any arguments are passed in, otherwise they're kept.

            Exceptions are propagated to the caller, except for
            :py:class:`~taillight.signal.SignalStop` and
            :py:class:`~taillight.signal.SignalDefer`.

            .. warning::
                This method requires asyncio to be made available. If it is
                unavailable, no fallback is provided (it wouldn't make any
                sense).

            :param sender:
                The sender on this call.

            :returns:
                A list of return values from the callbacks.

            """

            ret = []
            slot_args = args
            slot_kwargs = kwargs

            self.last_status = self.STATUS_DONE

            with self._slots_lock:
                if self._defer is None:
                    slots = self.yield_slots(sender)
                else:
                    # XXX ignores sender
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
                        if asyncio.iscoroutinefunction(slot.function):
                            s_ret = yield from s_ret

                        ret.append(s_ret)
                    except SignalStop as e:
                        self.last_status = self.STATUS_STOP
                        break
                    except SignalDefer as e:
                        self.last_status = self.STATUS_DEFER
                        self._defer = self._DeferType(slots, args, kwargs)
                        return ret

                self.reset_defer()

            return ret

        @asyncio.coroutine
        def resume_async(self, sender):
            """Resume a deferred asynchronous call.

            If the signal is not in a deferred state, this returns None; else
            it returns the results of the remaining calls.

            This is a wrapper around
            :py:meth:`~taillight.signal.Signal.call_async`, but it also
            includes checking if the signal is deferred. Otherwise, it shares
            all the semantics of ``call_async``.

            .. warning::
                This method requires asyncio to be made available. If it is
                unavailable, no fallback is provided (it wouldn't make any
                sense).

            """
            with self._slots_lock:
                if self._defer is None:
                    return

                ret = yield from self.call_async(sender)
                return ret

    def __repr__(self):
        return "Signal(name={}, prio_descend={}, slots={})".format(
            self.name, self.prio_descend, self.slots)


class UnsharedSignal(Signal):
    """Like a :py:class:`~taillight.signal.Signal`, but multiple calls with
    the same name do not return the same signal.

    This works just like an anonymous signal semantically, but can be tagged
    with a name.
    
    """

    def __new__(cls, *args, **kwargs):
        return object.__new__(cls)

    def __repr__(self):
        return "UnsharedSignal(name={}, prio_descend={}, slots={})".format(
            self.name, self.prio_descend, self.slots)

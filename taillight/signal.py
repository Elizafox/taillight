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

    This is conceptually similar to (and a great deal like) signals and slots,
    but with greater emphasis on priorities and having a well-defined order
    that the slots are called with. In addition, execution of slots may be
    stopped by raising :py:class:`~taillight.signal.SignalStop`. Signals may
    also be paused by raising :py:class:`~taillight.signal.SignalDefer`, where
    the signal will resume calling where it left off (preserving the arguments
    last called with, if none are passed in).

    When the signal is in a deferred state, adding or deleting slots is not
    allowed, as this would lead to inconsistencies in how the new slots should
    be called and how the deleted slots should be handled. However, a simple
    call to :py:meth:`~taillight.signal.Signal.reset_defer` resets the
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

    Note unlike blinker, all references to functions in the slots are strong.
    This is to ease the lifecycle management of objects, and allow for things
    such as slots using ``lambda``. If such functionality is required, it is
    easily implemented by using weakref proxies independently.

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

    _DeferType = namedtuple("_DeferType", "iterator args kwargs")

    _sigcreate_lock = Lock()  # Locking for the below dict
    _signals = WeakValueDictionary()

    def __new__(cls, name=None, prio_descend=True):
        with Signal._sigcreate_lock:
            if name is None:
                return super().__new__(cls)

            signal = Signal._signals.get(name, None)
            if signal is None:
                signal = Signal._signals[name] = super().__new__(cls)

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
        self.name = name

        self._slots_lock = RLock()  # The GIL shouldn't be relied on!

        self._uid = 0
        self._uid_lock = Lock()

        self._defer = None  # Used in deferral
        self.last_status = None  # Last status of call()

        self.prio_descend = prio_descend

        self.slots = list()

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

    def add(self, function=None, priority=0, listener=ANY):
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

        s = Slot(self, priority, uid, function, listener)

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

    def add_wraps(self, priority=0, listener=ANY):
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
            for slot in self.slots:
                if slot.listener is ANY or sender == slot.listener:
                    yield slot

    def defer_set_args(self, args=(), kwargs={}):
        """Set the arguments when the signal is deferred.

        This is an advanced function and should only be used if you truly know
        what you're doing.

        """
        with self._slots_lock:
            if self._defer is not None:
                self._defer = self._DeferType(self._defer.iterator, args,
                                              kwargs)

    def call(self, sender, *args, **kwargs):
        """Call the signal's slots.

        All arguments and keywords are passed to the slots when run. If a
        callback is resuming, the arguments from last time are deleted if any
        arguments are passed in, otherwise they're kept.

        Exceptions are propagated to the caller, except for
        :py:class:`~taillight.signal.SignalStop` and
        :py:class:`~taillight.signal.SignalDefer`.

        .. note::
            If any arguments are asyncio coroutines, use
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

                if not args and kwargs:
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

            self.last_status = self.STATUS_DONE

            with self._slots_lock:
                if self._defer is None:
                    slots = self.yield_slots(sender)
                else:
                    # XXX ignores sender
                    slots = self._defer.iterator

                    if not args and kwargs:
                        args = self._defer.args
                        kwargs = self._defer.kwargs

                for slot in slots:
                    # Run the slot
                    try:
                        s_ret = slot(sender, *args, **kwargs)
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

    def __repr__(self):
        return "Signal(name={}, prio_descend={}, slots={}".format(
            self.name, self.prio_descend, self.slots)


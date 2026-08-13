# Copyright © 2017-2026 Elizabeth Ashford.
# This file is part of the taillight project. See LICENSE in the root
# directory for licensing information.

"This module contains the Signal class and exceptions related to signals."

from __future__ import annotations

from bisect import insort_right
from collections import deque
from collections.abc import Awaitable, Callable, Hashable, Iterable, Iterator
from dataclasses import dataclass, replace
from enum import Enum, IntEnum
from inspect import isawaitable
from threading import Lock, RLock
from typing import Any, Generic, TypeAlias, TypeVar, cast, overload
from weakref import WeakValueDictionary

from taillight import ANY, TaillightException
from taillight.slot import Slot, SlotNotFoundError

# pylint: disable=invalid-name
_SlotType = deque

ResultT = TypeVar("ResultT")
CallbackResult: TypeAlias = ResultT | Awaitable[ResultT]
Callback: TypeAlias = Callable[..., CallbackResult[ResultT]]


@dataclass(frozen=True)
class _DeferredCall(Generic[ResultT]):
    """The state required to resume one deferred invocation."""

    iterator: Iterator[Slot[CallbackResult[ResultT]]]
    sender: object
    args: tuple[Any, ...]
    kwargs: dict[str, Any]


class _SignalMeta(type):
    """Construct and cache named signals without publishing partial objects."""

    def __call__(
        cls, name: Hashable | None = None, prio_descend: bool = True
    ) -> Any:
        signal_cls = cast(Any, cls)
        if name is None or not signal_cls._share_by_name:
            return super().__call__(name, prio_descend)

        with signal_cls._sigcreate_lock:
            signal = signal_cls._signals.get(name)
            if signal is None:
                signal = super().__call__(name, prio_descend)
                signal_cls._signals[name] = signal

            return signal


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
class Signal(Generic[ResultT], metaclass=_SignalMeta):
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
    call to :py:meth:`~taillight.signal.Signal.reset_defer` discards the next
    deferred call, while :py:meth:`~taillight.signal.Signal.reset_defers`
    discards all of them.

    Multiple calls may be deferred at a time. Deferred calls are resumed in
    last-in, first-out order.

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

    _share_by_name = True
    _sigcreate_lock = Lock()  # Locking for the below dict
    _signals: Any = WeakValueDictionary()

    def __init__(
        self, name: Hashable | None = None, prio_descend: bool = True
    ) -> None:
        """Create the Signal object.

        :param name:
            The name of the signal. Presently not used for much, but may be
            used as a unique identifier for signals in the future.

        :param prio_descend:
            Determines the behaviour of slot list insertion. By default, slots
            with lower priority values are run first. This may be changed by
            setting prio_descend to ``False``.

        """
        self.slots: deque[Slot[CallbackResult[ResultT]]] = _SlotType()

        if name is None:
            name = "<anonymous>"

        self.name = name

        self._slots_lock = RLock()  # The GIL shouldn't be relied on!

        self._uid = 0
        self._uid_lock = Lock()

        self._defers: list[_DeferredCall[ResultT]] = []
        self.last_status: SignalStatus | None = None

        self.prio_descend = prio_descend

    @property
    def _defer(self) -> _DeferredCall[ResultT] | None:
        """Return the next deferred call, for compatibility with older code."""
        return self._defers[-1] if self._defers else None

    @property
    def pending_deferrals(self) -> int:
        """Return the number of calls waiting to be resumed."""
        with self._slots_lock:
            return len(self._defers)

    def priority_higher(
        self, *args: Slot[Any], boost: int = 1
    ) -> int:
        """Return a priority value above the slots specified in the
        arguments.

        This respects the value of ``prio_descend``.

        :param boost:
            Boost the priority by this amount.

        """
        slots: Iterable[Slot[Any]] = args or self.slots
        if self.prio_descend:
            # Lower numbers = higher priority
            return min(slots, key=lambda slot: slot.priority).priority - boost

        # Higher numbers = higher priority
        return max(slots, key=lambda slot: slot.priority).priority + boost

    def priority_lower(
        self, *args: Slot[Any], boost: int = 1
    ) -> int:
        """Return a priority value below the slots specified in the
        arguments.

        This respects the value of ``prio_descend``.

        :param boost:
            Boost the priority by this amount.

        """
        slots: Iterable[Slot[Any]] = args or self.slots
        if self.prio_descend:
            # Higher numbers = lower priority
            return max(slots, key=lambda slot: slot.priority).priority + boost

        # Lower numbers = lower priority
        return min(slots, key=lambda slot: slot.priority).priority - boost

    def find_function(
        self, function: Callback[ResultT]
    ) -> list[Slot[CallbackResult[ResultT]]]:
        """Find the given :py:class:`~taillight.slot.Slot` instance(s), given
        a function.

        Since a function may be registered multiple times, this function
        returns a list of functions found.

        If a slot with the given function is not found, then a
        :py:class:`~taillight.slot.SlotNotFoundError` is raised.
        """
        ret: list[Slot[CallbackResult[ResultT]]] = []
        with self._slots_lock:
            for slot in self.slots:
                if slot.function is function:
                    ret.append(slot)

        if ret:
            return ret

        raise SlotNotFoundError(f"Function not found: {repr(function)}")

    def find_uid(self, uid: int) -> Slot[CallbackResult[ResultT]]:
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

        raise SlotNotFoundError(f"Signal UID not found: {uid}")

    def find_listener(
        self, listener: object
    ) -> list[Slot[CallbackResult[ResultT]]]:
        """Find the given :py:class:`~taillight.slot.Slot` instance(s) that
        are listening on the given listener.

        This returns a list of slots.

        If a slot with the given function is not found, then a
        :py:class:`~taillight.slot.SlotNotFoundError` is raised.
        """
        ret: list[Slot[CallbackResult[ResultT]]] = []
        with self._slots_lock:
            for slot in self.slots:
                if slot.listener is listener:
                    ret.append(slot)

        if ret:
            return ret

        raise SlotNotFoundError(f"Listener not found: {repr(listener)}")

    def __contains__(self, slot: object) -> bool:
        return slot in self.slots

    @overload
    def add(
        self,
        function: Callback[ResultT],
        priority: int = SignalPriority.PRIORITY_NORMAL,
        listener: object = ANY,
    ) -> Slot[CallbackResult[ResultT]]: ...

    @overload
    def add(
        self,
        function: None = None,
        priority: int = SignalPriority.PRIORITY_NORMAL,
        listener: object = ANY,
    ) -> Callable[[Callback[ResultT]], Slot[CallbackResult[ResultT]]]: ...

    def add(
        self,
        function: Callback[ResultT] | None = None,
        priority: int = SignalPriority.PRIORITY_NORMAL,
        listener: object = ANY,
    ) -> (
        Slot[CallbackResult[ResultT]]
        | Callable[[Callback[ResultT]], Slot[CallbackResult[ResultT]]]
    ):
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

        slot: Slot[CallbackResult[ResultT]] = Slot(
            self, priority, uid, function, listener)

        with self._slots_lock:
            if self._defers:
                # Requires lock to avoid racing with call
                raise SignalDeferralSetError("Cannot add due to deferral "
                                             "point being set")

            insort_right(self.slots, slot)

        return slot

    def add_wraps(
        self,
        priority: int = SignalPriority.PRIORITY_NORMAL,
        listener: object = ANY,
    ) -> Callable[[Callback[ResultT]], Slot[CallbackResult[ResultT]]]:
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
        def decorator(
            function: Callback[ResultT],
        ) -> Slot[CallbackResult[ResultT]]:
            return self.add(function, priority, listener)

        return decorator

    def delete(
        self,
        target: Slot[CallbackResult[ResultT]]
        | Iterable[Slot[CallbackResult[ResultT]]],
    ) -> None:
        """Delete a slot from the signal.

        :param target:
            The :py:class:`~taillight.slot.Slot` object(s) to delete.

        """
        with self._slots_lock:
            if self._defers:
                # Requires lock to avoid racing with call
                raise SignalDeferralSetError("Cannot delete due to deferral "
                                             "point being set")

            if isinstance(target, Slot):
                self.slots.remove(target)
            elif isinstance(target, Iterable):
                for slot in target:
                    if not isinstance(slot, Slot):
                        raise TypeError(f"Expected Slot, got {type(slot).__name__}")

                    self.delete(slot)
            else:
                target_type = type(target).__name__
                raise TypeError(f"Expected Slot or Iterable, got {target_type}")

    def delete_function(self, function: Callback[ResultT]) -> None:
        """Delete a function from the signal.

        This will delete every slot that contains this signal.

        :param function:
            The function to remove.

        """
        with self._slots_lock:
            self.delete(self.find_function(function))

    def delete_uid(self, uid: int) -> None:
        """Delete the slot with the given UID from the signal.

        :param uid:
            The uid of the :py:class:`~taillight.slot.Slot` object to delete.

        """
        with self._slots_lock:
            if self._defers:
                # Requires lock to avoid racing with call
                raise SignalDeferralSetError("Cannot delete due to deferral "
                                             "point being set")

            for i, slot in enumerate(self.slots):
                if uid == slot.uid:
                    del self.slots[i]
                    return

        raise SlotNotFoundError(f"Signal UID not found: {uid}")

    def clear(self) -> None:
        """Clear the slot of all signals."""
        with self._slots_lock:
            if self._defers:
                raise SignalDeferralSetError(
                    "Cannot clear due to deferral point being set")
            self.slots.clear()

    def reset_defer(self) -> None:
        """Discard the next deferred call, if one exists."""
        with self._slots_lock:
            if self._defers:
                self._defers.pop()

    def reset_defers(self) -> None:
        """Discard all deferred calls."""
        with self._slots_lock:
            self._defers.clear()

    def reset_call(
        self, sender: object, *args: Any, **kwargs: Any
    ) -> list[CallbackResult[ResultT]]:
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
            self.reset_defers()
            return self.call(sender, *args, **kwargs)

    def yield_slots(
        self, sender: object
    ) -> Iterator[Slot[CallbackResult[ResultT]]]:
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

    def defer_set_args(
        self,
        args: tuple[Any, ...] | None = None,
        kwargs: dict[str, Any] | None = None,
    ) -> None:
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
            if not self._defers:
                return None

            deferred = self._defers[-1]
            if args is None:
                args = deferred.args

            if kwargs is None:
                kwargs = deferred.kwargs

            self._defers[-1] = replace(deferred, args=args, kwargs=kwargs)

    # pylint: disable=inconsistent-return-statements
    def resume(
        self, sender: object | None = None
    ) -> list[CallbackResult[ResultT]] | None:
        """Resume a deferred call.

        If the signal is not in a deferred state, this returns None; else it
        returns the results of the remaining calls.

        Deferred calls are resumed in last-in, first-out order. ``sender``
        must match the sender of the next deferred call unless it is ``None``.

        .. note::
            If any slot functions are awaitables, use
            :py:meth:`~taillight.signal.Signal.resume_async` instead.

        """
        with self._slots_lock:
            if not self._defers:
                return None

            deferred = self._take_deferred(sender)

        return self._run(deferred, resumed=True)

    def _new_call(
        self, sender: object, args: tuple[Any, ...], kwargs: dict[str, Any]
    ) -> _DeferredCall[ResultT]:
        """Create an isolated frame for a new signal invocation."""
        with self._slots_lock:
            slots = iter(tuple(self.yield_slots(sender)))
        return _DeferredCall(slots, sender, args, kwargs)

    def _take_deferred(self, sender: object | None) -> _DeferredCall[ResultT]:
        """Remove and return the next deferred frame after validating it."""
        deferred = self._defers[-1]
        if sender is not None and sender != deferred.sender:
            raise SignalDeferralSenderError(
                "deferred signal sender unexpectedly changed")
        return self._defers.pop()

    def _run(
        self, deferred: _DeferredCall[ResultT], resumed: bool = False
    ) -> list[CallbackResult[ResultT]]:
        """Run a synchronous invocation frame until completion or deferral."""
        ret: list[CallbackResult[ResultT]] = []
        self.last_status = SignalStatus.STATUS_DONE

        for slot in deferred.iterator:
            try:
                ret.append(slot(
                    deferred.sender, *deferred.args, **deferred.kwargs))
            except SignalStop:
                self.last_status = SignalStatus.STATUS_STOP
                break
            except SignalDefer:
                self.last_status = SignalStatus.STATUS_DEFER
                with self._slots_lock:
                    self._defers.append(deferred)
                break
            except BaseException:
                if resumed:
                    with self._slots_lock:
                        self._defers.append(deferred)
                raise

        return ret

    def call(
        self, sender: object, *args: Any, **kwargs: Any
    ) -> list[CallbackResult[ResultT]]:
        """Call the signal's slots.

        All arguments and keywords are passed to the slots when run. This
        always starts a new invocation; use
        :py:meth:`~taillight.signal.Signal.resume` to continue a deferred one.

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
        return self._run(self._new_call(sender, args, kwargs))

    async def call_async(
        self, sender: object, *args: Any, **kwargs: Any
    ) -> list[ResultT]:
        """Call the signal's slots asynchronously.

        Awaitable return values are awaited; other return values are collected
        directly. This includes awaitables returned by regular functions and
        callable objects, not only functions declared with ``async def``.

        This function is an awaitable.

        All arguments and keywords are passed to the slots when run. This
        always starts a new invocation; use
        :py:meth:`~taillight.signal.Signal.resume_async` to continue a
        deferred one.

        Exceptions are propagated to the caller, except for
        :py:class:`~taillight.signal.SignalStop` and
        :py:class:`~taillight.signal.SignalDefer`.

        :param sender:
            The sender on this call.

        :returns:
            A list of return values from the callbacks.
        """

        return await self._run_async(self._new_call(sender, args, kwargs))

    async def _run_async(
        self, deferred: _DeferredCall[ResultT], resumed: bool = False
    ) -> list[ResultT]:
        """Run an asynchronous frame until completion or deferral."""
        ret: list[ResultT] = []
        self.last_status = SignalStatus.STATUS_DONE

        for slot in deferred.iterator:
            try:
                result = slot(
                    deferred.sender, *deferred.args, **deferred.kwargs)
                if isawaitable(result):
                    result = await result
                ret.append(cast(ResultT, result))
            except SignalStop:
                self.last_status = SignalStatus.STATUS_STOP
                break
            except SignalDefer:
                self.last_status = SignalStatus.STATUS_DEFER
                with self._slots_lock:
                    self._defers.append(deferred)
                break
            except BaseException:
                if resumed:
                    with self._slots_lock:
                        self._defers.append(deferred)
                raise

        return ret

    # pylint: disable=inconsistent-return-statements
    async def resume_async(
        self, sender: object | None = None
    ) -> list[ResultT] | None:
        """Resume a deferred asynchronous call.

        If the signal is not in a deferred state, this returns None; else
        it returns the results of the remaining calls.

        Deferred calls are resumed in last-in, first-out order. ``sender``
        must match the sender of the next deferred call unless it is ``None``.
        """
        with self._slots_lock:
            if not self._defers:
                return None

            deferred = self._take_deferred(sender)

        return await self._run_async(deferred, resumed=True)

    def __len__(self) -> int:
        return len(self.slots)

    def __repr__(self) -> str:
        return (
            f"Signal(name={self.name}, prio_descend={self.prio_descend}, "
            f"slots={self.slots})"
        )


class StrongSignal(Signal[ResultT]):
    """Like a :py:class:`~taillight.signal.Signal`, but strong references are
    kept to the signals (so you don't have to keep a reference around).

    Signals will stick around (and all StrongSignals instantiated with the
    same name will return the same signal) until removed with
    :py:class:`~taillight.signal.StrongSignal.delete_signal`.
    """

    # Use separate locks than above...
    _sigcreate_lock = Lock()  # Locking for the below dict
    _signals: Any = {}

    @classmethod
    def delete_signal(cls, signal: Hashable) -> None:
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
        with cls._sigcreate_lock:
            try:
                del cls._signals[signal]
            except KeyError as error:
                raise SignalNotFoundError(
                    f"Signal not found: {signal}") from error

    def __repr__(self) -> str:
        return (
            f"StrongSignal(name={self.name}, prio_descend={self.prio_descend}, "
            f"slots={self.slots})"
        )


class UnsharedSignal(Signal[ResultT]):
    """Like a :py:class:`~taillight.signal.Signal`, but multiple calls with
    the same name do not return the same signal.

    This works just like an anonymous signal semantically, but can be tagged
    with a name.
    """

    _share_by_name = False

    def __repr__(self) -> str:
        return (
            f"UnsharedSignal(name={self.name}, prio_descend={self.prio_descend}, "
            f"slots={self.slots})"
        )

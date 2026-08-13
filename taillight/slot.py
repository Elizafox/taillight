# Copyright © 2017-2026 Elizabeth Ashford.
# This file is part of the taillight project. See LICENSE in the root
# directory for licensing information.

"""This module contains the Slot class and slot-related exceptions."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from functools import update_wrapper
from typing import TYPE_CHECKING, Any, Generic, TypeVar

from taillight import TaillightException

if TYPE_CHECKING:
    from taillight.signal import Signal as SignalType


ReturnT = TypeVar("ReturnT")


class SlotError(TaillightException):
    """The base class for all slot errors."""


class SlotNotFoundError(SlotError):
    """Raised when a given slot is not found."""


@dataclass(order=True)
class Slot(Generic[ReturnT]):
    """A slot in a given signal.

    This is also callable, for purposes of enabling decorator usage.

    You probably do not want to instantiate this yourself. You should use
    :py:meth:`~taillight.signal.Signal.add`.

    """

    signal: SignalType[Any] = field(compare=False, repr=False)
    priority: int
    uid: int
    function: Callable[..., ReturnT] = field(compare=False, repr=False)
    listener: object = field(compare=False, repr=False)

    def __post_init__(self) -> None:
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
            The sender filter for this slot.

        """
        update_wrapper(self, self.function)

    def __call__(self, sender: object, *args: Any, **kwargs: Any) -> ReturnT:
        return self.function(sender, *args, **kwargs)

    def disconnect(self) -> None:
        """Remove this slot from its signal."""
        self.signal.delete(self)

    def __hash__(self) -> int:
        return hash((self.signal, self.priority, self.uid, self.function,
                     self.listener))

    def __repr__(self) -> str:
        return (
            f"Slot(priority={self.priority}, uid={self.uid}, "
            f"function={self.function}, listener={self.listener})"
        )

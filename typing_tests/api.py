"""Static checks for the public generic API."""

from collections.abc import Awaitable

from taillight import CallResult, PriorityOrder, Signal, Slot

signal: Signal[int] = Signal(priority_order=PriorityOrder.ASCENDING)
sync_slot: Slot[int | Awaitable[int]] = signal.add(lambda sender: 1)


@signal.add()
def decorated(sender: object) -> int:
    return 2


async def asynchronous(sender: object) -> int:
    return 3


async_slot: Slot[int | Awaitable[int]] = signal.add(asynchronous)
sync_result: CallResult[int | Awaitable[int]] = signal.emit("sender")


async def check_async_api() -> None:
    async_result: CallResult[int] = await signal.call_async("sender")
    resumed: CallResult[int] | None = await signal.resume_async()
    _ = async_result, resumed


_ = sync_slot, decorated, async_slot, sync_result

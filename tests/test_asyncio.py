import asyncio
import unittest

from taillight import signal


class TestCallSlot(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.signal = signal.Signal()

    async def test_async_function(self):
        async def callback(sender):
            await asyncio.sleep(0)
            return sender

        self.signal.add(callback)

        self.assertEqual(await self.signal.call_async("sender"), ["sender"])

    async def test_sync_function(self):
        self.signal.add(lambda sender: sender)

        self.assertEqual(await self.signal.call_async("sender"), ["sender"])

    async def test_sync_function_returning_awaitable(self):
        async def result():
            await asyncio.sleep(0)
            return 42

        self.signal.add(lambda sender: result())

        self.assertEqual(await self.signal.call_async("sender"), [42])

    async def test_async_callable_object(self):
        class Callback:
            async def __call__(self, sender):
                return sender

        self.signal.add(Callback())

        self.assertEqual(await self.signal.call_async("sender"), ["sender"])

    async def test_mixed_callbacks_preserve_order(self):
        async def async_callback(sender):
            await asyncio.sleep(0)
            return 2

        self.signal.add(lambda sender: 1)
        self.signal.add(async_callback)
        self.signal.add(lambda sender: 3)

        self.assertEqual(await self.signal.call_async("sender"), [1, 2, 3])

    async def test_arguments_survive_multiple_deferrals(self):
        def defer(sender, value):
            raise signal.SignalDefer

        def capture(sender, value):
            return value

        self.signal.add(defer)
        self.signal.add(defer)
        self.signal.add(capture)

        self.assertEqual(
            await self.signal.call_async("sender", "value"), [])
        self.assertEqual(await self.signal.resume_async("sender"), [])
        self.assertEqual(
            await self.signal.resume_async("sender"), ["value"])

    async def test_multiple_calls_defer_independently(self):
        def defer(sender, value):
            raise signal.SignalDefer

        def capture(sender, value):
            return sender, value

        self.signal.add(defer)
        self.signal.add(capture)

        self.assertEqual(await self.signal.call_async("first", 1), [])
        self.assertEqual(await self.signal.call_async("second", 2), [])
        self.assertEqual(
            await self.signal.resume_async("second"), [("second", 2)])
        self.assertEqual(
            await self.signal.resume_async("first"), [("first", 1)])

    async def test_concurrent_calls_keep_separate_frames(self):
        both_started = asyncio.Event()
        started = 0

        async def defer(sender, value):
            nonlocal started
            started += 1
            if started == 2:
                both_started.set()
            await both_started.wait()
            raise signal.SignalDefer

        def capture(sender, value):
            return value

        self.signal.add(defer)
        self.signal.add(capture)

        results = await asyncio.gather(
            self.signal.call_async("same sender", 1),
            self.signal.call_async("same sender", 2),
        )

        self.assertEqual(results, [[], []])
        self.assertTrue(all(
            result.status is signal.SignalStatus.STATUS_DEFER
            for result in results
        ))
        self.assertEqual(self.signal.pending_deferrals, 2)
        resumed = {
            (await self.signal.resume_async("same sender"))[0],
            (await self.signal.resume_async("same sender"))[0],
        }
        self.assertEqual(resumed, {1, 2})

    async def test_cancelled_resume_preserves_deferred_frame(self):
        waiting = asyncio.Event()

        def defer(sender):
            raise signal.SignalDefer

        async def wait(sender):
            waiting.set()
            await asyncio.Event().wait()

        self.signal.add(defer)
        self.signal.add(wait)
        self.signal.call("sender")

        task = asyncio.create_task(self.signal.resume_async("sender"))
        await waiting.wait()
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task

        self.assertTrue(self.signal.is_deferred)
        self.signal.reset_defers()


if __name__ == '__main__':
    unittest.main()

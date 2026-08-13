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


if __name__ == '__main__':
    unittest.main()

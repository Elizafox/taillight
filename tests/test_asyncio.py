import unittest
from taillight import signal

try:
    import asyncio
except ImportError:
    asyncio = None


def tearDownModule():
    if asyncio is not None:
        loop = asyncio.get_event_loop()
        loop.stop()
        loop.close()


x = 0
y = 0
z = 0


if asyncio is not None:
    @asyncio.coroutine
    def coroutine_1(sender):
        global x
        x += 1


    def function_1(sender):
        global y
        y += 1


    @asyncio.coroutine
    def coroutine_2(sender):
        global z
        yield from asyncio.sleep(0.01)
        z += 1


@unittest.skipIf(asyncio is None, "asyncio not found")
class TestCallSlot(unittest.TestCase):

    def setUp(self):
        self.signal = signal.Signal()
        self.loop = asyncio.get_event_loop()

    def tearDown(self):
        global x, y, z
        x = y = z = 0

    def test_call_wrapped(self):
        global x
        slot = self.signal.add(coroutine_1)

        self.loop.run_until_complete(self.signal.call_async("x"))

        self.assertEqual(x, 1)

    def test_call_function(self):
        global x
        slot = self.signal.add(function_1)

        self.loop.run_until_complete(self.signal.call_async("y"))

        self.assertEqual(y, 1)

    def test_call_yield_from(self):
        global z
        slot = self.signal.add(coroutine_2)

        self.loop.run_until_complete(self.signal.call_async("z"))

        self.assertEqual(z, 1)

    def test_combine(self):
        global x, y, z
        slot = [self.signal.add(function_1), self.signal.add(coroutine_1),
                self.signal.add(coroutine_2)]

        self.loop.run_until_complete(self.signal.call_async("xyz"))

        self.assertEqual(x, 1)
        self.assertEqual(y, 1)
        self.assertEqual(z, 1)


if __name__ == '__main__':
    unittest.main()

import unittest
from taillight import signal

x = 0


def test_func(sender):
    global x
    x += 1
    return x


y = 0


def test_func2(sender):
    global y
    y += 1
    return y


def test_defer1(sender):
    raise signal.SignalDefer()


def test_stop1(sender):
    raise signal.SignalStop()


class TestCallSlot(unittest.TestCase):

    def setUp(self):
        self.signal = signal.Signal()

    def tearDown(self):
        global x, y
        x = y = 0

    def test_call_listener(self):
        global x, y
        self.signal.add(test_func, listener="x")
        self.signal.add(test_func2, listener="y")

        self.signal.call("x")
        self.assertEqual(x, 1)
        self.assertEqual(y, 0)

        self.signal.call("y")
        self.assertEqual(x, 1)
        self.assertEqual(y, 1)

    def test_call_any(self):
        global x, y
        slot1 = self.signal.add(test_func, listener="x")
        slot2 = self.signal.add(test_func2, listener="y")

        self.signal.call(signal.ANY)
        self.assertEqual(self.signal.last_status, signal.Signal.STATUS_DONE)
        self.assertEqual(x, 1)
        self.assertEqual(y, 1)

        # These should work without raising
        self.signal.delete(slot1)
        self.signal.delete(slot2)

    def test_defer(self):
        global x, y
        slot1 = self.signal.add(test_func)
        slot2 = self.signal.add(test_func2,
                                priority=self.signal.priority_higher(slot1))
        slot3 = self.signal.add(test_defer1,
                                priority=self.signal.priority_higher(slot2))

        self.signal.call(signal.ANY)

        # Deferral point set
        self.assertIsNotNone(self.signal._defer)
        self.assertEqual(self.signal.last_status, signal.Signal.STATUS_DEFER)
        self.assertEqual(x, 0)
        self.assertEqual(y, 0)

        # Resume
        self.signal.call(signal.ANY)

        # Should have completed the chain
        self.assertIsNone(self.signal._defer)
        self.assertEqual(self.signal.last_status, signal.Signal.STATUS_DONE)
        self.assertEqual(x, 1)
        self.assertEqual(y, 1)

    def test_stop(self):
        global x, y
        slot1 = self.signal.add(test_func)
        slot2 = self.signal.add(test_func2,
                                priority=self.signal.priority_higher(slot1))
        slot3 = self.signal.add(test_stop1,
                                priority=self.signal.priority_higher(slot2))

        self.signal.call(signal.ANY)

        # Deferral point should NOT be set
        self.assertIsNone(self.signal._defer)
        self.assertEqual(self.signal.last_status, signal.Signal.STATUS_STOP)
        self.assertEqual(x, 0)
        self.assertEqual(y, 0)

    def test_defer_ensure_raises(self):
        slot1 = self.signal.add(test_func)
        slot2 = self.signal.add(test_func2,
                                priority=self.signal.priority_higher(slot1))
        slot3 = self.signal.add(test_defer1,
                                priority=self.signal.priority_higher(slot2))

        self.signal.call(signal.ANY)

        with self.assertRaises(signal.SignalDeferralSetError):
            self.signal.delete(slot1)

        with self.assertRaises(signal.SignalDeferralSetError):
            self.signal.add(lambda x: None)

        self.signal.reset_defer()

        # These should work now
        self.signal.delete(slot1)
        self.signal.delete(slot2)
        self.signal.delete(slot3)


if __name__ == '__main__':
    unittest.main()

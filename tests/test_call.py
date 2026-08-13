import unittest
from threading import Event, Thread

from taillight import signal

x = 0
y = 0


def test_func(sender, arg=None):
    global x
    x += 1
    return x


def test_func2(sender, arg=None):
    global y
    y += 1
    return y


def test_defer(sender, arg=None):
    raise signal.SignalDefer()


def test_stop(sender, arg=None):
    raise signal.SignalStop()


number = 0
fox = None


def test_defer_args1(sender, arg, noise):
    global number
    number = arg
    raise signal.SignalDefer()


def test_defer_args2(sender, arg, noise):
    global fox
    fox = noise


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
        self.assertEqual(self.signal.last_status,
                         signal.SignalStatus.STATUS_DONE)
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
        self.signal.add(test_defer,
                                priority=self.signal.priority_higher(slot2))

        self.signal.call(signal.ANY)

        # Deferral point set
        self.assertTrue(self.signal.is_deferred)
        self.assertEqual(self.signal.pending_deferrals, 1)
        self.assertEqual(self.signal.last_status,
                         signal.SignalStatus.STATUS_DEFER)
        self.assertEqual(x, 0)
        self.assertEqual(y, 0)

        # Resume
        self.signal.resume(signal.ANY)

        # Should have completed the chain
        self.assertFalse(self.signal.is_deferred)
        self.assertEqual(self.signal.last_status,
                         signal.SignalStatus.STATUS_DONE)
        self.assertEqual(x, 1)
        self.assertEqual(y, 1)

    def test_defer_arg_save(self):
        global number, fox
        slot1 = self.signal.add(test_defer_args2)
        self.signal.add(test_defer_args1,
                                priority=self.signal.priority_higher(slot1))

        self.signal.call(signal.ANY, 123, 'arf')

        # Should be deferred..
        self.assertTrue(self.signal.is_deferred)

        # but the first var should be set properly...
        self.assertEqual(number, 123)

        # and the other var should still be untouched...
        self.assertIsNone(fox)

        # now resume...
        self.signal.resume(signal.ANY)

        # and ensure the other method set the other var
        self.assertEqual(fox, 'arf')

    def test_stop(self):
        global x, y
        slot1 = self.signal.add(test_func)
        slot2 = self.signal.add(test_func2,
                                priority=self.signal.priority_higher(slot1))
        self.signal.add(test_stop,
                                priority=self.signal.priority_higher(slot2))

        self.signal.call(signal.ANY)

        # Deferral point should NOT be set
        self.assertFalse(self.signal.is_deferred)
        self.assertEqual(self.signal.last_status,
                         signal.SignalStatus.STATUS_STOP)
        self.assertEqual(x, 0)
        self.assertEqual(y, 0)

    def test_result_carries_invocation_status(self):
        self.signal.add(test_defer)

        result = self.signal.call("sender")

        self.assertIsInstance(result, signal.SignalResult)
        self.assertEqual(result.status, signal.SignalStatus.STATUS_DEFER)

    def test_active_call_uses_slot_snapshot(self):
        entered = Event()
        release = Event()

        def wait(sender):
            entered.set()
            release.wait(timeout=2)
            return "original"

        self.signal.add(wait)
        results = []
        thread = Thread(target=lambda: results.extend(self.signal.call("sender")))
        thread.start()
        self.assertTrue(entered.wait(timeout=2))

        self.signal.add(lambda sender: "new")
        release.set()
        thread.join(timeout=2)

        self.assertFalse(thread.is_alive())
        self.assertEqual(results, ["original"])
        self.assertEqual(self.signal.call("sender"), ["original", "new"])

    def test_defer_ensure_raises(self):
        slot1 = self.signal.add(test_func)
        slot2 = self.signal.add(test_func2,
                                priority=self.signal.priority_higher(slot1))
        slot3 = self.signal.add(test_defer,
                                priority=self.signal.priority_higher(slot2))

        self.signal.call(signal.ANY)

        with self.assertRaises(signal.SignalDeferralSetError):
            self.signal.delete(slot1)

        with self.assertRaises(signal.SignalDeferralSetError):
            self.signal.add(lambda x: None)

        with self.assertRaises(signal.SignalDeferralSetError):
            self.signal.clear()

        self.signal.reset_defer()

        # These should work now
        self.signal.delete(slot1)
        self.signal.delete(slot2)
        self.signal.delete(slot3)

    def test_defer_args_preserved(self):
        def capture(sender, arg=None):
            return arg

        capture_slot = self.signal.add(capture)
        self.signal.add(
            test_defer, priority=self.signal.priority_higher(capture_slot))

        self.signal.call(signal.ANY, arg="test")
        self.assertEqual(self.signal.resume(), ["test"])

    def test_defer_args_modify(self):
        def capture(sender, arg=None):
            return arg

        capture_slot = self.signal.add(capture)
        self.signal.add(
            test_defer, priority=self.signal.priority_higher(capture_slot))

        self.signal.call(signal.ANY, arg="test")
        self.signal.defer_set_args(kwargs={"arg": "newtest"})
        self.assertEqual(self.signal.resume(), ["newtest"])

    def test_multiple_deferrals_resume_in_lifo_order(self):
        def defer(sender, value):
            raise signal.SignalDefer

        def capture(sender, value):
            return sender, value

        self.signal.add(defer)
        self.signal.add(capture)

        self.assertEqual(self.signal.call("first", 1), [])
        self.assertEqual(self.signal.call("second", 2), [])
        with self.assertRaises(signal.SignalDeferralSenderError):
            self.signal.resume("first")

        self.assertEqual(self.signal.resume("second"), [("second", 2)])
        self.assertEqual(self.signal.resume("first"), [("first", 1)])
        self.assertIsNone(self.signal.resume("first"))

    def test_reset_defer_discards_only_top_frame(self):
        self.signal.add(lambda sender: (_ for _ in ()).throw(signal.SignalDefer))

        self.signal.call("first")
        self.signal.call("second")
        self.signal.reset_defer()

        self.assertEqual(self.signal.pending_deferrals, 1)
        self.assertEqual(self.signal.resume("first"), [])
        self.assertFalse(self.signal.is_deferred)

    def test_reset_defers_discards_every_frame(self):
        self.signal.add(lambda sender: (_ for _ in ()).throw(signal.SignalDefer))

        self.signal.call("first")
        self.signal.call("second")
        self.signal.reset_defers()

        self.assertEqual(self.signal.pending_deferrals, 0)

    def test_resume_exception_preserves_frame(self):
        def defer(sender):
            raise signal.SignalDefer

        def fail(sender):
            raise RuntimeError("failed")

        self.signal.add(defer)
        self.signal.add(fail)
        self.signal.call("sender")

        with self.assertRaises(RuntimeError):
            self.signal.resume()

        self.assertEqual(self.signal.pending_deferrals, 1)

    def test_callback_exception_propagates(self):
        error = RuntimeError("callback failed")

        def fail(sender):
            raise error

        self.signal.add(fail)

        with self.assertRaises(RuntimeError) as raised:
            self.signal.call("sender")

        self.assertIs(raised.exception, error)
        self.assertFalse(self.signal.is_deferred)

    def test_nested_invocation_has_independent_result(self):
        nested = False

        def callback(sender):
            nonlocal nested
            if not nested:
                nested = True
                return self.signal.call("inner")[0]
            return sender

        self.signal.add(callback)

        self.assertEqual(self.signal.call("outer"), ["inner"])

    def test_connection_conveniences(self):
        slot = self.signal.connect(lambda sender: sender)
        self.assertEqual(self.signal.emit("connected"), ["connected"])
        slot.disconnect()
        self.assertEqual(self.signal.emit("disconnected"), [])

        with self.signal.connection(lambda sender: sender) as temporary:
            self.assertIn(temporary, self.signal)
            self.assertEqual(self.signal.emit("temporary"), ["temporary"])

        self.assertNotIn(temporary, self.signal)

    def test_call_result_is_immutable(self):
        result = self.signal.call("sender")

        with self.assertRaises((AttributeError, TypeError)):
            result.status = signal.SignalStatus.STATUS_STOP


if __name__ == '__main__':
    unittest.main()

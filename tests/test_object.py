import unittest
from taillight import signal


class TestSignalObject(unittest.TestCase):

    def test_singleton(self):
        signal_a = signal.Signal("a")
        signal_b = signal.Signal("b")
        signal_a2 = signal.Signal("a")
        signal_b2 = signal.Signal("b")

        self.assertIs(signal_a, signal_a2)
        self.assertIs(signal_b, signal_b2)
        self.assertIsNot(signal_a, signal_b)

    def test_singleton_add(self):
        signal_a = signal.Signal("a")

        function1 = lambda x: None
        function2 = lambda y: None

        signal_a.add(function1)
        signal_a.add(function2)

        signal_a_slots = signal_a.slots

        # This shouldn't wipe out the previous functions
        signal_a2 = signal.Signal("a")

        self.assertListEqual(signal_a_slots, signal_a2.slots)
        self.assertListEqual(signal_a.slots, signal_a2.slots)  # Subtle!

    def test_unshared(self):
        signal_a = signal.UnsharedSignal("a")
        signal_b = signal.UnsharedSignal("b")
        signal_a2 = signal.UnsharedSignal("a")
        signal_b2 = signal.UnsharedSignal("b")

        self.assertIsNot(signal_a, signal_a2)
        self.assertIsNot(signal_b, signal_b2)
        self.assertIsNot(signal_a, signal_b)

    def test_strong(self):
        signal_a = signal.StrongSignal("a")
        signal_a.add(lambda x: None)

        # Remove last strong reference
        del signal_a

        # Signal should remain
        signal_a = signal.StrongSignal("a")
        self.assertEqual(len(signal_a), 1)

        # Try a deletion; slot should be gone
        signal_a.delete_signal("a")
        self.assertEqual(len(signal_a), 0)

        # Clean up
        signal_a.delete_signal("a")

    def test_anonymous_signal(self):
        signal_anon1 = signal.Signal()
        signal_anon2 = signal.Signal()

        self.assertIsNot(signal_anon1, signal_anon2)

    def test_anonymous_unshared_signal(self):
        signal_anon1 = signal.UnsharedSignal()
        signal_anon2 = signal.UnsharedSignal()

        self.assertIsNot(signal_anon1, signal_anon2)


if __name__ == '__main__':
    unittest.main()

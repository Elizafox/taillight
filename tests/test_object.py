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

    def test_unshared(self):
        signal_a = signal.UnsharedSignal("a")
        signal_b = signal.UnsharedSignal("b")
        signal_a2 = signal.UnsharedSignal("a")
        signal_b2 = signal.UnsharedSignal("b")

        self.assertIsNot(signal_a, signal_a2)
        self.assertIsNot(signal_b, signal_b2)
        self.assertIsNot(signal_a, signal_b)

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

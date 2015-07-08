import unittest
from taillight import signal


class TestSignalObject(unittest.TestCase):

    def test_singleton(self):
        signal_a = signal.Signal("a")
        signal_b = signal.Signal("b")
        signal_a2 = signal.Signal("a")
        signal_b2 = signal.Signal("b")

        self.assertIs(signal_a, signal_a2)

    def test_anonymous(self):
        signal_anon1 = signal.Signal()
        signal_anon2 = signal.Signal()

        self.assertIsNot(signal_anon1, signal_anon2)


if __name__ == '__main__':
    unittest.main()

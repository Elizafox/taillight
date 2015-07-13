import unittest
from taillight import signal


class TestAddSlot(unittest.TestCase):

    def setUp(self):
        self.signal = signal.Signal()

    def test_add(self):
        function1 = lambda x: None
        function2 = lambda y: None

        slot1 = self.signal.add(function1)
        slot2 = self.signal.add(function2)

        self.assertListEqual(self.signal.slots, [slot1, slot2])

    def test_add_decorate(self):
        function1 = lambda x: None
        function2 = lambda y: None

        # Equivalent to using the decorator
        slot1 = self.signal.add_wraps()(function1)
        slot2 = self.signal.add_wraps()(function2)

        self.assertListEqual(self.signal.slots, [slot1, slot2])


if __name__ == '__main__':
    unittest.main()

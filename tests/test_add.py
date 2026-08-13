import unittest

from taillight import signal


class TestAddSlot(unittest.TestCase):

    def setUp(self):
        self.signal = signal.Signal()

    def test_add(self):
        def function1(x):
            return None
        def function2(y):
            return None

        slot1 = self.signal.add(function1)
        slot2 = self.signal.add(function2)

        self.assertSequenceEqual(self.signal.slots,
                                 signal._SlotType((slot1, slot2)),
                                 signal._SlotType)

    def test_add_decorate(self):
        def function1(x):
            return None
        def function2(y):
            return None

        # Equivalent to using the decorator
        slot1 = self.signal.add_wraps()(function1)
        slot2 = self.signal.add_wraps()(function2)

        self.assertSequenceEqual(self.signal.slots,
                                 signal._SlotType((slot1, slot2)),
                                 signal._SlotType)


if __name__ == '__main__':
    unittest.main()

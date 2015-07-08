import unittest
from taillight import signal
from taillight.slot import SlotNotFoundError

class TestDeleteSlot(unittest.TestCase):

    def setUp(self):
        self.signal = signal.Signal()

    def test_delete(self):
        function = lambda x: None
        function2 = lambda y: None

        slot = self.signal.add(function)
        slot2 = self.signal.add(function2)

        self.signal.delete(slot)
        self.assertNotIn(slot, self.signal)

        with self.assertRaises(SlotNotFoundError):
            self.signal.find_function(function)

        with self.assertRaises(SlotNotFoundError):
            self.signal.find_uid(slot.uid)

        self.assertIsNotNone(self.signal.find_uid(slot2.uid))

        self.signal.delete_uid(slot2.uid)
        self.assertNotIn(slot2, self.signal)

        with self.assertRaises(SlotNotFoundError):
            self.signal.find_function(function2)

        with self.assertRaises(SlotNotFoundError):
            self.signal.find_uid(slot2.uid)

if __name__ == '__main__':
    unittest.main()

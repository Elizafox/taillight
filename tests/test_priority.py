import unittest
from taillight import signal


class TestPriority(unittest.TestCase):

    def setUp(self):
        self.signal_a = signal.Signal(prio_descend=False)
        self.signal_d = signal.Signal()

    def test_higher_ascend(self):
        slot = self.signal_a.add(lambda x: None)
        # Higher priority values are higher priority
        self.assertGreater(self.signal_a.priority_higher(slot), slot.priority)

    def test_higher_descend(self):
        slot = self.signal_d.add(lambda x: None)
        # Lower priority values are higher priority
        self.assertLess(self.signal_d.priority_higher(slot), slot.priority)

    def test_lower_ascend(self):
        slot = self.signal_a.add(lambda x: None)
        # Lower priority values are lower priority
        self.assertLess(self.signal_a.priority_lower(slot), slot.priority)

    def test_lower_descend(self):
        slot = self.signal_d.add(lambda x: None)
        # Higher priority values are lower priority
        self.assertGreater(self.signal_d.priority_lower(slot), slot.priority)

    def test_priority_call_ascend(self):
        slot1 = self.signal_a.add(lambda x: 2)
        slot2 = self.signal_a.add(lambda x: 1,
                priority=self.signal_a.priority_higher(slot1))
        slot3 = self.signal_a.add(lambda x: 0,
                priority=self.signal_a.priority_higher(slot2))
        result = self.signal_a.call(self)
        self.assertListEqual(result, [0, 1, 2])

    def test_priority_call_descend(self):
        slot1 = self.signal_d.add(lambda x: 2)
        slot2 = self.signal_d.add(lambda x: 1,
                priority=self.signal_d.priority_higher(slot1))
        slot3 = self.signal_d.add(lambda x: 0,
                priority=self.signal_d.priority_higher(slot2))
        result = self.signal_d.call(self)
        self.assertListEqual(result, [0, 1, 2])


if __name__ == '__main__':
    unittest.main()

import unittest

from taillight import signal


class TestPriority(unittest.TestCase):

    def setUp(self):
        self.signal_ascending = signal.Signal(
            priority_order=signal.PriorityOrder.ASCENDING)
        self.signal_descending = signal.Signal(
            priority_order=signal.PriorityOrder.DESCENDING)

    def test_higher_ascend(self):
        slot = self.signal_ascending.add(lambda x: None)
        self.assertLess(
            self.signal_ascending.priority_higher(slot), slot.priority)

    def test_higher_descend(self):
        slot = self.signal_descending.add(lambda x: None)
        self.assertGreater(
            self.signal_descending.priority_higher(slot), slot.priority)

    def test_lower_ascend(self):
        slot = self.signal_ascending.add(lambda x: None)
        self.assertGreater(
            self.signal_ascending.priority_lower(slot), slot.priority)

    def test_lower_descend(self):
        slot = self.signal_descending.add(lambda x: None)
        self.assertLess(
            self.signal_descending.priority_lower(slot), slot.priority)

    def test_priority_call_ascend(self):
        slot1 = self.signal_ascending.add(lambda x: 2)
        slot2 = self.signal_ascending.add(
            lambda x: 1,
            priority=self.signal_ascending.priority_higher(slot1),
        )
        self.signal_ascending.add(
            lambda x: 0,
            priority=self.signal_ascending.priority_higher(slot2),
        )
        result = self.signal_ascending.call(self)
        self.assertEqual(result, [0, 1, 2])

    def test_priority_call_descend(self):
        slot1 = self.signal_descending.add(lambda x: 2)
        slot2 = self.signal_descending.add(
            lambda x: 1,
            priority=self.signal_descending.priority_higher(slot1),
        )
        self.signal_descending.add(
            lambda x: 0,
            priority=self.signal_descending.priority_higher(slot2),
        )
        result = self.signal_descending.call(self)
        self.assertEqual(result, [0, 1, 2])

    def test_explicit_priority_order(self):
        ascending = signal.Signal(
            priority_order=signal.PriorityOrder.ASCENDING)
        descending = signal.Signal(
            priority_order=signal.PriorityOrder.DESCENDING)

        for current in (ascending, descending):
            current.add(lambda sender: 1, priority=1)
            current.add(lambda sender: 2, priority=2)

        self.assertEqual(ascending.call(self), [1, 2])
        self.assertEqual(descending.call(self), [2, 1])

    def test_conflicting_priority_options_raise(self):
        with self.assertRaises(ValueError):
            signal.Signal(
                prio_descend=True,
                priority_order=signal.PriorityOrder.DESCENDING,
            )

    def test_equal_priority_order_is_stable(self):
        for priority_order in signal.PriorityOrder:
            current = signal.Signal(priority_order=priority_order)
            current.add(lambda sender: "first", priority=1)
            current.add(lambda sender: "second", priority=1)

            self.assertEqual(current.call(self), ["first", "second"])


if __name__ == '__main__':
    unittest.main()

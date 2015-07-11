import unittest
from taillight import signal


class TestFindFunction(unittest.TestCase):

    def setUp(self):
        self.signal = signal.Signal()

    def test_uid(self):
        sig = signal.Signal()

        function = lambda x: None
        slot = self.signal.add(function)
        slot2 = self.signal.add(function)

        result = self.signal.find_uid(0)
        self.assertIsNotNone(result)
        self.assertIs(result, slot)

        result = self.signal.find_uid(1)
        self.assertIsNotNone(result)
        self.assertIs(result, slot2)

    def test_function(self):
        sig = signal.Signal()

        function = lambda x: None
        slot = self.signal.add(function)
        slot2 = self.signal.add(function)

        result = self.signal.find_function(function)
        self.assertIsNotNone(result)
        self.assertTrue(len(result) == 2)
        self.assertIn(slot, result)
        self.assertIn(slot2, result)


if __name__ == '__main__':
    unittest.main()

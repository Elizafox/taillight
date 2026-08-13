import unittest
from concurrent.futures import ThreadPoolExecutor
from gc import collect
from threading import Barrier
from weakref import ref

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

        def function1(x):
            return None
        def function2(y):
            return None

        signal_a.add(function1)
        signal_a.add(function2)

        signal_a_slots = signal_a.slots

        # This shouldn't wipe out the previous functions
        signal_a2 = signal.Signal("a")

        self.assertSequenceEqual(signal_a_slots, signal_a2.slots,
                                 signal._SlotType)

    def test_singleton_does_not_reuse_uids(self):
        signal_a = signal.Signal("uid")
        first = signal_a.add(lambda sender: None)

        signal_a2 = signal.Signal("uid")
        second = signal_a2.add(lambda sender: None)

        self.assertGreater(second.uid, first.uid)

    def test_singleton_keeps_priority_order(self):
        _signal_a = signal.Signal("priority", prio_descend=False)
        signal_a2 = signal.Signal("priority")

        self.assertFalse(signal_a2.prio_descend)

    def test_singleton_initializes_only_once(self):
        class CountingSignal(signal.Signal):
            initializations = 0

            def __init__(self, name=None, prio_descend=True):
                type(self).initializations += 1
                super().__init__(name, prio_descend)

        signal_a = CountingSignal("counted", prio_descend=False)
        signal_a2 = CountingSignal("counted")

        self.assertIs(signal_a, signal_a2)
        self.assertEqual(CountingSignal.initializations, 1)
        self.assertFalse(signal_a2.prio_descend)

    def test_subclasses_have_isolated_named_caches(self):
        class CustomSignal(signal.Signal):
            pass

        base = signal.Signal("shared name")
        custom = CustomSignal("shared name")

        self.assertIsNot(base, custom)
        self.assertIs(custom, CustomSignal("shared name"))

    def test_concurrent_construction_initializes_once(self):
        class CountingSignal(signal.Signal):
            initializations = 0

            def __init__(self, name=None, prio_descend=True):
                type(self).initializations += 1
                super().__init__(name, prio_descend)

        barrier = Barrier(8)

        def construct(_):
            barrier.wait()
            return CountingSignal("concurrent")

        with ThreadPoolExecutor(max_workers=8) as executor:
            instances = list(executor.map(construct, range(8)))

        self.assertTrue(all(instance is instances[0] for instance in instances))
        self.assertEqual(CountingSignal.initializations, 1)

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

        # Try a deletion; signal should be gone from cache
        signal.StrongSignal.delete_signal("a")
        signal_a = signal.StrongSignal("a")  # New instance
        self.assertEqual(len(signal_a), 0)

        # Clean up
        signal_a.delete_signal("a")

    def test_strong_subclasses_have_isolated_strong_caches(self):
        class CustomStrongSignal(signal.StrongSignal):
            pass

        custom = CustomStrongSignal("custom strong")
        custom.add(lambda sender: None)
        del custom

        self.assertEqual(len(CustomStrongSignal("custom strong")), 1)
        self.assertEqual(len(signal.StrongSignal("custom strong")), 0)
        CustomStrongSignal.delete_signal("custom strong")
        signal.StrongSignal.delete_signal("custom strong")

    def test_strong_deletion_is_synchronised_with_construction(self):
        name = "concurrent strong"
        original = signal.StrongSignal(name)
        barrier = Barrier(2)

        def construct():
            barrier.wait()
            return signal.StrongSignal(name)

        def delete():
            barrier.wait()
            signal.StrongSignal.delete_signal(name)

        with ThreadPoolExecutor(max_workers=2) as executor:
            constructed = executor.submit(construct)
            deleted = executor.submit(delete)
            constructed.result()
            deleted.result()

        current = signal.StrongSignal(name)
        self.assertIs(current, signal.StrongSignal(name))
        self.assertIn(constructed.result(), (original, current))
        signal.StrongSignal.delete_signal(name)

    def test_delete_missing_strong_signal(self):
        with self.assertRaises(signal.SignalNotFoundError):
            signal.StrongSignal.delete_signal("missing")

    def test_anonymous_signal(self):
        signal_anon1 = signal.Signal()
        signal_anon2 = signal.Signal()

        self.assertIsNot(signal_anon1, signal_anon2)

    def test_anonymous_unshared_signal(self):
        signal_anon1 = signal.UnsharedSignal()
        signal_anon2 = signal.UnsharedSignal()

        self.assertIsNot(signal_anon1, signal_anon2)

    def test_weak_cache_releases_unreferenced_signal(self):
        cached = signal.Signal("collectable")
        weak = ref(cached)
        del cached
        collect()

        self.assertIsNone(weak())


if __name__ == '__main__':
    unittest.main()

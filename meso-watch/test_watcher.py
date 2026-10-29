import unittest

import watcher
from watcher import Listing, connect, find_deals


class FindDealsTest(unittest.TestCase):
    def setUp(self):
        self.db = connect(":memory:")
        watcher.MIN_LISTINGS, watcher.DISCOUNT = 5, 0.30
        # build up history: 6 normal listings around 100m
        for i, p in enumerate([95, 100, 100, 105, 110, 98]):
            find_deals(self.db, [Listing(f"h{i}", "Arcane Weapon", p * 10**6)], now=1000 + i)

    def test_flags_cheap_popular_item(self):
        deals = find_deals(self.db, [Listing("x", "Arcane Weapon", 60 * 10**6)], now=2000)
        self.assertEqual([d[0].listing_id for d in deals], ["x"])

    def test_ignores_small_discount(self):
        self.assertEqual(find_deals(self.db, [Listing("x", "Arcane Weapon", 80 * 10**6)], now=2000), [])

    def test_ignores_unpopular_item(self):
        self.assertEqual(find_deals(self.db, [Listing("x", "Rare Hat", 1)], now=2000), [])

    def test_alerts_once_per_listing(self):
        cheap = [Listing("x", "Arcane Weapon", 60 * 10**6)]
        self.assertEqual(len(find_deals(self.db, cheap, now=2000)), 1)
        self.assertEqual(find_deals(self.db, cheap, now=2300), [])

    def test_old_history_expires(self):
        far_future = 1000 + (watcher.LOOKBACK_DAYS + 1) * 86400
        self.assertEqual(find_deals(self.db, [Listing("x", "Arcane Weapon", 1)], now=far_future), [])


if __name__ == "__main__":
    unittest.main()

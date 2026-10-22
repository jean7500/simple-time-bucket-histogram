import math
import unittest

from simple_time_bucket_histogram import TimeBucketHistogram, Bucket


class TestBucketBoundary(unittest.TestCase):
    def test_half_open_interval_boundary(self):
        # Decision stated in README: buckets are half-open [start, end).
        # A timestamp exactly on a boundary belongs to the bucket starting
        # at that boundary.
        h = TimeBucketHistogram(width=10)
        h.add(10)
        self.assertEqual(list(h.buckets()), [Bucket(start=10.0, end=20.0, count=1)])


class TestAdd(unittest.TestCase):
    def test_add_returns_new_count(self):
        h = TimeBucketHistogram(width=5)
        self.assertEqual(h.add(3), 1)
        self.assertEqual(h.add(4), 2)

    def test_add_within_same_bucket(self):
        h = TimeBucketHistogram(width=10)
        h.add(0)
        h.add(5)
        h.add(9)
        self.assertEqual(list(h.buckets()), [Bucket(0.0, 10.0, 3)])

    def test_add_into_distinct_buckets(self):
        h = TimeBucketHistogram(width=10)
        h.add(0)
        h.add(10)
        h.add(20)
        self.assertEqual(
            list(h.buckets()),
            [Bucket(0.0, 10.0, 1), Bucket(10.0, 20.0, 1), Bucket(20.0, 30.0, 1)],
        )


class TestCounts(unittest.TestCase):
    def test_counts_shape(self):
        h = TimeBucketHistogram(width=10)
        h.add(0)
        h.add(0)
        h.add(15)
        self.assertEqual(h.counts(), [((0.0, 10.0), 2), ((10.0, 20.0), 1)])


class TestBucketsEmpty(unittest.TestCase):
    def test_empty_histogram_yields_nothing(self):
        h = TimeBucketHistogram(width=10)
        self.assertEqual(list(h.buckets()), [])
        self.assertEqual(list(h.buckets(include_empty=True), ), [])

    def test_empty_histogram_counts(self):
        h = TimeBucketHistogram(width=10)
        self.assertEqual(h.counts(), [])


class TestBucketsIncludeEmpty(unittest.TestCase):
    def test_fills_gaps_contiguously(self):
        h = TimeBucketHistogram(width=10)
        h.add(0)
        h.add(25)
        result = list(h.buckets(include_empty=True))
        self.assertEqual(
            result,
            [
                Bucket(0.0, 10.0, 1),
                Bucket(10.0, 20.0, 0),
                Bucket(20.0, 30.0, 1),
            ],
        )

    def test_include_empty_single_bucket(self):
        h = TimeBucketHistogram(width=10)
        h.add(5)
        self.assertEqual(
            list(h.buckets(include_empty=True)), [Bucket(0.0, 10.0, 1)]
        )


class TestFloor(unittest.TestCase):
    def test_nonzero_floor_aligns_buckets(self):
        # floor=100 shifts the bucket grid so 100 is a boundary.
        h = TimeBucketHistogram(width=10, floor=100)
        h.add(100)
        h.add(109)
        self.assertEqual(list(h.buckets()), [Bucket(100.0, 110.0, 2)])

    def test_floor_negative_supported(self):
        # Negative floor is valid — it just shifts the grid. The floor /
        # width normalization in the constructor handles this without
        # special-casing. With floor=-5 and width=10, the bucket grid is
        # aligned to multiples of 10 starting from -5, so -5 lands in the
        # bucket [-10, 0) along with other values in that range.
        h = TimeBucketHistogram(width=10, floor=-5)
        h.add(-5)
        self.assertEqual(list(h.buckets()), [Bucket(-10.0, 0.0, 1)])


class TestNow(unittest.TestCase):
    def test_now_uses_injected_clock(self):
        # Deterministic: we pass a fake clock; no wall-clock dependence.
        ticks = [42.0]
        h = TimeBucketHistogram(width=10, clock=lambda: ticks[0])
        self.assertEqual(h.now(), 1)
        self.assertEqual(list(h.buckets()), [Bucket(40.0, 50.0, 1)])

    def test_now_without_clock_raises(self):
        h = TimeBucketHistogram(width=10)
        with self.assertRaises(TypeError):
            h.now()


class TestInvalidInputs(unittest.TestCase):
    def test_zero_width_rejected(self):
        with self.assertRaises(ValueError):
            TimeBucketHistogram(width=0)

    def test_negative_width_rejected(self):
        with self.assertRaises(ValueError):
            TimeBucketHistogram(width=-1)

    def test_nan_timestamp_rejected(self):
        h = TimeBucketHistogram(width=10)
        with self.assertRaises(ValueError):
            h.add(float("nan"))

    def test_infinity_rejected(self):
        h = TimeBucketHistogram(width=10)
        with self.assertRaises(ValueError):
            h.add(float("inf"))

    def test_non_callable_clock_rejected(self):
        with self.assertRaises(TypeError):
            TimeBucketHistogram(width=10, clock=123)


class TestReset(unittest.TestCase):
    def test_reset_clears_buckets(self):
        h = TimeBucketHistogram(width=10)
        h.add(0)
        h.add(10)
        h.reset()
        self.assertEqual(list(h.buckets()), [])
        # Still usable afterwards.
        h.add(0)
        self.assertEqual(list(h.buckets()), [Bucket(0.0, 10.0, 1)])


class TestOrdering(unittest.TestCase):
    def test_buckets_sorted_chronologically(self):
        h = TimeBucketHistogram(width=10)
        # Deliberately add out of order.
        h.add(30)
        h.add(0)
        h.add(20)
        h.add(10)
        starts = [b.start for b in h.buckets()]
        self.assertEqual(starts, [0.0, 10.0, 20.0, 30.0])


class TestNegativeTimestamps(unittest.TestCase):
    def test_pre_epoch_timestamps_supported(self):
        # Negative timestamps (before Unix epoch) must produce correct
        # bucket indices. The floor division used in _bucket_index handles
        # this naturally; the test pins the behaviour so it stays that way.
        h = TimeBucketHistogram(width=10)
        h.add(-5)
        h.add(-1)
        self.assertEqual(list(h.buckets()), [Bucket(-10.0, 0.0, 2)])


class TestProperties(unittest.TestCase):
    def test_width_and_floor_exposed(self):
        h = TimeBucketHistogram(width=7, floor=100)
        self.assertEqual(h.width, 7.0)
        self.assertEqual(h.floor, 100.0)


if __name__ == "__main__":
    unittest.main()

"""Core implementation for time-bucket histograms."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Iterator, List, Optional, Tuple


@dataclass(frozen=True)
class Bucket:
    """A single histogram bucket.

    Attributes:
        start: The inclusive lower-bound POSIX timestamp of this bucket
            (i.e. the floor of any timestamp that maps here).
        end:   The exclusive upper-bound POSIX timestamp (start + width).
        count: How many timestamps fell into this bucket's half-open range.

    `Bucket` is frozen so callers can safely keep references to buckets they
    observed without later discovering a mutation. Equality is structural,
    which makes the unit-test comparisons read naturally.
    """

    start: float
    end: float
    count: int


class TimeBucketHistogram:
    """Groups timestamped events into fixed-width chronological buckets.

    The histogram does not retain the raw timestamps; it only retains the
    per-bucket count. This is the trade-off that lets us run indefinitely
    without unbounded memory growth — detail is discarded the moment an
    event is added.

    Interpretation decision (stated plainly so there is no ambiguity):
    Buckets are half-open intervals [start, end). A timestamp exactly on a
    bucket boundary belongs to the bucket starting at that boundary. The
    reference epoch for `floor=0` is the Unix epoch (1970-01-01T00:00:00Z).
    All timestamps are treated as plain numbers; no timezone interpretation
    is performed.
    """

    def __init__(
        self,
        width: float,
        clock: Optional[Callable[[], float]] = None,
        floor: float = 0.0,
    ) -> None:
        if width <= 0:
            raise ValueError("width must be strictly positive")
        if not isinstance(width, (int, float)):
            raise TypeError("width must be a number")
        if not isinstance(floor, (int, float)):
            raise TypeError("floor must be a number")
        if clock is not None and not callable(clock):
            raise TypeError("clock must be callable or None")
        self._width: float = float(width)
        self._floor: float = float(floor)
        self._buckets: Dict[int, int] = {}
        # Normalize the floor so the reference bucket index is exactly 0.
        self._floor_index = int(self._floor // self._width)
        # `clock` is used only by now(), not by add(). That means tests can
        # deterministically exercise now() by passing a fake clock.
        self._clock = clock

    @property
    def width(self) -> float:
        return self._width

    @property
    def floor(self) -> float:
        return self._floor

    def _bucket_index(self, ts: float) -> int:
        """Return the integer bucket index for a timestamp.

        Uses floor division on raw floats. Because `width` is strictly
        positive and finite and the floor offset is precomputed, the only
        risk of an unbounded result is when `ts` is not finite; that case is
        rejected at the add() boundary.
        """
        return int(ts // self._width) - self._floor_index

    def _bucket_bounds(self, idx: int) -> Tuple[float, float]:
        start = (idx + self._floor_index) * self._width
        return (start, start + self._width)

    def add(self, ts: float) -> int:
        """Record a single timestamp, returning the new bucket count.

        Raises ValueError if `ts` is not a finite number — NaN or infinity
        produce no consistent bucket index and would silently corrupt the
        histogram, so they are rejected rather than silently swallowed.
        """
        if not isinstance(ts, (int, float)):
            raise TypeError("ts must be a number")
        if ts != ts or ts in (float("inf"), float("-inf")):
            raise ValueError("ts must be finite")
        idx = self._bucket_index(float(ts))
        self._buckets[idx] = self._buckets.get(idx, 0) + 1
        return self._buckets[idx]

    def now(self) -> int:
        """Record an event at the current clock time.

        Requires `clock` to have been provided at construction; otherwise
        we'd be silently relying on wall-clock time, which makes tests
        non-deterministic. We raise explicitly rather than fall back to
        time.time() so the contract is obvious.
        """
        if self._clock is None:
            raise TypeError("now() requires a clock callable passed at construction")
        return self.add(float(self._clock()))

    def buckets(self, include_empty: bool = False) -> Iterator[Bucket]:
        """Yield populated buckets in chronological order.

        When `include_empty` is True, yield every bucket in the closed range
        [min_observed, max_observed] including empty buckets with count 0.
        This is useful for producing contiguous output such as a bar chart.
        """
        if not self._buckets:
            return
        if not include_empty:
            for idx in sorted(self._buckets):
                start, end = self._bucket_bounds(idx)
                yield Bucket(start=start, end=end, count=self._buckets[idx])
            return
        lo = min(self._buckets)
        hi = max(self._buckets)
        for idx in range(lo, hi + 1):
            start, end = self._bucket_bounds(idx)
            yield Bucket(start=start, end=end, count=self._buckets.get(idx, 0))

    def counts(self) -> List[Tuple[Tuple[float, float], int]]:
        """Return populated buckets as a list of ((start, end), count).

        Ordered by start ascending. Provided as a convenience for callers
        that prefer tuples over dataclasses.
        """
        return [
            ((b.start, b.end), b.count) for b in self.buckets(include_empty=False)
        ]

    def reset(self) -> None:
        """Clear all buckets."""
        self._buckets.clear()

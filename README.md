# simple-time-bucket-histogram

Groups timestamped events into fixed-size chronological buckets and reports counts per bucket.

```python
from simple_time_bucket_histogram import TimeBucketHistogram, Bucket

# width=10 means each bucket spans 10 time units.
h = TimeBucketHistogram(width=10)
h.add(0)
h.add(5)
h.add(10)
h.add(22)

for b in h.buckets():
    print(b.start, b.end, b.count)
# 0.0 10.0 2
# 10.0 20.0 1
# 20.0 30.0 1

print(h.counts())
# [((0.0, 10.0), 2), ((10.0, 20.0), 1), ((20.0, 30.0), 1)]
```

To record the current time, pass a `clock` callable at construction and call `now()`:

```python
h = TimeBucketHistogram(width=60, clock=lambda: some_clock_value)
h.now()
```

`now()` raises `TypeError` if no `clock` was provided. The library never silently falls back to wall-clock time; that would make any test using `now()` non-deterministic.

## Why

This exists for the case where you have a stream of timestamps and you only care about how many landed in each fixed-width slot, not which specific events produced them. By discarding the raw timestamps at insertion time, memory stays bounded by the number of *distinct buckets observed*, not the number of events. The trade-off is that you cannot later go back and ask which event was which — the counts are all that remain.

## Edges you will hit

Buckets are half-open intervals `[start, end)`. A timestamp landing exactly on a boundary belongs to the bucket whose `start` equals that timestamp, not the previous one. If you are feeding in values produced by a separate timer, align your `width` and `floor` to that timer's tick grid or you will see surprising bucket assignments.

Non-finite timestamps (`nan`, `inf`, `-inf`) are rejected by `add()` with `ValueError` rather than silently producing a corrupt index. The `floor` parameter shifts the bucket grid so that `floor` itself is a bucket boundary; the default `floor=0` uses the Unix epoch as the origin.

## Performance

The window keeps a bounded buffer, so `push` is constant time and memory does not
grow with the length of the stream. `peak` and `trough` are linear in the window
size, which is the trade that keeps `push` cheap.

## Limitations

Values are coerced to floats, so very large integers lose precision. If you need
exact integer aggregates over a window, this is the wrong tool.


"""Drain time of a resend (US-31, T-31.2): the summary used by scripts/measure_drain.py."""

from scripts.measure_drain import Sample, summarize


def samples(*depths):
    return [Sample(float(i), d) for i, d in enumerate(depths)]


def test_drain_goes_from_the_last_peak_sample_to_the_first_empty_one():
    drain = summarize(samples(0, 784, 784, 600, 300, 20, 0, 0))
    assert drain.peak == 784
    assert drain.seconds == 4.0  # from t=2 (last 784) to t=6 (first 0)
    assert round(drain.rate, 1) == 196.0


def test_no_drain_while_the_queue_still_has_messages():
    assert summarize(samples(784, 500, 10)) is None


def test_no_drain_if_the_queue_never_filled():
    assert summarize(samples(0, 0, 0)) is None
    assert summarize([]) is None

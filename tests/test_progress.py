"""The progress bar: a TTY redraws one line, a pipe writes one line per step."""

import io

from smart_insights.progress import BAR_WIDTH, Progress


class TtyBuffer(io.StringIO):
    """A StringIO that claims to be a terminal, so Progress redraws in place."""

    def isatty(self) -> bool:
        return True


def test_tty_redraws_a_single_line_and_fills_the_bar():
    stream = TtyBuffer()
    with Progress("insights", 2, stream) as progress:
        progress.start("row 1")
        progress.advance()
        progress.advance("row 2")

    output = stream.getvalue()
    assert output.count("\n") == 1  # only the newline that closes the bar
    frames = output.split("\r")[1:]  # the leading "" before the first redraw
    in_flight = frames[1]  # start(): announced, but no step done yet
    assert "insights [" + "-" * BAR_WIDTH + "] 0/2" in in_flight
    assert "row 1" in in_flight
    assert "insights [" + "#" * BAR_WIDTH + "] 2/2" in frames[-1]
    assert frames[-1].rstrip().endswith("row 2")  # rstrip: padding over the longer note


def test_non_tty_writes_one_line_per_completed_step():
    stream = io.StringIO()
    with Progress("evaluate", 2, stream) as progress:
        progress.start("row 1")  # in-flight renders are pointless in a log
        progress.advance()
        progress.advance("row 2")

    lines = stream.getvalue().splitlines()
    assert len(lines) == 2
    assert "\r" not in stream.getvalue()
    assert "evaluate" in lines[0] and "1/2" in lines[0] and "row 1" in lines[0]
    assert "2/2" in lines[1] and "row 2" in lines[1]


def test_log_prints_above_the_bar_and_redraws_it():
    stream = TtyBuffer()
    with Progress("pass B: enrich", 1, stream) as progress:
        progress.log("  row 3 edge_case_anomaly: tracking is not firing")
        progress.advance()

    # Split on "\n" only: splitlines() would also split the in-place redraws.
    logged, redrawn = stream.getvalue().split("\n")[:2]
    assert logged.endswith("  row 3 edge_case_anomaly: tracking is not firing")
    assert "1/1" in redrawn


def test_a_shorter_line_leaves_no_tail_of_the_longer_one():
    stream = TtyBuffer()
    with Progress("run", 2, stream) as progress:
        progress.advance("a note long enough to need overwriting")
        progress.advance("short")

    last_frame = stream.getvalue().split("\r")[-1]
    assert "overwriting" not in last_frame
    assert last_frame.startswith("run [")

"""Progress UX: a dependency-free bar, shared by every CLI command.

It writes to stderr because stdout is the data channel (the report tables, the
`wrote ...` lines): `run > out.txt` still shows a live bar, and the bar never
lands in the redirected file. Off a TTY the bar degrades to one plain line per
completed step — what a CI log wants — and in-flight renders are skipped, since
there is no line to overwrite.
"""

from __future__ import annotations

import sys
import time
from types import TracebackType
from typing import IO

BAR_WIDTH = 24
NOTE_WIDTH = 36


def status(message: str, stream: IO[str] | None = None) -> None:
    """A one-off progress line with no counter, on the bar's channel."""
    print(message, file=stream or sys.stderr, flush=True)


def _format_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.0f}s"
    whole_minutes, remaining_seconds = divmod(int(seconds), 60)
    return f"{whole_minutes}m{remaining_seconds:02d}s"


class Progress:
    """A determinate bar over `total` steps, used as a context manager.

    Call `start()` with the item about to be worked on — that is what keeps a
    slow LLM call from looking hung — and `advance()` once it is done. ASCII
    only: a cp1252 Windows console cannot encode block characters.
    """

    def __init__(self, label: str, total: int, stream: IO[str] | None = None) -> None:
        self._label = label
        self._total = total
        self._stream = stream if stream is not None else sys.stderr
        self._done = 0
        self._note = ""
        self._started = time.monotonic()
        self._line_length = 0
        self._is_tty = bool(getattr(self._stream, "isatty", lambda: False)())

    def __enter__(self) -> Progress:
        if self._is_tty:
            self._render()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._is_tty and self._line_length:
            self._stream.write("\n")
            self._stream.flush()

    def start(self, note: str) -> None:
        """Name the item now in flight; it stays on the bar until advance()."""
        self._note = note
        if self._is_tty:
            self._render()

    def advance(self, note: str | None = None) -> None:
        """Mark one step done. The note defaults to the one start() announced."""
        if note is not None:
            self._note = note
        self._done += 1
        self._render()

    def log(self, message: str) -> None:
        """Print a line above the bar, which redraws underneath it."""
        if self._is_tty:
            self._stream.write("\r" + " " * self._line_length + "\r")
            self._line_length = 0
        self._stream.write(message + "\n")
        if self._is_tty:
            self._render()
        else:
            self._stream.flush()

    def _render(self) -> None:
        line = f"{self._label} {self._bar()} {self._done}/{self._total}  {self._timing()}"
        if self._note:
            line += f"  {self._note[:NOTE_WIDTH]}"
        if self._is_tty:
            # Pad to the previous line's width so a shorter line leaves no tail.
            self._stream.write("\r" + line.ljust(self._line_length))
            self._line_length = len(line)
        else:
            self._stream.write(line + "\n")
        self._stream.flush()

    def _bar(self) -> str:
        filled = round(BAR_WIDTH * self._done / self._total) if self._total else BAR_WIDTH
        return "[" + "#" * filled + "-" * (BAR_WIDTH - filled) + "]"

    def _timing(self) -> str:
        elapsed = time.monotonic() - self._started
        if not self._done or self._done >= self._total:
            return f"({_format_duration(elapsed)})"
        remaining = elapsed / self._done * (self._total - self._done)
        return f"({_format_duration(elapsed)}, ~{_format_duration(remaining)} left)"

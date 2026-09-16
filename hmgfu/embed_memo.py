"""Phase 89.1/89.2 — one embedding per turn text, even across threads.

The turn's text is embedded on a worker thread for retrieval (`retrieve.build_query`, 73.2) while the sensitizer routes on the
main thread; the nearest-exemplar router (89.1) needs the same vector. A plain one-entry memo cannot share an embedding that is
still in flight, so the second caller would issue a second provider call for the same text. This memo makes the second caller
wait for the first call's result instead. One entry is kept after completion (the last text), which is all a turn needs."""
from __future__ import annotations

import threading
from concurrent.futures import Future
from typing import Callable, Dict, List, Optional, Tuple


class EmbedMemo:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._last: Optional[Tuple[str, List[float]]] = None
        self._inflight: Dict[str, Future] = {}
        self.calls = 0                        # provider calls actually made (tests, evidence)

    def __call__(self, text: str, fn: Callable[[str], List[float]]) -> List[float]:
        with self._lock:
            if self._last is not None and self._last[0] == text:
                return self._last[1]
            fut = self._inflight.get(text)
            owner = fut is None
            if owner:
                fut = Future()
                self._inflight[text] = fut
        if not owner:
            return fut.result()
        try:
            self.calls += 1
            vec = fn(text)
        except BaseException as exc:          # the waiters see the same failure; nothing cached
            with self._lock:
                self._inflight.pop(text, None)
            fut.set_exception(exc)
            raise
        with self._lock:
            self._last = (text, vec)
            self._inflight.pop(text, None)
        fut.set_result(vec)
        return vec

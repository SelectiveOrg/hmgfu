"""95.81 — on a phone the workspace was taller than the screen.

Reported from a real phone: the settings panel is cropped, and the composer with the Send button sits
below the fold. The cause is one line of the app shell, `#root { height: 100vh }`. On mobile browsers
100vh is the viewport WITH the retractable address bar and toolbar counted in, which is typically 60
to 120 px more than what the user can see. Everything the shell lays out from its own height inherits
the error: the settings panel's max-height is a percentage of a box that is taller than the screen, so
its bottom edge and the composer are pushed underneath the browser's own chrome.

Invariant: the app shell is as tall as the screen ACTUALLY is, and the bottom bar clears the phone's
safe area. `100dvh` is the dynamic viewport height, which excludes retracted browser UI; the plain
`100vh` rule stays first as the fallback for browsers without it.
"""

from __future__ import annotations

import os
import re

WEB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web")


def _read(*parts):
    with open(os.path.join(WEB, *parts), "r", encoding="utf-8") as fh:
        return fh.read()


def test_the_shell_is_as_tall_as_the_screen():
    html = _read("index.html")
    assert "100dvh" in html, "the shell must use the dynamic viewport height on phones"
    assert re.search(r"@supports\s*\(height:\s*100dvh\)", html), \
        "and keep a plain-vh fallback for browsers without it"


def test_the_shell_does_not_measure_itself_in_viewport_widths():
    """100vw counts the scrollbar, which is what produced the sideways wobble next to the crop.
    The prose that explains why may name it; a declaration may not."""
    assert not re.search(r"width\s*:\s*100vw", _read("index.html"))


def test_the_page_may_use_the_whole_screen():
    assert "viewport-fit=cover" in _read("index.html"), \
        "without it a notched phone leaves the safe-area insets unusable"


def test_the_composer_clears_the_home_indicator():
    src = _read("app", "Transcript.jsx")
    assert "safe-area-inset-bottom" in src, \
        "the bottom bar must add the phone's own bottom inset to its padding"


def test_the_changed_front_end_files_are_re_fetched():
    """The UI is served from disk with cache-busting query strings; a change nobody fetches is no fix."""
    html = _read("index.html")
    for name, lowest in (("Transcript.jsx", 22),):
        m = re.search(r"/app/" + re.escape(name) + r"\?v=(\d+)", html)
        assert m, f"{name} is not loaded with a version"
        assert int(m.group(1)) >= lowest, f"{name} keeps its old version, so browsers keep the old file"

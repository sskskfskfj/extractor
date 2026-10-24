"""Text normalization and nearest-occurrence matching."""

from __future__ import annotations

import html
import re
import unicodedata

from dataclasses import dataclass


@dataclass(frozen=True)
class PairMatch:
    distance: int
    start: int
    end: int
    excerpt: str


def clean_text(value: str) -> str:
    value = html.unescape(value or "")
    value = re.sub(r"<[^>]*>", " ", value)
    value = unicodedata.normalize("NFKC", value)
    return re.sub(r"\s+", " ", value).strip()


def nearest_pair(value: str, first: str, second: str, context_chars: int = 90) -> PairMatch | None:
    """Return the closest two literal terms in one row; distance excludes terms."""
    text = clean_text(value)
    first = clean_text(first)
    second = clean_text(second)
    if not text or not first or not second:
        return None

    first_positions = [m.span() for m in re.finditer(re.escape(first), text)]
    second_positions = [m.span() for m in re.finditer(re.escape(second), text)]
    if not first_positions or not second_positions:
        return None

    best: tuple[int, int, int] | None = None
    # A linear merge finds the nearest non-overlapping interval pair.
    i = j = 0
    while i < len(first_positions) and j < len(second_positions):
        a_start, a_end = first_positions[i]
        b_start, b_end = second_positions[j]
        if a_end <= b_start:
            candidate = (b_start - a_end, a_start, b_end)
            i += 1
        elif b_end <= a_start:
            candidate = (a_start - b_end, b_start, a_end)
            j += 1
        else:
            candidate = (0, min(a_start, b_start), max(a_end, b_end))
            # Overlapping keyword occurrences are both present; no intervening chars.
            i += 1
            j += 1
        if best is None or candidate < best:
            best = candidate

    if best is None:
        return None
    distance, start, end = best
    excerpt_start = max(0, start - context_chars)
    excerpt_end = min(len(text), end + context_chars)
    excerpt = text[excerpt_start:excerpt_end]
    if excerpt_start:
        excerpt = "…" + excerpt
    if excerpt_end < len(text):
        excerpt += "…"
    return PairMatch(distance, start, end, excerpt)


def nearest_sentence(value: str, first: str, second: str) -> tuple[str, PairMatch] | None:
    """Return the sentence containing the nearest pair, if both terms share one sentence."""
    text = clean_text(value)
    sentences = [part.strip() for part in re.split(r"(?<=[.!?。！？])\s+", text) if part.strip()]
    candidates: list[tuple[int, int, str, PairMatch]] = []
    for index, sentence in enumerate(sentences):
        match = nearest_pair(sentence, first, second)
        if match is not None:
            candidates.append((match.distance, index, sentence, match))
    if not candidates:
        return None
    _, _, sentence, match = min(candidates, key=lambda item: (item[0], item[1]))
    return sentence, match

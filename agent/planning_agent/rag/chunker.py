"""Heading-aware markdown chunking.

Why headings and not a fixed character count: a heading section is already one
idea. Cutting every N characters slices sentences in half and produces chunks
that embed badly — the vector ends up describing half a thought.

Three decisions worth defending in an interview:

1. **Split on headings first, then only split long sections.** Most sections are
   already the right size; forcing them into uniform windows is worse.
2. **Keep the heading path inside the chunk text.** A chunk that says "a 12.9
   point gap" is meaningless on its own. Prefixed with
   "METHOD.md > Feature discovery" it is both retrievable and citable — the
   citation comes for free.
3. **Overlap between windows.** A fact sitting on a boundary would otherwise be
   lost from both sides.

Token counts are approximated from word counts (see WORDS_PER_TOKEN). Calling a
tokenizer API per chunk would be exact and slow; the chunk size is a heuristic
anyway, so a heuristic count is honest here. It is stated rather than hidden.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

# English prose runs ~0.75 words per token. Used only to size chunks.
WORDS_PER_TOKEN = 0.75

TARGET_TOKENS = 500
OVERLAP_TOKENS = 50

TARGET_WORDS = int(TARGET_TOKENS * WORDS_PER_TOKEN)   # 375
OVERLAP_WORDS = int(OVERLAP_TOKENS * WORDS_PER_TOKEN)  # 37

_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*$")
_FENCE = re.compile(r"^\s*```")


@dataclass
class Chunk:
    """One retrievable unit."""

    text: str            # what gets embedded — includes the heading path
    source: str          # file name, e.g. "METHOD.md"
    heading_path: str    # e.g. "METHOD.md > 12. Limitations > Coverage"
    chunk_index: int     # position within its section, for stable ids
    word_count: int = field(default=0)

    @property
    def citation(self) -> str:
        return self.heading_path

    @property
    def id(self) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", self.heading_path.lower()).strip("-")
        return f"{slug}--{self.chunk_index}"[:400]

    def to_metadata(self) -> dict:
        return {
            "source": self.source,
            "heading_path": self.heading_path,
            "chunk_index": self.chunk_index,
            "word_count": self.word_count,
        }


def _split_sections(markdown: str, source: str) -> list[tuple[str, str]]:
    """Split into (heading_path, body) pairs, tracking the heading stack.

    Fenced code blocks are passed through untouched — a '#' inside a code fence
    is a comment, not a heading, and treating it as one shreds the document.
    """
    stack: list[tuple[int, str]] = []
    sections: list[tuple[str, str]] = []
    body: list[str] = []
    in_fence = False

    def path_now() -> str:
        return " > ".join([source] + [title for _, title in stack])

    for line in markdown.splitlines():
        if _FENCE.match(line):
            in_fence = not in_fence
            body.append(line)
            continue

        match = None if in_fence else _HEADING.match(line)
        if match:
            if any(part.strip() for part in body):
                sections.append((path_now(), "\n".join(body).strip()))
            body = []
            level = len(match.group(1))
            title = match.group(2).strip()
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, title))
        else:
            body.append(line)

    if any(part.strip() for part in body):
        sections.append((path_now(), "\n".join(body).strip()))
    return sections


def _window(words: list[str]) -> list[list[str]]:
    """Sliding windows with overlap. Only used on over-long sections."""
    if len(words) <= TARGET_WORDS:
        return [words]
    step = TARGET_WORDS - OVERLAP_WORDS
    windows = []
    start = 0
    while start < len(words):
        windows.append(words[start : start + TARGET_WORDS])
        if start + TARGET_WORDS >= len(words):
            break
        start += step
    return windows


def chunk_markdown(markdown: str, source: str) -> list[Chunk]:
    """Chunk one markdown document."""
    chunks: list[Chunk] = []
    for heading_path, body in _split_sections(markdown, source):
        words = body.split()
        if not words:
            continue
        for index, window in enumerate(_window(words)):
            # The heading path is prepended to the embedded text on purpose:
            # it is context the section body assumes but never states.
            text = f"{heading_path}\n\n{' '.join(window)}"
            chunks.append(
                Chunk(
                    text=text,
                    source=source,
                    heading_path=heading_path,
                    chunk_index=index,
                    word_count=len(window),
                )
            )
    return chunks


def chunk_files(paths: list[Path]) -> list[Chunk]:
    """Chunk several markdown files, skipping any that are missing."""
    chunks: list[Chunk] = []
    for path in paths:
        if not path.exists():
            continue
        chunks.extend(chunk_markdown(path.read_text(encoding="utf-8"), path.name))
    return chunks

"""Album reader (#317, kernel C5): one vector PDF page -> axes, dimensions, level marks, legend, scale.

PyMuPDF (optional extra ``pdf-review``) is imported only when a page is read, so ``import dt_ai.album``
works without it. Rules and assumptions: :mod:`dt_ai.album.reader`.
"""

from dt_ai.album.reader import (
    AlbumExtraMissing,
    AlbumReadError,
    PageReading,
    check_dimension,
    check_level_pair,
    parse_level_text,
    read_page,
    reading_to_json,
)

__all__ = [
    "AlbumExtraMissing",
    "AlbumReadError",
    "PageReading",
    "check_dimension",
    "check_level_pair",
    "parse_level_text",
    "read_page",
    "reading_to_json",
]

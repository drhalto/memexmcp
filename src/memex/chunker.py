"""File-type aware chunker.

- Code: boundary-aware (def/class/fn/...) falling back to size.
- Markdown / plain text: heading- and paragraph-aware window.
- PDF: pypdf text extraction → text window chunker.
- DOCX: python-docx paragraph extraction → text window chunker.
- HTML: selectolax strip → text window chunker.
- Unknown: tries UTF-8 text; skips binaries.

Every path returns a list[Chunk] with 1-based inclusive line spans (or page
spans for PDFs, reported via start_line=end_line=page_number).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

CODE_SUFFIXES: frozenset[str] = frozenset({
    ".py", ".pyi",
    ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs",
    ".go", ".rs", ".rb", ".php", ".swift", ".kt", ".scala",
    ".java", ".c", ".cc", ".cpp", ".h", ".hh", ".hpp", ".cs",
    ".sql", ".sh", ".bash",
    ".toml", ".yaml", ".yml",
})
TEXT_SUFFIXES: frozenset[str] = frozenset({
    ".md", ".mdx", ".rst", ".txt", ".org",
})
PDF_SUFFIXES: frozenset[str] = frozenset({".pdf"})
DOCX_SUFFIXES: frozenset[str] = frozenset({".docx"})
HTML_SUFFIXES: frozenset[str] = frozenset({".html", ".htm"})

ALLOWED_SUFFIXES: frozenset[str] = (
    CODE_SUFFIXES | TEXT_SUFFIXES | PDF_SUFFIXES | DOCX_SUFFIXES | HTML_SUFFIXES
)

MAX_FILE_BYTES = 10_000_000  # 10 MB — bigger than code default since PDFs get large


_CODE_BOUNDARY_PREFIXES = (
    "def ", "async def ", "class ",
    "function ", "async function ", "export ",
    "import ", "from ",
    "const ", "let ", "var ",
    "pub fn ", "fn ", "impl ",
    "type ", "interface ", "struct ", "enum ",
    "package ", "func ",
)


@dataclass(frozen=True, slots=True, kw_only=True)
class Chunk:
    start_line: int  # 1-based inclusive (or page number for PDFs)
    end_line: int    # 1-based inclusive
    content: str


def chunk_file(path: Path, *, max_chunk_size: int = 2000) -> list[Chunk]:
    """Dispatch on suffix. Returns [] for empty or unparseable files."""
    suffix = path.suffix.lower()
    try:
        if suffix in CODE_SUFFIXES:
            return chunk_code(path.read_text(encoding="utf-8"), max_chunk_size=max_chunk_size)
        if suffix in TEXT_SUFFIXES:
            return chunk_text(path.read_text(encoding="utf-8"), max_chunk_size=max_chunk_size)
        if suffix in PDF_SUFFIXES:
            return chunk_pdf(path, max_chunk_size=max_chunk_size)
        if suffix in DOCX_SUFFIXES:
            return chunk_docx(path, max_chunk_size=max_chunk_size)
        if suffix in HTML_SUFFIXES:
            return chunk_html(path, max_chunk_size=max_chunk_size)
    except (OSError, UnicodeDecodeError):
        return []
    return []


def chunk_code(content: str, *, max_chunk_size: int = 2000) -> list[Chunk]:
    if not content.strip():
        return []
    lines = content.split("\n")
    chunks: list[Chunk] = []
    cur_lines: list[str] = []
    cur_size = 0
    cur_start = 1

    def flush(end_line_1based: int) -> None:
        nonlocal cur_lines, cur_size, cur_start
        if cur_lines:
            text = "\n".join(cur_lines)
            if text.strip():
                chunks.append(Chunk(start_line=cur_start, end_line=end_line_1based, content=text))
        cur_lines = []
        cur_size = 0

    for idx, line in enumerate(lines):
        line_no = idx + 1
        line_size = len(line) + 1
        stripped = line.lstrip()
        is_boundary = any(stripped.startswith(p) for p in _CODE_BOUNDARY_PREFIXES)
        should_break = (
            (is_boundary and cur_size > max_chunk_size * 0.5)
            or (cur_size + line_size > max_chunk_size and cur_lines)
        )
        if should_break:
            flush(line_no - 1)
            cur_start = line_no
            cur_lines = [line]
            cur_size = line_size
        else:
            if not cur_lines:
                cur_start = line_no
            cur_lines.append(line)
            cur_size += line_size

    flush(len(lines))
    if not chunks:
        chunks.append(Chunk(start_line=1, end_line=len(lines), content=content))
    return chunks


def chunk_text(content: str, *, max_chunk_size: int = 2000) -> list[Chunk]:
    """Prose-friendly chunker. Prefers breaks at blank lines and markdown headings."""
    if not content.strip():
        return []
    lines = content.split("\n")
    chunks: list[Chunk] = []
    cur: list[str] = []
    cur_size = 0
    cur_start = 1

    def flush(end_line: int) -> None:
        nonlocal cur, cur_size, cur_start
        if cur:
            text = "\n".join(cur)
            if text.strip():
                chunks.append(Chunk(start_line=cur_start, end_line=end_line, content=text))
        cur = []
        cur_size = 0

    for idx, line in enumerate(lines):
        line_no = idx + 1
        line_size = len(line) + 1
        is_heading = line.lstrip().startswith("#")
        is_blank = not line.strip()
        should_break = (
            (is_heading and cur_size > max_chunk_size * 0.4)
            or (is_blank and cur_size > max_chunk_size * 0.8)
            or (cur_size + line_size > max_chunk_size and cur)
        )
        if should_break:
            flush(line_no - 1)
            cur_start = line_no
            cur = [line]
            cur_size = line_size
        else:
            if not cur:
                cur_start = line_no
            cur.append(line)
            cur_size += line_size

    flush(len(lines))
    if not chunks:
        chunks.append(Chunk(start_line=1, end_line=len(lines), content=content))
    return chunks


def chunk_pdf(path: Path, *, max_chunk_size: int = 2000) -> list[Chunk]:
    """One chunk per page, subdivided if a page exceeds max_chunk_size."""
    try:
        from pypdf import PdfReader
    except ImportError:
        return []
    try:
        reader = PdfReader(str(path))
    except Exception:
        return []

    chunks: list[Chunk] = []
    for page_idx, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception:
            continue
        text = text.strip()
        if not text:
            continue
        if len(text) <= max_chunk_size:
            chunks.append(Chunk(start_line=page_idx, end_line=page_idx, content=text))
        else:
            # Long page — slice into size-bounded pieces, all tagged with page_idx.
            for piece in _slice_text(text, max_chunk_size):
                chunks.append(Chunk(start_line=page_idx, end_line=page_idx, content=piece))
    return chunks


def chunk_docx(path: Path, *, max_chunk_size: int = 2000) -> list[Chunk]:
    try:
        import docx
    except ImportError:
        return []
    try:
        doc = docx.Document(str(path))
    except Exception:
        return []
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    if not paragraphs:
        return []
    # Join and treat as text — paragraph boundaries become blank lines for chunk_text.
    joined = "\n\n".join(paragraphs)
    return chunk_text(joined, max_chunk_size=max_chunk_size)


def chunk_html(path: Path, *, max_chunk_size: int = 2000) -> list[Chunk]:
    try:
        from selectolax.parser import HTMLParser
    except ImportError:
        return []
    try:
        raw = path.read_bytes()
    except OSError:
        return []
    try:
        tree = HTMLParser(raw)
    except Exception:
        return []
    text = tree.text(separator="\n", strip=True)
    if not text.strip():
        return []
    return chunk_text(text, max_chunk_size=max_chunk_size)


def _slice_text(text: str, max_size: int) -> list[str]:
    """Greedy paragraph-aware slicer. Never breaks a paragraph unless it alone exceeds max_size."""
    paragraphs = text.split("\n\n")
    out: list[str] = []
    cur: list[str] = []
    cur_size = 0
    for para in paragraphs:
        p_size = len(para) + 2
        if cur_size + p_size > max_size and cur:
            out.append("\n\n".join(cur))
            cur = [para]
            cur_size = p_size
        else:
            cur.append(para)
            cur_size += p_size
    if cur:
        out.append("\n\n".join(cur))
    # If a single paragraph blew the limit, hard-split it.
    final: list[str] = []
    for piece in out:
        if len(piece) <= max_size:
            final.append(piece)
        else:
            for i in range(0, len(piece), max_size):
                final.append(piece[i : i + max_size])
    return final

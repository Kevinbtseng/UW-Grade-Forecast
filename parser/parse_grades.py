"""Parse a UW-Madison "Percentage Distribution of Grades" PDF into section rows.

Each text line is read from the right edge: the last 16 tokens are the grade columns,
optionally preceded by the average GPA, then the grade count, section and course number.
Redacted sections carry ``***`` instead of GPA and percentages.
"""

import hashlib
import logging
import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import NamedTuple

import pdfplumber
import pyarrow as pa
import pyarrow.parquet as pq

logger = logging.getLogger(__name__)

PARSER_VERSION = "0.1.0"

# Parsed by position, never by header text: COVID terms label S and U as S/SD and U/UD.
GRADE_COLUMNS = (
    "a", "ab", "b", "bc", "c", "d", "f", "s", "u", "cr", "n", "p", "i", "nw", "nr", "other",
)
PCT_SUM_TOLERANCE = 1.0
SUSPECT_NUMERIC_TOKENS = 8
NO_GRADES = (None,) * len(GRADE_COLUMNS)

TERM_RE = re.compile(r"^TERM\s*:\s*(\d+)")
SUBJECT_RE = re.compile(r"^(\d+)\s+.+?\s+Grades\s*GPA$")  # term 1032 prints GradesGPA
NUM_RE = re.compile(r"^(?:\.|\d+(?:\.\d+)?)$")
GPA_RE = re.compile(r"^\d\.\d{3}$")
SECTION_RE = re.compile(r"^(?=.*\d)[0-9A-Z]{1,4}$")  # 001 now; 00A, 000A, 1, 30 in older terms
COUNT_RE = re.compile(r"^\d+$")
REDACTED = "***"

SCHEMA = pa.schema(
    [
        ("term", pa.int64()),
        ("subject_code", pa.string()),
        ("course_number", pa.string()),
        ("section", pa.string()),
        ("course_name", pa.string()),
        ("n_grades", pa.int64()),
        ("avg_gpa", pa.float64()),
        *[(col, pa.float64()) for col in GRADE_COLUMNS],
        ("redacted", pa.bool_()),
        ("source_file", pa.string()),
        ("source_sha256", pa.string()),
        ("parser_version", pa.string()),
    ]
)


class _Tail(NamedTuple):
    head: list[str]
    gpa: float | None
    grades: list[float] | None  # None means redacted


@dataclass
class ParseResult:
    source_file: str = ""
    source_sha256: str = ""
    term: int | None = None
    rows: list[dict] = field(default_factory=list)
    expected_total_grades: int | None = None
    expected_total_gpa: float | None = None
    unparsed_lines: list[str] = field(default_factory=list)

    @property
    def bad_pct_sum(self) -> int:
        """Graded sections whose percentages don't sum to 100 within the tolerance."""
        graded_rows = [row for row in self.rows if not row["redacted"]]
        count = 0
        for row in graded_rows:
            total_pct = sum(row[col] for col in GRADE_COLUMNS)
            if abs(total_pct - 100.0) > PCT_SUM_TOLERANCE:
                count += 1
        return count

    @property
    def reconciliation(self) -> float | None:
        """Share of the report's grand-total grade count captured in the parsed rows."""
        if not self.expected_total_grades:
            return None
        return sum(row["n_grades"] for row in self.rows) / self.expected_total_grades


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def extract_lines(pdf_path: Path) -> Iterator[str]:
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            yield from (page.extract_text() or "").split("\n")


def parse_pdf(pdf_path: Path) -> ParseResult:
    return parse_lines(
        extract_lines(pdf_path),
        source_file=pdf_path.name,
        source_sha256=sha256_file(pdf_path),
    )


def _split_tail(tokens: list[str]) -> _Tail | None:
    if REDACTED in tokens:
        return _Tail(tokens[: tokens.index(REDACTED)], None, None)
    n_cols = len(GRADE_COLUMNS)
    grade_tokens = tokens[-n_cols:]
    if len(grade_tokens) < n_cols or not all(NUM_RE.match(token) for token in grade_tokens):
        return None
    grades = [0.0 if token == "." else float(token) for token in grade_tokens]
    head = tokens[:-n_cols]
    gpa = None
    # Sections graded only S/U/CR etc. have no GPA token at all (term 1032 prints #Num!).
    if head and head[-1] == "#Num!":
        head = head[:-1]
    elif head and GPA_RE.match(head[-1]):
        gpa = float(head[-1])
        head = head[:-1]
    return _Tail(head, gpa, grades)


def _clean_name(tokens: list[str]) -> str | None:
    # Titles from term 1194 on contain U+FFFD that other terms extract as spaces.
    name = " ".join(" ".join(tokens).replace("\ufffd", " ").split())
    return name or None


def parse_lines(lines: Iterable[str], source_file: str, source_sha256: str) -> ParseResult:
    result = ParseResult(source_file=source_file, source_sha256=source_sha256)
    provenance = {
        "source_file": source_file,
        "source_sha256": source_sha256,
        "parser_version": PARSER_VERSION,
    }
    subject: str | None = None
    names: dict[str, str] = {}  # course_number -> name, within the current subject
    pending: list[dict] = []  # sections still waiting for a Course Total line to name them
    in_summary = False

    def flush_pending() -> None:
        for row in pending:
            logger.warning(
                "no course name for %s %s %s",
                row["subject_code"],
                row["course_number"],
                row["section"],
            )
        pending.clear()

    for raw in lines:
        line = raw.strip()
        if not line:
            continue

        if match := TERM_RE.match(line):
            result.term = int(match.group(1))
            continue

        if match := SUBJECT_RE.match(line):
            # The header repeats on every page; pending sections carry across pages.
            if match.group(1) != subject:
                flush_pending()
                names.clear()
                subject = match.group(1)
                in_summary = False  # term 1032 repeats the header inside the summary block
            continue

        if line.startswith(("Summary by Level", "University of Wisconsin-Madison #")):
            in_summary = True
            continue

        tokens = line.split()

        if line.startswith("Grand Total"):
            # Terms 1064-1094 print spreadsheet errors (#Name?) here; leave the totals unset.
            if len(tokens) > 3 and tokens[2].isdigit() and GPA_RE.match(tokens[3]):
                result.expected_total_grades = int(tokens[2])
                result.expected_total_gpa = float(tokens[3])
            in_summary = True
            continue

        if in_summary or "Dept. Total" in line:
            continue

        tail = _split_tail(tokens)
        if tail and len(tail.head) >= 3:
            head = tail.head
            label = tuple(head[-3:-1])

            if label == ("Section", "Total"):
                continue  # sub-total of a section listed on several lines; the parts are the rows

            if label == ("Course", "Total") and COUNT_RE.match(head[-1]):
                # Course Total is not a section; it only supplies the course name.
                name = _clean_name(head[:-3])
                if name and pending:
                    course = pending[-1]["course_number"]
                    for row in pending:
                        if row["course_number"] == course:
                            row["course_name"] = name
                    pending[:] = [row for row in pending if row["course_name"] is None]
                    names[course] = name
                continue

            if SECTION_RE.match(head[-2]) and COUNT_RE.match(head[-1]):
                if subject is None or result.term is None:
                    raise ValueError(f"section row before term/subject header: {line!r}")
                course, section = head[-3], head[-2]
                name = _clean_name(head[:-3])
                row = {
                    "term": result.term,
                    "subject_code": subject,
                    "course_number": course,
                    "section": section,
                    "course_name": name or names.get(course),
                    "n_grades": int(head[-1]),
                    "avg_gpa": tail.gpa,
                    **dict(zip(GRADE_COLUMNS, tail.grades or NO_GRADES)),
                    "redacted": tail.grades is None,
                    **provenance,
                }
                if name:
                    names[course] = name
                elif course not in names:
                    pending.append(row)
                result.rows.append(row)
                continue

        numeric = sum(token == REDACTED or bool(NUM_RE.match(token)) for token in tokens)
        if numeric >= SUSPECT_NUMERIC_TOKENS:
            logger.warning("unparsed data-like line: %r", line)
            result.unparsed_lines.append(line)

    flush_pending()
    return result


def write_parquet(result: ParseResult, out_path: Path) -> None:
    metadata = {"parser_version": PARSER_VERSION, "source_sha256": result.source_sha256}
    if result.term is not None:
        metadata["term"] = str(result.term)
    if result.expected_total_grades is not None:
        metadata["expected_total_grades"] = str(result.expected_total_grades)
    if result.expected_total_gpa is not None:
        metadata["expected_total_gpa"] = str(result.expected_total_gpa)
    table = pa.Table.from_pylist(result.rows, schema=SCHEMA.with_metadata(metadata))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = out_path.with_name(out_path.name + ".tmp")
    pq.write_table(table, tmp_path)
    tmp_path.replace(out_path)

from pathlib import Path

import parse_grades as pg
import pyarrow.parquet as pq
import pytest

FIXTURES = Path(__file__).parent / "fixtures"


def parse_fixtures(*names: str) -> pg.ParseResult:
    lines: list[str] = []
    for name in names:
        lines.extend((FIXTURES / name).read_text(encoding="utf-8").splitlines())
    return pg.parse_lines(lines, source_file="fixture", source_sha256="")


def find(result: pg.ParseResult, course: str, section: str) -> dict:
    return next(
        row
        for row in result.rows
        if (row["course_number"], row["section"]) == (course, section)
    )


@pytest.fixture(scope="module")
def fall_1262() -> pg.ParseResult:
    return parse_fixtures("1262_p001.txt", "1262_p002.txt")


def test_term_and_subject_come_from_headers(fall_1262):
    assert fall_1262.term == 1262
    assert {row["subject_code"] for row in fall_1262.rows} == {"108"}


def test_old_term_code_drops_leading_zero():
    result = parse_fixtures("972_p001.txt")
    assert result.term == 972
    assert isinstance(result.term, int)


def test_section_row_with_name_and_values(fall_1262):
    row = find(fall_1262, "101", "001")
    assert row["course_name"] == "Intro to Ag & Applied Econ"
    assert row["n_grades"] == 65
    assert row["avg_gpa"] == 3.138
    assert [row[c] for c in ("a", "ab", "b", "bc", "c", "d")] == [20.0, 32.3, 26.2, 10.8, 4.6, 6.2]
    assert row["redacted"] is False


def test_section_keeps_leading_zeros_as_text(fall_1262):
    assert find(fall_1262, "101", "001")["section"] == "001"


def test_dot_means_zero(fall_1262):
    row = find(fall_1262, "101", "001")
    assert row["f"] == 0.0
    assert row["nr"] == 0.0


def test_grade_columns_are_positional(fall_1262):
    row = find(fall_1262, "244", "001")
    assert row["nw"] == 3.6
    assert row["nr"] == 1.8
    assert row["other"] == 0.0
    assert row["s"] == 0.0


def test_redacted_row_keeps_row_and_nulls_values(fall_1262):
    row = find(fall_1262, "299", "101")
    assert row["redacted"] is True
    assert row["n_grades"] == 1
    assert row["avg_gpa"] is None
    assert all(row[c] is None for c in pg.GRADE_COLUMNS)


def test_course_total_names_earlier_unnamed_sections(fall_1262):
    for section in ("001", "003", "007"):
        assert find(fall_1262, "306", section)["course_name"] == "The Real Estate Process"
    for section in ("081", "082", "101"):
        assert find(fall_1262, "399", section)["course_name"] == "Coord Intrnshp/Cooprtv Educ"


def test_course_total_name_applies_across_page_break(fall_1262):
    # 990 057/058 are on page 1; the Course Total naming them is on page 2.
    assert find(fall_1262, "990", "057")["course_name"] == "Research and Thesis"
    assert find(fall_1262, "990", "105")["course_name"] == "Research and Thesis"


def test_old_term_names_sections_from_course_total():
    result = parse_fixtures("972_p001.txt")
    row = find(result, "215", "001")
    assert row["course_name"] == "Intro to Ag Econ"
    assert row["avg_gpa"] == 3.134
    assert row["d"] == 1.5


def test_section_without_gpa_is_not_redacted(fall_1262):
    row = find(fall_1262, "990", "093")
    assert row["redacted"] is False
    assert row["avg_gpa"] is None
    assert row["s"] == 100.0


def test_num_error_in_gpa_column_means_no_gpa():
    lines = [
        "TERM:1032 Percentage Distribution of Grades",
        "108 A A E GradesGPA",
        "Seminar 900 001 12 #Num! 100.0 . . . . . . . . . . . . . . .",
        "962 004 2 #Num! 100.0 . . . . . . . . . . . . . . .",
        "Smr-Macromolecular Chem Course Total 2 #Num! 100.0 . . . . . . . . . . . . . . .",
    ]
    result = pg.parse_lines(lines, "fixture", "")
    assert [(row["course_number"], row["n_grades"], row["avg_gpa"]) for row in result.rows] == [
        ("900", 12, None),
        ("962", 2, None),
    ]
    assert result.rows[1]["course_name"] == "Smr-Macromolecular Chem"
    assert result.unparsed_lines == []


def test_covid_s_and_u_columns_parse_by_position():
    result = parse_fixtures("1214_p001.txt")
    row = find(result, "215", "001")
    assert row["s"] == 9.0
    assert row["u"] == 4.5


def test_total_and_summary_rows_are_not_sections(fall_1262):
    assert len(fall_1262.rows) == 47
    assert sum(row["redacted"] for row in fall_1262.rows) == 27
    assert fall_1262.unparsed_lines == []
    assert not any(row["course_number"] in {"Total", "Freshmen"} for row in fall_1262.rows)


def test_percentages_sum_to_100_for_graded_sections(fall_1262):
    assert fall_1262.bad_pct_sum == 0


def test_grand_total_is_stored_for_reconciliation():
    result = parse_fixtures("1262_p481.txt")
    assert result.rows == []
    assert result.expected_total_grades == 214086
    assert result.expected_total_gpa == 3.493


def test_subject_header_without_space_is_recognized():
    lines = [
        "TERM:1032 Percentage Distribution of Grades",
        "108 A A E GradesGPA",
        "215 001 110 2.908 12.7 16.4 34.5 14.5 18.2 1.8 0.9 0.9 . . . . . . . .",
    ]
    row = pg.parse_lines(lines, "fixture", "").rows[0]
    assert (row["term"], row["subject_code"], row["section"]) == (1032, "108", "001")


def test_subject_header_repeated_inside_summary_block_keeps_summary_skipped():
    lines = [
        "TERM:1032 Percentage Distribution of Grades",
        "108 A A E GradesGPA",
        "215 001 110 2.908 12.7 16.4 34.5 14.5 18.2 1.8 0.9 0.9 . . . . . . . .",
        "Summary by Level # Ave A AB B BC C D F S U CR N P I NW NR Other",
        "108 A A E GradesGPA",
        "Freshmen 97 2.979 16.5 16.5 29.9 20.6 16.5 . . . . . . . . . . .",
        "Prof Yr 1 3835 2.496 30.1 10.4 11.4 2.2 1.2 0.2 0.0 23.3 0.1 5.3 . 0.0 . . . 0.2",
    ]
    result = pg.parse_lines(lines, "fixture", "")
    assert len(result.rows) == 1
    assert result.unparsed_lines == []


@pytest.mark.parametrize(
    "grand_total",
    [
        "Grand Total #Name?#Name?Name?Name?Name?Name?Name?Name?Name?Name?Name?Name?Name?Name? #Name?",
        "Grand Total 153853#Name?Name?Name?Name?Name?Name?Name?Name?Name?Name?Name?Name? #Name?",
    ],
)
def test_corrupt_grand_total_leaves_totals_unset(grand_total):
    lines = ["TERM :1064 Percentage Distribution of Grades", grand_total, "Freshmen 13689 2.957"]
    result = pg.parse_lines(lines, "fixture", "")
    assert result.expected_total_grades is None
    assert result.expected_total_gpa is None
    assert result.reconciliation is None


def test_replacement_character_in_title_is_normalized():
    lines = [
        "TERM :1262 Percentage Distribution of Grades",
        "108 A A E Grades GPA",
        "Intro�to Ag 101 001 5 3.000 100.0 . . . . . . . . . . . . . . .",
    ]
    result = pg.parse_lines(lines, "fixture", "")
    assert result.rows[0]["course_name"] == "Intro to Ag"


def test_course_name_ending_in_digits_keeps_course_number():
    lines = [
        "TERM :1262 Percentage Distribution of Grades",
        "108 A A E Grades GPA",
        "Development Economics 2 731 001 5 ***",
    ]
    row = pg.parse_lines(lines, "fixture", "").rows[0]
    assert row["course_name"] == "Development Economics 2"
    assert row["course_number"] == "731"


@pytest.mark.parametrize("section", ["00A", "000A", "1", "30"])
def test_non_standard_section_codes_are_sections(section):
    lines = [
        "TERM :1032 Percentage Distribution of Grades",
        "108 A A E Grades GPA",
        f"Contemporary Topics 365 {section} 1 *** . . . . . . .",
    ]
    row = pg.parse_lines(lines, "fixture", "").rows[0]
    assert (row["course_number"], row["section"], row["n_grades"]) == ("365", section, 1)


def test_section_total_is_skipped_and_parts_are_kept():
    lines = [
        "TERM :1262 Percentage Distribution of Grades",
        "108 A A E Grades GPA",
        "Some Course 971 008 2 *** . . . . . . .",
        "971 008 3 *** . . . . . . .",
        "Section Total 5 . . . . . . . 100.0 . . . . . . . .",
    ]
    result = pg.parse_lines(lines, "fixture", "")
    assert [row["n_grades"] for row in result.rows] == [2, 3]
    assert result.unparsed_lines == []


def test_write_parquet_round_trip(tmp_path, fall_1262):
    out = tmp_path / "1262.parquet"
    pg.write_parquet(fall_1262, out)
    table = pq.read_table(out)
    assert table.num_rows == 47
    assert table.schema.field("section").type == "string"
    assert table.schema.metadata[b"parser_version"] == pg.PARSER_VERSION.encode()

from pathlib import Path

from algolens.ingest.formula_quality import find_formula_warnings, main


def test_flags_known_probability_corruption_with_page() -> None:
    markdown = """<!-- source_page: 2 -->
If AB != C:
Pr[output=YES] ≤ 12
"""
    warnings = find_formula_warnings(markdown)

    assert len(warnings) == 1
    assert warnings[0].source_page == 2
    assert "probability" in warnings[0].pattern


def test_flags_known_good_pivot_bound_corruption() -> None:
    markdown = """<!-- source_page: 5 -->
Good pivot: sizes of L and G ≤ 34
"""
    warnings = find_formula_warnings(markdown)

    assert len(warnings) == 1
    assert warnings[0].source_page == 5
    assert "good-pivot" in warnings[0].pattern


def test_flags_malformed_recurrence() -> None:
    markdown = """<!-- source_page: 6 -->
T ( n ) ≤ T + T + 2 cn
"""
    warnings = find_formula_warnings(markdown)

    assert len(warnings) == 1
    assert warnings[0].source_page == 6
    assert "recursive arguments" in warnings[0].pattern


def test_does_not_flag_reviewed_correct_expressions() -> None:
    markdown = """<!-- source_page: 5 -->
Good pivot: both subarrays have size at most 3n/4.
Pr[output = YES] <= 1/2
T(n) <= T(n/4) + T(3n/4) + 2*c*n
"""
    assert find_formula_warnings(markdown) == []


def test_warning_without_page_marker_keeps_page_unknown() -> None:
    markdown = "Pr[output=YES] ≤ 12"
    warnings = find_formula_warnings(markdown)

    assert len(warnings) == 1
    assert warnings[0].source_page is None


def test_flags_actual_quicksort_recurrence_layout() -> None:
    markdown = """<!-- source_page: 5 -->
_T_ ( _n_ ) _? maxn/_ 4 _?i?_ 3 _n/_ 4( _T_ ( _i_ ) + _T_ ( _n ? i_ )) + _E_ (#iterations) _? cn_
"""
    warnings = find_formula_warnings(markdown)

    assert any(
        warning.source_page == 5 and "recurrence" in warning.pattern.lower() for warning in warnings
    )


def test_cli_reports_warnings_and_can_fail_strictly(tmp_path: Path, capsys) -> None:
    notes = tmp_path / "notes.md"
    notes.write_text(
        "<!-- source_page: 2 -->\nPr[output=YES] ≤ 12\n",
        encoding="utf-8",
    )

    assert main(["--path", str(notes)]) == 0
    output = capsys.readouterr().out
    assert "Warnings found: 1" in output
    assert "PDF page 2" in output

    assert main(["--path", str(notes), "--fail-on-warning"]) == 1
    assert "Warnings found: 1" in capsys.readouterr().out


def test_cli_returns_two_for_missing_input(tmp_path: Path, capsys) -> None:
    missing = tmp_path / "missing.md"

    assert main(["--path", str(missing)]) == 2
    assert "could not read" in capsys.readouterr().err.lower()


def test_cli_default_audits_checked_in_extraction(capsys) -> None:
    assert main([]) == 0
    output = capsys.readouterr().out

    assert "Warnings found: 4" in output
    assert "PDF page 2" in output
    assert "PDF page 5" in output
    assert "PDF page 6" in output

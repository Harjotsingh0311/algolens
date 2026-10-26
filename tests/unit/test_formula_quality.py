from algolens.ingest.formula_quality import find_formula_warnings


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

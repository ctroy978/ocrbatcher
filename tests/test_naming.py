from grader.naming import extract_first_name


def test_extracts_name_from_colon():
    text = "Name: Alex\nScore: 95"
    result = extract_first_name(text, fallback="Student", page_index=0)
    assert result.display_name == "Alex"
    assert result.filename_stem == "alex"


def test_extracts_name_with_spacing_and_accents():
    text = "name:   Zoë\nEssay text here."
    result = extract_first_name(text, fallback="Student", page_index=2)
    assert result.display_name == "Zoë"
    assert result.filename_stem == "zoe"


def test_fallback_used_when_missing():
    text = "Essay text with no explicit name."
    result = extract_first_name(text, fallback="Student", page_index=2)
    assert result.display_name == "Student_03"
    assert result.filename_stem == "student_03"


def test_line_start_variation():
    text = "Name   John Doe\nMore text"
    result = extract_first_name(text, fallback=None, page_index=1)
    assert result.display_name == "John"
    assert result.filename_stem == "john"


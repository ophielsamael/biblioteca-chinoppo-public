from biblio.proto import line


def test_escapes_tabs_newlines_and_none():
    assert line(1, "Rock\t&\nRoll", None, "Ñandú 'x'") == "1\tRock & Roll\t\tÑandú 'x'"

from biblio.names import parse_episode, parse_name


def test_ep_simple_upper():   assert parse_episode("S01E01.MKV") == (1, [1])
def test_ep_with_title():     assert parse_episode("S03E05 No hay Acción de Gracias.mkv") == (3, [5])
def test_ep_leading_space():  assert parse_episode(" S04E01 M de mejores amigas.mkv") == (4, [1])
def test_ep_show_prefix():    assert parse_episode("Game of Thrones S01E10.mkv") == (1, [10])
def test_ep_multi_lower():    assert parse_episode("s01e03e04.iso") == (1, [3, 4])
def test_ep_multi_mixed():    assert parse_episode("S02e06E07e08.iso") == (2, [6, 7, 8])
def test_ep_three():          assert parse_episode("S02E01e02e03.iso") == (2, [1, 2, 3])
def test_ep_no_code():        assert parse_episode("Making of.mkv") is None


def test_title_and_year():
    assert parse_name("Black Swan (2010)") == ("Black Swan", 2010)


def test_year_without_parens():
    assert parse_name("Begin Again( 2014)") == ("Begin Again", 2014)


def test_dots_and_quality_tags():
    assert parse_name("Blade.Runner.2049.2017.UHD.BluRay") == ("Blade Runner 2049", 2017)


def test_no_year():
    assert parse_name("80s live") == ("80s live", None)


def test_accents_kept():
    assert parse_name("La Tumba de las Luciérnagas (1988)") == ("La Tumba de las Luciérnagas", 1988)


def test_trailing_space():
    assert parse_name("Ciudad de Dios ") == ("Ciudad de Dios", None)

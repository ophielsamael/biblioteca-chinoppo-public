from biblio import keys
from biblio.config import load_settings

GOOD = "0123456789abcdef0123456789abcdef"


def test_saved_key_wins_over_the_environment_and_the_placeholder_is_ignored(tmp_path):
    assert keys.tmdb_key("pon_aqui_tu_clave_de_tmdb", tmp_path) == ""
    assert keys.tmdb_key("a" * 32, tmp_path) == "a" * 32
    keys.save(tmp_path, tmdb=GOOD)
    assert keys.tmdb_key("a" * 32, tmp_path) == GOOD
    assert load_settings({"DATA_DIR": str(tmp_path), "TMDB_API_KEY": "b" * 32}).tmdb_key == GOOD
    keys.save(tmp_path, tmdb="")                 # an empty value never erases a saved key
    assert keys.load(tmp_path)["tmdb"] == GOOD


def test_keys_api_saves_uses_it_and_rescans(settings, catalog):
    from app import create_app
    rescans = []
    app = create_app(settings, catalog)
    app.config["RESCAN"] = lambda: rescans.append(1)
    c = app.test_client()
    assert c.get("/api/keys").json == {"tmdb": False}
    assert c.post("/api/keys", json={"tmdb": "nope"}).status_code == 400
    assert c.post("/api/keys", json={"tmdb": GOOD}).json == {"ok": True}
    assert c.get("/api/keys").json == {"tmdb": True}
    assert settings.tmdb_key == GOOD and rescans == [1]
    assert keys.load(settings.data_dir)["tmdb"] == GOOD
    assert GOOD not in c.get("/api/keys").get_data(as_text=True)      # the key itself is never served

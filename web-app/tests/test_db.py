import db as db_module


def test_get_db_returns_module_database():
    assert db_module.get_db() is db_module.db

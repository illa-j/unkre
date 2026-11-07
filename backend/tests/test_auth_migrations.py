from io import StringIO
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

INI = Path(__file__).resolve().parents[1] / "src/adapters/database/alembic.ini"


def test_migrations_upgrade_and_downgrade_auth_without_removing_users(tmp_path):
    config = Config(str(INI))
    engine = create_engine(f"sqlite:///{tmp_path / 'migrations.db'}")
    try:
        with engine.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
            tables = inspect(connection).get_table_names()
            assert "user_auth_challenges" in tables
            assert {"referrals", "promo_codes", "promo_redemptions"} <= set(tables)
            assert "generation_presets" in tables
            assert "preset_favorites" in tables
            assert "system_settings" in tables
            assert len(tables) == 21
            command.downgrade(config, "0002_user_auth_challenges")
            tables = inspect(connection).get_table_names()
            assert {"referrals", "promo_codes", "promo_redemptions"}.isdisjoint(tables)
            assert "user_auth_challenges" in tables
            command.downgrade(config, "0001_initial")
            assert "user_auth_challenges" not in inspect(connection).get_table_names()
            assert "users" in inspect(connection).get_table_names()
            command.upgrade(config, "head")
            command.downgrade(config, "base")
            assert inspect(connection).get_table_names() == ["alembic_version"]
    finally:
        engine.dispose()


def test_existing_schema_can_be_stamped_and_upgraded(tmp_path):
    config = Config(str(INI))
    engine = create_engine(f"sqlite:///{tmp_path / 'existing.db'}")
    try:
        with engine.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "0001_initial")
            # Імітуємо існуючу схему до запровадження Alembic.
            connection.execute(text("DELETE FROM alembic_version"))
            command.stamp(config, "0001_initial")
            command.upgrade(config, "head")
            assert "user_auth_challenges" in inspect(connection).get_table_names()
    finally:
        engine.dispose()


def test_postgres_migration_sql_uses_postgres_checks_and_retention_index():
    output = StringIO()
    config = Config(str(INI), output_buffer=output)
    config.set_main_option(
        "sqlalchemy.url", "postgresql://unused:unused@localhost/unused"
    )
    command.upgrade(config, "head", sql=True)
    sql = output.getvalue()
    assert "CREATE TABLE user_auth_challenges" in sql
    assert "CREATE TABLE generation_presets" in sql
    assert "CREATE TABLE system_settings" in sql
    assert "jsonb_typeof(" in sql
    assert "json_type(" not in sql
    assert "CREATE INDEX ix_generations_retention" in sql

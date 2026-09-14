import asyncio

import app.main as main_module


def test_lifespan_skips_database_changes_when_startup_actions_are_disabled(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(main_module.settings, "run_migrations_on_startup", False)
    monkeypatch.setattr(main_module.settings, "seed_demo_data", False)
    monkeypatch.setattr(main_module, "run_migrations", lambda: calls.append("migrate"))
    monkeypatch.setattr(main_module, "seed_db", lambda: calls.append("seed"))

    async def exercise_lifespan():
        async with main_module.lifespan(main_module.app):
            pass

    asyncio.run(exercise_lifespan())

    assert calls == []


def test_lifespan_keeps_local_migration_and_seed_convenience(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(main_module.settings, "run_migrations_on_startup", True)
    monkeypatch.setattr(main_module.settings, "seed_demo_data", True)
    monkeypatch.setattr(main_module, "run_migrations", lambda: calls.append("migrate"))
    monkeypatch.setattr(main_module, "seed_db", lambda: calls.append("seed"))

    async def exercise_lifespan():
        async with main_module.lifespan(main_module.app):
            pass

    asyncio.run(exercise_lifespan())

    assert calls == ["migrate", "seed"]

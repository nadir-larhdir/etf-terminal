# Schema Management Notes

The project currently uses `db/schema.py` plus `scripts/db/initialize_database.py` for schema creation and index management.

Current approach:
- table definitions live in one place: `db/schema.py`
- initialization remains idempotent
- SQLite and Postgres/Supabase both use the same bootstrap flow

Future Alembic adoption:
- use `db/schema.py` as the reference for the initial migration baseline
- move additive schema changes into versioned Alembic revisions
- keep `initialize_database.py` as a development bootstrap until Alembic is introduced fully

This repo is intentionally not migrated to Alembic yet to avoid disrupting the current working initialization scripts.

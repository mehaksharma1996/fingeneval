# ADR 0002: SQLAlchemy with SQLite locally and PostgreSQL in production

**Status:** Prototype-only; retained as historical design context

SQLite gives a credential-free demo and fast tests. SQLAlchemy/Alembic preserve a PostgreSQL migration path. SQLite is not approved for multi-tenant production because it lacks row-level security, operational concurrency, managed backups, and the target isolation controls.

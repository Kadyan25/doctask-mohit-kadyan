from app.config import settings


def get_checkpointer_dsn() -> str:
    """AsyncPostgresSaver wants a plain psycopg DSN, not the
    'postgresql+psycopg://' SQLAlchemy dialect form used elsewhere."""
    return settings.database_url.replace("postgresql+psycopg://", "postgresql://")

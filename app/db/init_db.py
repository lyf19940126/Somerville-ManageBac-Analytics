from app.config import ensure_directories, load_settings
from app.db.models import Base, get_engine


def init_db() -> None:
    settings = load_settings(require_term_id=False)
    ensure_directories()
    engine = get_engine(settings.database_url)
    Base.metadata.create_all(engine)


if __name__ == "__main__":
    init_db()

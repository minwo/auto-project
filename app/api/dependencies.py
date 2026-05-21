from app.repository import CandidateRepository, UnavailableRepository
from app.postgres_repository import create_postgres_repository
from app.settings import load_settings

_repo_instance: CandidateRepository | None = None

def build_repository() -> CandidateRepository:
    settings = load_settings()
    if settings.use_database:
        try:
            return create_postgres_repository(settings.database_url)
        except Exception as exc:
            return UnavailableRepository(str(exc), database_configured=True)
    return CandidateRepository()

def set_repository(repo: CandidateRepository):
    global _repo_instance
    _repo_instance = repo

def get_repository() -> CandidateRepository:
    global _repo_instance
    if _repo_instance is None:
        _repo_instance = build_repository()
    return _repo_instance

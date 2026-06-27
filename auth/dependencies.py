from auth.repository import UserRepository
from auth.service import UserService
from core.database import SessionDep


def get_user_service(session: SessionDep) -> UserService:
    return UserService(UserRepository(session))

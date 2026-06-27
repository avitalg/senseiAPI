import uuid

from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError

from auth.models import AuthType, AuthUser, InvalidCredentialsError, UserRole
from auth.repository import UserRepository

PASSWORD_HASH = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return PASSWORD_HASH.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return PASSWORD_HASH.verify(password, password_hash)
    except (TypeError, UnknownHashError):
        return False


class UserService:
    """Business logic for user management."""

    def __init__(self, repository: UserRepository) -> None:
        self._repository = repository

    async def register_user(
        self,
        *,
        password: str,
        auth_type: AuthType,
        role: UserRole,
        email: str,
        full_name: str | None = None,
    ) -> AuthUser:
        return await self._repository.create(
            password_hash=hash_password(password),
            auth_type=auth_type,
            role=role,
            email=email,
            full_name=full_name,
        )

    async def authenticate_user(self, *, email: str, password: str) -> AuthUser:
        credentials = await self._repository.get_credentials_by_email(email)
        if credentials is None:
            # Work the same time to prevent timing attacks
            hash_password(password)
            raise InvalidCredentialsError()
        if not verify_password(password, credentials.password_hash):
            raise InvalidCredentialsError()
        return credentials.user

    async def get_user_by_id(self, user_id: uuid.UUID) -> AuthUser | None:
        return await self._repository.get_by_user_id(user_id)

    async def change_password(
        self,
        *,
        user_id: uuid.UUID,
        current_password: str,
        new_password: str,
    ) -> AuthUser:
        updated_user = await self._repository.update_password(
            user_id=user_id,
            current_password=current_password,
            new_password_hash=hash_password(new_password),
            password_matches=verify_password,
        )
        if updated_user is None:
            raise InvalidCredentialsError()
        return updated_user

    async def logout(self, *, user_id: uuid.UUID) -> None:
        updated_user = await self._repository.increment_token_version(user_id)
        if updated_user is None:
            raise InvalidCredentialsError()

"""Authentication service for business logic."""

from typing import Optional
from sqlalchemy.orm import Session

from src.repositories import AuthCodeRepository, UserRepository
from src.database.models import User


class AuthService:
    """Service for authentication-related business logic."""
    
    def __init__(self, db_session: Session):
        self.auth_code_repo = AuthCodeRepository(db_session)
        self.user_repo = UserRepository(db_session)
    
    def authenticate_with_code(self, code: str, telegram_user_id: int) -> Optional[User]:
        """Authenticate user with one-time code and link Telegram account."""
        # Get valid auth code
        auth_code = self.auth_code_repo.get_valid_code(code)
        if not auth_code:
            return None
        
        # Get the user
        user = self.user_repo.get_by_id(auth_code.user_id)
        if not user or not user.is_active:
            return None
        
        # Mark code as used
        self.auth_code_repo.mark_as_used(auth_code.id)
        
        # Link Telegram account if not already linked
        if not user.telegram_user_id:
            self.user_repo.update(user.id, telegram_user_id=telegram_user_id)
            user.telegram_user_id = telegram_user_id
        
        return user
    
    def is_user_authenticated(self, telegram_user_id: int) -> bool:
        """Check if user is authenticated (has linked Telegram account)."""
        user = self.user_repo.get_by_telegram_user_id(telegram_user_id)
        return user is not None and user.is_active
    
    def get_authenticated_user(self, telegram_user_id: int) -> Optional[User]:
        """Get authenticated user by Telegram user ID."""
        user = self.user_repo.get_by_telegram_user_id(telegram_user_id)
        if user and user.is_active:
            return user
        return None
    
    def cleanup_expired_codes(self) -> int:
        """Clean up expired auth codes."""
        return self.auth_code_repo.cleanup_expired_codes()


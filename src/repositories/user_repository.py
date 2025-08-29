"""User repository for database operations."""

from typing import Optional
from sqlalchemy.orm import Session

from .base_repository import BaseRepository
from src.database.models import User


class UserRepository(BaseRepository[User]):
    """Repository for User entity operations."""
    
    def __init__(self, db_session: Session):
        super().__init__(db_session, User)
    
    def get_by_username(self, username: str) -> Optional[User]:
        """Get user by username."""
        return self.db_session.query(User).filter(
            User.username == username
        ).first()
    
    def get_by_telegram_user_id(self, telegram_user_id: str) -> Optional[User]:
        """Get user by Telegram user ID."""
        return self.db_session.query(User).filter(
            User.telegram_user_id == telegram_user_id
        ).first()
    
    def create_user(self, username: str, telegram_user_id: str = None) -> User:
        """Create a new user."""
        return self.create(
            username=username,
            telegram_user_id=telegram_user_id
        )
    
    def activate_user(self, user_id) -> Optional[User]:
        """Activate user account."""
        return self.update(user_id, is_active=True)
    
    def deactivate_user(self, user_id) -> Optional[User]:
        """Deactivate user account."""
        return self.update(user_id, is_active=False)


"""User service for business logic."""

import secrets
import string
from typing import Optional
from sqlalchemy.orm import Session

from src.repositories import UserRepository, AuthCodeRepository
from src.database.models import User, AuthCode


class UserService:
    """Service for user-related business logic."""
    
    def __init__(self, db_session: Session):
        self.user_repo = UserRepository(db_session)
        self.auth_code_repo = AuthCodeRepository(db_session)
    
    def create_user_with_code(self, username: str) -> tuple[User, AuthCode]:
        """Create a new user and generate an auth code."""
        # Check if user already exists
        existing_user = self.user_repo.get_by_username(username)
        if existing_user:
            raise ValueError(f"User with username '{username}' already exists")
        
        # Create user
        user = self.user_repo.create_user(username=username)
        
        # Generate auth code
        auth_code = self._generate_auth_code(user.id)
        
        return user, auth_code
    
    def get_user_by_username(self, username: str) -> Optional[User]:
        """Get user by username."""
        return self.user_repo.get_by_username(username)
    
    def get_user_by_telegram_id(self, telegram_user_id: str) -> Optional[User]:
        """Get user by Telegram user ID."""
        return self.user_repo.get_by_telegram_user_id(telegram_user_id)
    
    def link_telegram_account(self, user_id, telegram_user_id: str) -> Optional[User]:
        """Link Telegram account to user."""
        return self.user_repo.update(user_id, telegram_user_id=telegram_user_id)
    
    def _generate_auth_code(self, user_id) -> AuthCode:
        """Generate a unique auth code for user."""
        # Generate a secure random code
        alphabet = string.ascii_letters + string.digits
        code = ''.join(secrets.choice(alphabet) for _ in range(32))
        
        # Ensure uniqueness
        while self.auth_code_repo.get_by_code(code):
            code = ''.join(secrets.choice(alphabet) for _ in range(32))
        
        return self.auth_code_repo.create_auth_code(user_id=user_id, code=code)
    
    def regenerate_auth_code(self, user_id) -> AuthCode:
        """Generate a new auth code for existing user."""
        user = self.user_repo.get_by_id(user_id)
        if not user:
            raise ValueError(f"User with ID '{user_id}' not found")
        
        return self._generate_auth_code(user_id)


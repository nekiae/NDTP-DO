"""Auth code repository for database operations."""

from typing import Optional, List
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_

from .base_repository import BaseRepository
from src.database.models import AuthCode


class AuthCodeRepository(BaseRepository[AuthCode]):
    """Repository for AuthCode entity operations."""
    
    def __init__(self, db_session: Session):
        super().__init__(db_session, AuthCode)
    
    def get_by_code(self, code: str) -> Optional[AuthCode]:
        """Get auth code by code value."""
        return self.db_session.query(AuthCode).filter(
            AuthCode.code == code
        ).first()
    
    def get_valid_code(self, code: str) -> Optional[AuthCode]:
        """Get valid (unused and not expired) auth code."""
        now = datetime.utcnow()
        return self.db_session.query(AuthCode).filter(
            and_(
                AuthCode.code == code,
                AuthCode.is_used == False # noqa: E712
            ),  
            AuthCode.expires_at > now
        ).first()
    
    def get_user_codes(self, user_id, include_used: bool = False) -> List[AuthCode]:
        """Get all codes for a user."""
        query = self.db_session.query(AuthCode).filter(
            AuthCode.user_id == user_id
        )
        
        if not include_used:
            query = query.filter(AuthCode.is_used == False)  # noqa: E712
        
        return query.order_by(AuthCode.created_at.desc()).all()
    
    def create_auth_code(self, user_id, code: str, expires_at: datetime = None) -> AuthCode:
        """Create a new auth code."""
        return self.create(
            user_id=user_id,
            code=code,
            expires_at=expires_at
        )
    
    def mark_as_used(self, code_id) -> Optional[AuthCode]:
        """Mark auth code as used."""
        return self.update(
            code_id,
            is_used=True,
            used_at=datetime.utcnow()
        )
    
    def cleanup_expired_codes(self) -> int:
        """Remove expired codes and return count of deleted codes."""
        now = datetime.utcnow()
        expired_codes = self.db_session.query(AuthCode).filter(
            AuthCode.expires_at < now
        )
        count = expired_codes.count()
        expired_codes.delete()
        self.db_session.commit()
        return count


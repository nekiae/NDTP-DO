"""Base repository with common database operations."""

from abc import ABC
from typing import TypeVar, Generic, Optional, List
from sqlalchemy.orm import Session

T = TypeVar('T')


class BaseRepository(Generic[T], ABC):
    """Abstract base repository implementing common CRUD operations."""
    
    def __init__(self, db_session: Session, model_class):
        self.db_session = db_session
        self.model_class = model_class
    
    def create(self, **kwargs) -> T:
        """Create a new entity."""
        entity = self.model_class(**kwargs)
        self.db_session.add(entity)
        self.db_session.commit()
        self.db_session.refresh(entity)
        return entity
    
    def get_by_id(self, entity_id) -> Optional[T]:
        """Get entity by ID."""
        return self.db_session.query(self.model_class).filter(
            self.model_class.id == entity_id
        ).first()
    
    def get_all(self, skip: int = 0, limit: int = 100) -> List[T]:
        """Get all entities with pagination."""
        return self.db_session.query(self.model_class).offset(skip).limit(limit).all()
    
    def update(self, entity_id, **kwargs) -> Optional[T]:
        """Update entity by ID."""
        entity = self.get_by_id(entity_id)
        if entity:
            for key, value in kwargs.items():
                setattr(entity, key, value)
            self.db_session.commit()
            self.db_session.refresh(entity)
        return entity
    
    def delete(self, entity_id) -> bool:
        """Delete entity by ID."""
        entity = self.get_by_id(entity_id)
        if entity:
            self.db_session.delete(entity)
            self.db_session.commit()
            return True
        return False


"""Database models and connection management for SQLite"""
from sqlalchemy import create_engine, Column, String, Text, Integer, JSON, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from typing import List, Optional, Dict, Any
import json

Base = declarative_base()


class Test(Base):
    """Test model for storing medical tests"""
    __tablename__ = "tests"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False, index=True)
    category = Column(String, nullable=False, index=True)
    synonyms = Column(JSON, default=list)  # Store as JSON array
    embeddings = Column(JSON, default=list)  # Store embeddings as JSON array
    embeddings_updated = Column(Integer, default=0)  # Timestamp to track when embeddings were last updated

    def to_dict(self) -> Dict[str, Any]:
        """Convert test to dictionary format"""
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "synonyms": self.synonyms if isinstance(self.synonyms, list) else [],
            "embeddings": self.embeddings if isinstance(self.embeddings, list) else []
        }


# Database setup
DATABASE_URL = "sqlite:///./medical_tests.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Initialize database and create tables"""
    Base.metadata.create_all(bind=engine)


def get_db() -> Session:
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_db_session() -> Session:
    """Get a database session (for direct use, not dependency injection)"""
    return SessionLocal()


# Database helper functions
class TestRepository:
    """Repository pattern for test operations"""
    
    @staticmethod
    def get_all_tests(db: Session) -> List[Test]:
        """Get all tests"""
        return db.query(Test).all()
    
    @staticmethod
    def get_test_by_id(db: Session, test_id: str) -> Optional[Test]:
        """Get test by ID"""
        return db.query(Test).filter(Test.id == test_id).first()
    
    @staticmethod
    def create_test(db: Session, test_data: Dict[str, Any]) -> Test:
        """Create a new test"""
        test = Test(**test_data)
        db.add(test)
        db.commit()
        db.refresh(test)
        return test
    
    @staticmethod
    def update_test(db: Session, test_id: str, test_data: Dict[str, Any]) -> Optional[Test]:
        """Update an existing test"""
        test = db.query(Test).filter(Test.id == test_id).first()
        if not test:
            return None
        
        for key, value in test_data.items():
            if value is not None:
                setattr(test, key, value)
        
        db.commit()
        db.refresh(test)
        return test
    
    @staticmethod
    def delete_test(db: Session, test_id: str) -> bool:
        """Delete a test"""
        test = db.query(Test).filter(Test.id == test_id).first()
        if not test:
            return False
        
        db.delete(test)
        db.commit()
        return True
    
    @staticmethod
    def get_all_categories(db: Session) -> List[str]:
        """Get unique list of categories"""
        categories = db.query(Test.category).distinct().all()
        return sorted([cat[0] for cat in categories if cat[0]])
    
    @staticmethod
    def update_test_embeddings(db: Session, test_id: str, embeddings: List[List[float]]) -> bool:
        """Update embeddings for a specific test"""
        test = db.query(Test).filter(Test.id == test_id).first()
        if not test:
            return False
        
        test.embeddings = embeddings
        db.commit()
        return True
    
    @staticmethod
    def get_tests_with_embeddings(db: Session) -> List[Dict[str, Any]]:
        """Get all tests with embeddings for matching"""
        tests = db.query(Test).filter(Test.embeddings != None).all()
        # Filter out tests with empty embeddings (None or empty list)
        result = []
        for test in tests:
            if test.embeddings and isinstance(test.embeddings, list) and len(test.embeddings) > 0:
                result.append(test.to_dict())
        return result


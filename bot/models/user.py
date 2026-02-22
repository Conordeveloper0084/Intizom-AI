from sqlalchemy import Column, BigInteger, String, Integer, DateTime, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from database.db import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False)
    full_name = Column(String(255), nullable=True)
    username = Column(String(255), nullable=True)
    streak = Column(Integer, default=0)
    total_score = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_active = Column(DateTime, default=datetime.utcnow)

    plans = relationship("Plan", back_populates="user", cascade="all, delete")
    score_logs = relationship("ScoreLog", back_populates="user", cascade="all, delete")
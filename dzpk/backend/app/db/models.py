"""SQLAlchemy ORM 模型。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class User(Base):
    """用户账号。"""
    __tablename__ = "users"

    id = Column(String(36), primary_key=True)             # UUID
    username = Column(String(20), unique=True, nullable=True)
    password_hash = Column(String(128), nullable=True)
    device_id = Column(String(64), nullable=True)
    chips = Column(Integer, default=10000)
    total_hands = Column(Integer, default=0)
    total_wins = Column(Integer, default=0)
    total_profit = Column(Integer, default=0)
    is_anonymous = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)
    last_login_at = Column(DateTime, default=datetime.now)


class HandHistory(Base):
    """牌局历史记录。"""
    __tablename__ = "hand_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    room_id = Column(String(16), nullable=False, index=True)
    started_at = Column(DateTime, default=datetime.now, nullable=False)
    ended_at = Column(DateTime)
    button_seat = Column(Integer)
    community_cards = Column(String(64))  # 空格分隔字符串
    summary_json = Column(Text)  # 完整快照 JSON

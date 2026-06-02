from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Text, DateTime, func
from sqlalchemy.orm import relationship
from database import Base

class Room(Base):
    __tablename__ = "rooms"

    name = Column(String, primary_key=True, index=True)
    password_hash = Column(String, nullable=False)
    status = Column(String, default="collecting")  # 'collecting', 'completed'
    created_at = Column(DateTime, server_default=func.now())

    participants = relationship("Participant", back_populates="room", cascade="all, delete-orphan")
    confessions = relationship("Confession", back_populates="room", cascade="all, delete-orphan")
    endorsements = relationship("ConfessionEndorsement", back_populates="room", cascade="all, delete-orphan")

class Participant(Base):
    __tablename__ = "participants"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    room_name = Column(String, ForeignKey("rooms.name"), nullable=False)
    name = Column(String, nullable=False)
    has_confessed = Column(Boolean, default=False)

    room = relationship("Room", back_populates="participants")
    confessions_received = relationship("Confession", back_populates="target_participant", cascade="all, delete-orphan")

class Confession(Base):
    __tablename__ = "confessions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    room_name = Column(String, ForeignKey("rooms.name"), nullable=False)
    target_participant_id = Column(Integer, ForeignKey("participants.id"), nullable=False)
    confession_text = Column(Text, nullable=False)

    room = relationship("Room", back_populates="confessions")
    target_participant = relationship("Participant", back_populates="confessions_received")
    endorsements = relationship("ConfessionEndorsement", back_populates="confession", cascade="all, delete-orphan")

class ConfessionEndorsement(Base):
    __tablename__ = "confession_endorsements"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    room_name = Column(String, ForeignKey("rooms.name"), nullable=False)
    confession_id = Column(Integer, ForeignKey("confessions.id"), nullable=False)
    vote = Column(String, nullable=False)  # 'agree', 'not_agree', 'cant_comment'

    room = relationship("Room", back_populates="endorsements")
    confession = relationship("Confession", back_populates="endorsements")


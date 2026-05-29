from datetime import datetime
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from .database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(255), nullable=False)
    username = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, index=True)
    department = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    created_tests = relationship("Test", back_populates="creator")
    assignments = relationship("UserTest", back_populates="user")
    attempts = relationship("TestAttempt", back_populates="user")


class Test(Base):
    __tablename__ = "tests"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    creator = relationship("User", back_populates="created_tests")
    questions = relationship("Question", back_populates="test", cascade="all, delete-orphan")
    assignments = relationship("UserTest", back_populates="test")
    attempts = relationship("TestAttempt", back_populates="test")


class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, index=True)
    test_id = Column(Integer, ForeignKey("tests.id"), nullable=False, index=True)
    text = Column(Text, nullable=False)

    test = relationship("Test", back_populates="questions")
    answer_options = relationship(
        "AnswerOption", back_populates="question", cascade="all, delete-orphan"
    )
    attempt_answers = relationship("TestAttemptAnswer", back_populates="question")

    @property
    def allows_multiple_answers(self) -> bool:
        return sum(1 for option in self.answer_options if option.is_correct) > 1


class AnswerOption(Base):
    __tablename__ = "answer_options"

    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False, index=True)
    text = Column(Text, nullable=False)
    is_correct = Column(Boolean, default=False, nullable=False)

    question = relationship("Question", back_populates="answer_options")
    attempt_answers = relationship("TestAttemptAnswer", back_populates="answer_option")


class UserTest(Base):
    __tablename__ = "user_tests"
    __table_args__ = (UniqueConstraint("user_id", "test_id", name="uq_user_test"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    test_id = Column(Integer, ForeignKey("tests.id"), nullable=False, index=True)
    assigned_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="assignments")
    test = relationship("Test", back_populates="assignments")


class TestAttempt(Base):
    __tablename__ = "test_attempts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    test_id = Column(Integer, ForeignKey("tests.id"), nullable=False, index=True)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    finished_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    score_percent = Column(Float, nullable=False)
    passed = Column(Boolean, default=False, nullable=False)

    user = relationship("User", back_populates="attempts")
    test = relationship("Test", back_populates="attempts")
    answers = relationship(
        "TestAttemptAnswer", back_populates="attempt", cascade="all, delete-orphan"
    )


class TestAttemptAnswer(Base):
    __tablename__ = "test_attempt_answers"

    id = Column(Integer, primary_key=True, index=True)
    attempt_id = Column(Integer, ForeignKey("test_attempts.id"), nullable=False, index=True)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False, index=True)
    answer_option_id = Column(Integer, ForeignKey("answer_options.id"), nullable=False, index=True)

    attempt = relationship("TestAttempt", back_populates="answers")
    question = relationship("Question", back_populates="attempt_answers")
    answer_option = relationship("AnswerOption", back_populates="attempt_answers")

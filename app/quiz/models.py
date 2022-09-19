from dataclasses import dataclass
from json import dumps

from sqlalchemy.orm import relationship, backref

from app.store.database.sqlalchemy_base import (
    db,
    Column,
    BigInteger,
    String,
    Boolean,
    ForeignKey,
)


@dataclass
class Theme:
    id: int | None
    title: str


@dataclass
class Question:
    id: int | None
    title: str
    theme_id: int
    answers: list["Answer"]


@dataclass
class Answer:
    title: str
    is_correct: bool


class ThemeModel(db):
    __tablename__ = "themes"
    id = Column(BigInteger, primary_key=True)
    title = Column(String, unique=True)
    questions = relationship(
        "QuestionModel",
        cascade="all, delete",
        back_populates="theme",
        passive_deletes=True,
    )

    def __repr__(self):
        r = {"Theme": {"id": self.id, "title": self.title}}
        return dumps(r)


class QuestionModel(db):
    __tablename__ = "questions"
    id = Column(BigInteger, primary_key=True)
    title = Column(String, unique=True)
    theme_id = Column(
        BigInteger, ForeignKey("themes.id", ondelete="CASCADE"), nullable=False
    )
    theme = relationship(ThemeModel, back_populates="questions")
    answers = relationship(
        "AnswerModel",
        cascade="all, delete",
        back_populates="question",
        passive_deletes=True,
    )

    def __repr__(self):
        r = {
            "Question": {"id": self.id, "title": self.title, "theme_id": self.theme_id}
        }
        return dumps(r)


class AnswerModel(db):
    __tablename__ = "answers"
    id = Column(BigInteger, primary_key=True)
    question_id = Column(BigInteger, ForeignKey(QuestionModel.id, ondelete="CASCADE"))
    question = relationship(QuestionModel, back_populates="answers")
    title = Column(String, unique=True)
    is_correct = Column(Boolean)

    def __repr__(self):
        r = {"Answer": {"title": self.title, "is_correct": self.title}}
        return dumps(r)

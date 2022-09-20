from dataclasses import dataclass
import datetime
from json import dumps

from sqlalchemy.orm import relationship, backref

from app.store.database.sqlalchemy_base import (
    db,
    Column,
    BigInteger,
    String,
    Boolean,
    ForeignKey,
    DateTime,
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


@dataclass
class Users:
    id: int
    full_name: str
    vk_id: str
    created_at: str
    statistic_id: int


@dataclass
class Statistics:
    id: int
    total_wins: int
    total_losses: int
    total_draw: int


@dataclass
class GameUser:
    id: int
    user_id: int
    cards: str
    status: str
    current_game_id: int


@dataclass
class CurrentGame:
    id: int
    host: str
    queue: int
    state: int
    cards: str
    chat_id: int


@dataclass
class Chat:
    id: int
    chat_id: int


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
        back_populates="question",
        passive_deletes=True,
        cascade="all, delete",
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


class UsersModel(db):
    __tablename__ = "users"
    id = Column(BigInteger, primary_key=True)
    full_name = Column(String)
    vk_id = Column(String, unique=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    statistic_id = Column(BigInteger, ForeignKey("statistics.id", ondelete="CASCADE"))
    statistic = relationship("StatisticsModel", backref=backref("users", uselist=False))

    def __repr__(self):
        r = {
            "Users": {
                "id": self.id,
                "full_name": self.full_name,
                "vk_id": self.vk_id,
                "created_at": str(self.created_at),
                "statistic_id": self.statistic_id,
            }
        }
        return dumps(r)


class StatisticsModel(db):
    __tablename__ = "statistics"
    id = Column(BigInteger, primary_key=True)
    total_wins = Column(BigInteger, default=0)
    total_losses = Column(BigInteger, default=0)
    total_draw = Column(BigInteger, default=0)

    def __repr__(self):
        r = {
            "Statistics": {
                "id": self.id,
                "total_wins": self.total_wins,
                "total_losses": self.total_losses,
                "total_draw": self.total_draw,
            }
        }
        return dumps(r)


class GameUserModel(db):
    __tablename__ = "game_user"
    id = Column(BigInteger, primary_key=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"))
    user = relationship("UsersModel", backref=backref("game_user", uselist=False))
    users = relationship("CurrentGameModel", back_populates="users_id")
    cards = Column(String, default="")
    status = Column(String, default="")
    current_game_id = Column(BigInteger, ForeignKey("current_game.id"))
    current_game = relationship(
        "CurrentGameModel", backref=backref("game_user", uselist=False)
    )

    def __repr__(self):
        r = {
            "GameUser": {
                "id": self.id,
                "user_id": self.user_id,
                "cards": self.cards,
                "status": self.status,
                "current_game_id": self.current_game_id,
            }
        }
        return dumps(r)


class CurrentGameModel(db):
    __tablename__ = "current_game"
    id = Column(BigInteger, primary_key=True)
    host = Column(String)
    queue = Column(BigInteger, default=0)
    state = Column(BigInteger, default=0)
    cards = Column(String, default="")
    users_id = relationship(GameUserModel, back_populates="users")
    chat_id = Column(BigInteger, ForeignKey("chat.id", ondelete="CASCADE"))
    chat = relationship("ChatModel", backref=backref("current_game", uselist=False))

    def __repr__(self):
        r = {
            "CurrentGame": {
                "id": self.id,
                "host": self.host,
                "queue": self.queue,
                "state": self.state,
                "cards": self.cards,
                "chat_id": self.chat_id,
            }
        }
        return dumps(r)


class ChatModel(db):
    __tablename__ = "chat"
    id = Column(BigInteger, primary_key=True)
    chat_id = Column(BigInteger)

    def __repr__(self):
        r = {"Chat": {"id": self.id, "chat_id": self.chat_id}}
        return dumps(r)

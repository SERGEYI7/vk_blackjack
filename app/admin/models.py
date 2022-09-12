from dataclasses import dataclass
from hashlib import sha256
from typing import Optional
from json import dumps

from app.store.database.sqlalchemy_base import db, Column, BigInteger, String


@dataclass
class Admin:
    id: int
    email: str
    password: Optional[str] = None

    def is_password_valid(self, password: str):
        return self.password == sha256(password.encode()).hexdigest()

    @classmethod
    def from_session(cls, session: Optional[dict]) -> Optional["Admin"]:
        return cls(id=session["admin"]["id"], email=session["admin"]["email"])


class AdminModel(db):
    __tablename__ = "admins"
    # id = Column(BigInteger, primary_key=True, autoincrement=True)
    id = Column(BigInteger, primary_key=True)
    email = Column(String(length=2048))
    password = Column(String(length=2048))

    def __repr__(self):
        r = {"Admin": {"id": self.id, "email": self.email, "password": self.password}}
        return dumps(r)

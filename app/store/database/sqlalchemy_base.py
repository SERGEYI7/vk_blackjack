from sqlalchemy.orm import declarative_base
from sqlalchemy import (
    Column,
    BigInteger,
    VARCHAR,
    TEXT,
    String,
    Boolean,
    ForeignKey,
    DateTime,
)

db = declarative_base()

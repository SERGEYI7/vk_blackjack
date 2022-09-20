from dataclasses import dataclass


@dataclass
class UpdateObject:
    id: int
    user_id: int
    body: str


@dataclass
class Update:
    type: str
    object: UpdateObject


@dataclass
class Message:
    user_id: int
    text: str


@dataclass
class Users:
    id: int
    full_name: str
    vk_id: str
    created_at: str
    statistic_id: int


@dataclass
class Statistic:
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
    state: int
    cards: str
    users_id: int
    chat_id: int


@dataclass
class Chat:
    id: int
    chat_id: int

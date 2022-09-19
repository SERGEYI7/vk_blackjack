from dataclasses import dataclass, field


@dataclass
class UpdateObject:
    id: int
    user_id: int
    body: dict


@dataclass
class Update:
    type: str
    object: UpdateObject


@dataclass
class Message:
    user_id: field(default_factory=int)
    text: field(default_factory=str)
    peer_id: int
    chat_id: int
    kwargs: field(default_factory=dict)

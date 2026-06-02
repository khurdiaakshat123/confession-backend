from pydantic import BaseModel, Field
from typing import List, Dict

class RoomCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=50)
    password: str = Field(..., min_length=4)
    participant_names: List[str] = Field(..., min_items=2)

class RoomVerify(BaseModel):
    name: str
    password: str

class ParticipantResponse(BaseModel):
    id: int
    name: str
    has_confessed: bool

    class Config:
        from_attributes = True

class RoomStatusResponse(BaseModel):
    name: str
    status: str  # 'collecting', 'completed'
    participants: List[ParticipantResponse]

    class Config:
        from_attributes = True

class SingleConfessionInput(BaseModel):
    target_id: int
    confession_text: str

class ConfessionsSubmitRequest(BaseModel):
    from_participant_id: int
    confessions: List[SingleConfessionInput]

class ConfessionResultItem(BaseModel):
    id: int
    confession_text: str
    agree_count: int
    not_agree_count: int
    cant_comment_count: int

    class Config:
        from_attributes = True

class RoomResultsResponse(BaseModel):
    room_name: str
    status: str
    results: Dict[str, List[ConfessionResultItem]]

class ParticipantCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)

class SingleEndorsementInput(BaseModel):
    confession_id: int
    vote: str

class EndorsementSubmitRequest(BaseModel):
    votes: List[SingleEndorsementInput]

# pyrefly: ignore [missing-import]
from sqlmodel import SQLModel, Field, Relationship
from typing import List, Optional
import uuid

class Election(SQLModel, table=True):
    __tablename__ = "elections"
    year: int = Field(unique=True, primary_key=True)
    total_constituencies: Optional[int] = None
    total_electorate: Optional[int] = None
    total_votes_polled: Optional[int] = None
    # Add other fields if needed

class Constituency(SQLModel, table=True):
    __tablename__ = "constituencies"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    election_year: int = Field(foreign_key="elections.year")
    constituency_name: str
    constituency_number: Optional[str] = None
    electorate: Optional[int] = None
    votes_polled: Optional[int] = None
    nota_votes: Optional[int] = None
    candidates: List["Candidate"] = Relationship(back_populates="constituency")

class Candidate(SQLModel, table=True):
    __tablename__ = "candidates"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    constituency_id: uuid.UUID = Field(foreign_key="constituencies.id")
    name: str = Field(index=True)
    party: str
    votes: int
    vote_percentage: Optional[float] = None
    rank: Optional[int] = None
    sex: Optional[str] = None
    constituency: Optional[Constituency] = Relationship(back_populates="candidates")

    @property
    def normalized_name(self) -> str:
        return self.name.lower().replace(".", "").replace(" ", "").strip()

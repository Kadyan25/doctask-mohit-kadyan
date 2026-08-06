import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class PileCreate(BaseModel):
    name: str
    watch_folder_path: Optional[str] = None


class PileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    watch_folder_path: Optional[str]
    created_at: datetime

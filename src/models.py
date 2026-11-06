from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from puppet import YTPuppet 

@dataclass
class Video():
    id : str
    title : Optional[str] = None
    channel : Optional[str] = None
    channel_id : Optional[str] = None
    description : Optional[str] = None
    tags : Optional[list[str]] = None
    category : Optional[str] = None
    blacklist : Optional[bool] = False
    L : Optional[int] = None
    R : Optional[int] = None
    train : Optional[bool] = None
    comments : Optional[list[str]] = None

    def is_metadata_empty(self) -> bool:
        attrs = (self.title, self.description, self.tags, self.comments)
        return all(a in (None, "", []) for a in attrs)

    def __str__(self):
        return f"Video ID: {self.id}"

@dataclass
class Watch():
    state : str
    puppet : "YTPuppet"
    puppet_cond : str
    depth : int
    video : Video
    recs : list[Video]
    errors : list[str]
    source : Literal["homepage", "video"]
    watch_time : float
    topics : Optional[list[str]] = None

    def __str__(self):
        return f"{self.video}. Depth: {self.depth}, puppet state: {self.state}"
    
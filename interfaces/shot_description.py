"""Shot description data model for video generation."""
from pydantic import BaseModel


class ShotDescription(BaseModel):
    """Describes a single shot within a scene for detailed video generation."""
    idx: int
    is_last: bool
    visual_desc: str
    variation_type: str = "medium"  # large / medium / small
    ff_desc: str = ""   # first frame description
    lf_desc: str = ""   # last frame description
    motion_desc: str = ""  # camera/action motion description
    audio_desc: str = ""  # audio/sound description

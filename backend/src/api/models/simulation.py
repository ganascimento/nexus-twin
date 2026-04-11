from pydantic import BaseModel, Field


class SpeedUpdate(BaseModel):
    tick_interval_seconds: int = Field(gt=0)

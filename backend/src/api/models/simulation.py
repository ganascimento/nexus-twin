from pydantic import BaseModel


class SpeedUpdate(BaseModel):
    tick_interval_seconds: int

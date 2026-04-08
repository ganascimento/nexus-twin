from pydantic import BaseModel, field_validator


class AgentDecisionBase(BaseModel):
    action: str
    reasoning_summary: str

    @field_validator("reasoning_summary")
    @classmethod
    def reasoning_summary_not_empty(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("reasoning_summary cannot be empty or whitespace-only")
        return stripped

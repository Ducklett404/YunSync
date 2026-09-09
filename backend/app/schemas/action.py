from pydantic import BaseModel, ConfigDict


class ActionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    code: str
    title: str
    category: str
    description: str
    evidence_summary: str
    suitable_if: str
    safety_note: str
    primary_metric: str
    risk_level: str
    score: float
    rank_reason: str


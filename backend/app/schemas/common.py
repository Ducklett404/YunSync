from pydantic import BaseModel


class ApiMessage(BaseModel):
    message: str


class HealthStatus(BaseModel):
    status: str
    service: str
    environment: str


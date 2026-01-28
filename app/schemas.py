from pydantic import BaseModel, HttpUrl
from typing import Optional, List


class AppOnboardRequest(BaseModel):
    type: str                # backend / frontend / infra / ml / vcs
    framework: Optional[str] # fastapi / spring / node / etc
    url: HttpUrl
    env: Optional[str] = "prod"


class MonitoringDecision(BaseModel):
    monitorable: bool
    strategy: Optional[str]
    confidence: str
    details: str
    next_steps: Optional[List[str]] = None

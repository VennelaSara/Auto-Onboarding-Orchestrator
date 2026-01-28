from fastapi import FastAPI
from app.schemas import AppOnboardRequest, MonitoringDecision
from app.permission import detect_monitoring_strategy, apply_monitoring_strategy
from app.redis_client import save_monitoring_strategy, get_monitoring_strategy

app = FastAPI(
    title="Auto-Monitoring Orchestrator",
    description="Automatic onboarding and monitoring strategy detection",
    version="1.0.0"
)


@app.post("/onboard", response_model=MonitoringDecision)
def onboard_app(app_data: AppOnboardRequest):
    """
    Onboard a new application:
    - Detect its monitoring strategy
    - Apply the appropriate monitoring actions
    - Persist the decision in Redis
    """
    payload = app_data.model_dump()
    payload["url"] = str(payload["url"])

    # Step 1: Detect monitoring strategy
    decision = detect_monitoring_strategy(payload)

    # Step 2: Apply monitoring actions
    action_result = apply_monitoring_strategy(payload, decision)
    print("Action Result:", action_result)  # debug logs

    # Step 3: Persist strategy to Redis
    save_monitoring_strategy(payload["url"], decision)

    return decision


@app.get("/strategy/{app_url}", response_model=MonitoringDecision)
def get_saved_strategy(app_url: str):
    """
    Retrieve the saved monitoring strategy for an application from Redis
    """
    saved = get_monitoring_strategy(app_url)
    if not saved:
        return {"monitorable": False, "strategy": None, "confidence": "none", "details": "No strategy found"}
    return saved

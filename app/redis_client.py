import redis
from app.config import settings

# Connect to Redis
r = redis.Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=0,
    decode_responses=True  # store everything as string
)

def _serialize_strategy(strategy_info: dict) -> dict:
    """
    Convert all values in strategy_info to strings.
    Redis HSET only supports str, int, float, bytes.
    """
    serialized = {}
    for k, v in strategy_info.items():
        if isinstance(v, bool):
            serialized[k] = str(v)  # True -> "True", False -> "False"
        elif v is None:
            serialized[k] = "None"
        else:
            serialized[k] = str(v)
    return serialized

def save_monitoring_strategy(app_name: str, strategy_info: dict):
    """Save strategy info for an app"""
    try:
        serialized_info = _serialize_strategy(strategy_info)
        r.hset(f"app:{app_name}", mapping=serialized_info)
    except redis.ConnectionError as e:
        print(f"Redis connection error: {e}")
        raise
    except redis.RedisError as e:
        print(f"Redis error: {e}")
        raise

def get_monitoring_strategy(app_name: str):
    """Retrieve strategy info for an app"""
    try:
        data = r.hgetall(f"app:{app_name}")
        if not data:
            return None
        # Optional: convert "True"/"False" back to bool
        for k, v in data.items():
            if v == "True":
                data[k] = True
            elif v == "False":
                data[k] = False
            elif v == "None":
                data[k] = None
            elif v.isdigit():
                data[k] = int(v)
            else:
                try:
                    data[k] = float(v)
                except ValueError:
                    pass
        return data
    except redis.ConnectionError as e:
        print(f"Redis connection error: {e}")
        raise
    except redis.RedisError as e:
        print(f"Redis error: {e}")
        raise

def delete_monitoring_strategy(app_name: str):
    """Remove an app's monitoring info"""
    try:
        r.delete(f"app:{app_name}")
    except redis.ConnectionError as e:
        print(f"Redis connection error: {e}")
        raise
    except redis.RedisError as e:
        print(f"Redis error: {e}")
        raise

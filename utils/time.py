
from datetime import datetime, timezone

def generate_timestamp():
    return datetime.now(timezone.utc)

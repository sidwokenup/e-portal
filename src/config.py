import json
import os
from typing import List, Optional
from pydantic import BaseModel, Field

class UserCredential(BaseModel):
    user_id: str = Field(..., description="Unique identifier for the user profile")
    pan_number: str = Field(..., description="PAN / Aadhaar / User ID for login")
    password: str = Field(..., description="E-filing account password")

def load_credentials(config_path: str = "config/users.json", target_user_id: Optional[str] = None) -> List[UserCredential]:
    """
    Load credentials with container & multi-user support:
    1. If PAN_NUMBER and PASSWORD env vars are present, returns that single container user.
    2. If TARGET_USER_ID env var (or arg) is present, filters config/users.json for that user.
    3. Otherwise loads all users from config/users.json.
    """
    # 1. Direct environment variable injection (ideal for dedicated containers)
    env_pan = os.getenv("PAN_NUMBER")
    env_pwd = os.getenv("PASSWORD")
    if env_pan and env_pwd:
        user_id = os.getenv("USER_ID", "docker_user")
        return [UserCredential(user_id=user_id, pan_number=env_pan, password=env_pwd)]

    # 2. Check TARGET_USER_ID from env or parameter
    target_id = target_user_id or os.getenv("TARGET_USER_ID")

    # 3. Load from config file
    if not os.path.exists(config_path):
        return []

    with open(config_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    credentials = [UserCredential(**item) for item in data]

    if target_id:
        filtered = [c for c in credentials if c.user_id == target_id]
        if not filtered:
            raise ValueError(f"User ID '{target_id}' not found in {config_path}")
        return filtered

    return credentials


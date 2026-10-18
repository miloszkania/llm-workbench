import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv


class EnvironmentConfigError(RuntimeError):
    pass


@dataclass
class EnvironmentConfig:
    openrouter_api_key: str
    db_path: Path


@lru_cache(maxsize=1)
def get_env_config() -> EnvironmentConfig:
    # the project root is two directories above this package
    project_root = Path(__file__).resolve().parents[2]

    load_dotenv(project_root / ".env")

    env_values = {
        "OPENROUTER_API_KEY": os.getenv("OPENROUTER_API_KEY"),
        "DB_PATH": os.getenv("DB_PATH"),
    }

    missing_values = [name for name, value in env_values.items() if not value or not value.strip()]

    if len(missing_values) > 0:
        raise EnvironmentConfigError(f"The following environment variables are missing: {', '.join(missing_values)}")

    retrieved_config = EnvironmentConfig(
        openrouter_api_key=env_values["OPENROUTER_API_KEY"].strip(),
        db_path=project_root / env_values["DB_PATH"].strip(),
    )

    return retrieved_config

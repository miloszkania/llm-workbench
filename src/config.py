import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


class EnvironmentConfigError(RuntimeError):
    pass

@dataclass
class EnvironmentConfig:
    openrouter_api_key: str
    db_path: Path


def get_env_config() -> EnvironmentConfig:
    project_root = Path(__file__).resolve().parent.parent

    load_dotenv(f"{project_root}/.env")

    env_values = {
        "openrouter_api_key": os.getenv("OPENROUTER_API_KEY"),
        "db_path": os.getenv("DB_PATH"),
    }

    missing_values = [
        name for name, value in env_values.items() if not value
    ]

    if len(missing_values) > 0:
        raise EnvironmentConfigError(f"The following environment variables are missing: {", ".join(missing_values)}")

    retrieved_config = EnvironmentConfig(
        openrouter_api_key = env_values["openrouter_api_key"],
        db_path = Path(env_values["db_path"]),
    )

    return retrieved_config
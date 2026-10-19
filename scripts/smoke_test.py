"""Headless smoke test: renders every page through main.py and fails on uncaught exceptions.

By default, it runs isolated, without `.env` or network access (e.g. in CI): the app uses a temporary database
seeded with demo data, and every OpenRouter request fails, so the pages also have to handle an unreachable API.
With `--live`, it uses the database and OpenRouter key from `.env` instead.
Pages are only rendered, nothing is submitted.

Run from the project root: python3 scripts/smoke_test.py [--live]
"""

import argparse
import os
import sys
import tempfile
import uuid
from contextlib import ExitStack
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

from streamlit.testing.v1 import AppTest

from llm_workbench import db, records
from llm_workbench.db.default_judge_config import DEFAULT_JUDGE_CONFIG_ID
from llm_workbench.errors import OpenRouterRequestError
from llm_workbench.llm import openrouter_api

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def seed_demo_data() -> int:
    # one prompt with a judged run of two responses, so the pages have something to show. returns the prompt id
    prompt_id = records.save_prompt("Write a short poem about the sea.", "You are a poet.", ["creative"])
    run_id = uuid.uuid4().hex

    for response, manual_label in (("The waves roll in...", "success"), ("I'd rather not.", "refusal")):
        interaction_id = db.interactions.insert_interaction(
            {
                "prompt_id": prompt_id,
                "run_id": run_id,
                "time": str(datetime.now()),
                "model": "demo/target-model",
                "response": response,
                "duration": str(timedelta(seconds=3)),
                "token_usage": 50,
                "price": 0.0001,
            }
        )
        db.interactions.set_interaction_label(interaction_id, manual_label)
        db.judges.insert_judge_result(
            {
                "interaction_id": interaction_id,
                "judge_config_id": DEFAULT_JUDGE_CONFIG_ID,
                "judge_model": "demo/judge-model",
                "label": manual_label,
                "explanation": None,
                "time": str(datetime.now()),
                "duration": str(timedelta(seconds=1)),
                "price": 0.00001,
            }
        )

    return prompt_id


def unreachable_openrouter(*_args, **_kwargs):
    raise OpenRouterRequestError("OpenRouter is not reachable in the smoke test.", kind="network", original_error=None)


def render_pages(prompt_id: int) -> bool:
    # renders every page, returns whether any of them raised an exception
    failed = False

    for page in sorted((PROJECT_ROOT / "pages").glob("*.py")):
        app = AppTest.from_file(str(PROJECT_ROOT / "main.py"), default_timeout=60).run()

        # the experiment results page needs a prompt id, otherwise it redirects
        if page.name == "experiment_results.py":
            app.query_params["prompt"] = str(prompt_id)

        app.switch_page(f"pages/{page.name}").run()
        print(f"{page.name:30} exceptions={len(app.exception)} elements={len(app.main.children)}")

        for exception in app.exception:
            failed = True
            print(f"    {exception.value}")

    return failed


def main() -> int:
    # exit code: 1 if any render failed, 0 otherwise
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--live", action="store_true", help="use the database and OpenRouter key from .env")
    live = parser.parse_args().live

    if live:
        return 1 if render_pages(prompt_id=1) else 0

    with tempfile.TemporaryDirectory() as temp_dir, ExitStack() as patches:
        # environment variables take precedence over `.env`, so the local database and key stay untouched
        patches.enter_context(
            mock.patch.dict(
                os.environ,
                {"OPENROUTER_API_KEY": "smoke-test-key", "DB_PATH": str(Path(temp_dir) / "smoke_test.db")},
            )
        )
        patches.enter_context(mock.patch.object(openrouter_api, "_safe_run", side_effect=unreachable_openrouter))

        return 1 if render_pages(seed_demo_data()) else 0


if __name__ == "__main__":
    sys.exit(main())

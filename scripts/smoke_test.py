"""Headless smoke test: renders every page through main.py and fails on uncaught exceptions.

Uses the database and OpenRouter key from `.env`. Pages are only rendered, nothing is submitted.
Run from the project root: python3 scripts/smoke_test.py
"""
import sys
from pathlib import Path

from streamlit.testing.v1 import AppTest

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    failed = False

    for page in sorted((PROJECT_ROOT / "pages").glob("*.py")):
        app = AppTest.from_file(str(PROJECT_ROOT / "main.py"), default_timeout=60).run()

        # the experiment results page needs a prompt id, otherwise it redirects
        if page.name == "experiment_results.py":
            app.query_params["prompt"] = "1"

        app.switch_page(f"pages/{page.name}").run()
        print(f"{page.name:30} exceptions={len(app.exception)} elements={len(app.main.children)}")

        for exception in app.exception:
            failed = True
            print(f"    {exception.value}")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

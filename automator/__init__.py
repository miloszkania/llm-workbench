"""src package for the pipeline project.

This package re-exports the core modules so that Streamlit pages can
import e.g. `from src import database` regardless of the current working directory.
"""

__all__ = [
    "prompt_generator",
    "prompt_sender",
]

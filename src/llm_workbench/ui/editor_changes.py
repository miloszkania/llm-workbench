from collections.abc import Mapping
from typing import Any

import pandas as pd

# helpers for the change state of `st.data_editor`, which refers to rows by their position in the edited table


def has_changes(changes: Mapping[str, Any]) -> bool:
    return any(changes.get(kind) for kind in ("edited_rows", "deleted_rows", "added_rows"))


def deleted_ids(changes: Mapping[str, Any], table: pd.DataFrame) -> list[int]:
    return [int(table.iloc[row_idx]["id"]) for row_idx in changes.get("deleted_rows", [])]


def edited_rows_by_id(changes: Mapping[str, Any], table: pd.DataFrame) -> dict[int, dict[str, Any]]:
    return {
        int(table.iloc[int(row_idx)]["id"]): edited_columns
        for row_idx, edited_columns in changes.get("edited_rows", {}).items()
    }

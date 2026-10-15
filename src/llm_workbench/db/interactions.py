import json
from typing import Any, Literal

from llm_workbench.db.connection import fetch_all, run_sqlite_command


def insert_interaction(data: dict[str, Any]) -> int:
    inserted_interaction_id = run_sqlite_command(
        """
        insert into interactions
            (time, model, prompt, system_prompt, categories, response, duration, token_usage, price)
        values (?, ?, ?, ?, ?, ?, ?, ?, ?);
        """,
        (
            data["time"],
            data["model"],
            data["prompt"],
            data["system_prompt"],
            data["categories"],
            data["response"],
            data["duration"],
            data["token_usage"],
            data["price"],
        ),
    )

    if inserted_interaction_id is None:
        raise RuntimeError("Inserting an interaction did not work!")

    return inserted_interaction_id


def get_interaction_by_id(interaction_id: int) -> list[dict[str, Any]]:
    return fetch_all(
        """
        select * from interactions
            where id = ?
        """,
        [interaction_id],
    )


def delete_interaction(interaction_id: int) -> None:
    run_sqlite_command(
        """
        delete from interactions
        where id = ?
        """,
        [interaction_id],
    )


def get_all_interactions() -> list[dict[str, Any]]:
    return fetch_all("""
        select * from interactions;
    """)


def modify_interaction(
    interaction_id: int,
    column: Literal["manual_label", "categories"],
    new_value: object,
) -> None:
    if column in ["manual_label", "categories"]:  # only allowed columns
        run_sqlite_command(
            f"""
            update interactions
                set {column} = ? -- column is already filtered, so it's injection-safe
                where id = ?
            """,
            (
                new_value,
                int(interaction_id),
            ),
        )


def set_interaction_label(
    interaction_id: int,
    label: Literal["success", "refusal", "unclear"] | None,
) -> None:
    modify_interaction(interaction_id, "manual_label", label)


def set_interaction_categories(
    interaction_id: int,
    categories: list[str] | None,
) -> None:
    modify_interaction(
        interaction_id, "categories", json.dumps(categories, ensure_ascii=False)
    )

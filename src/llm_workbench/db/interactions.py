from typing import Any, Literal

from llm_workbench.db.connection import fetch_all, run_sqlite_command

# interactions together with the prompt they were sent with
SELECT_INTERACTIONS_WITH_PROMPTS = """
    select
        interactions.*,
        prompts.title as prompt_title,
        prompts.prompt,
        prompts.system_prompt,
        prompts.categories
    from interactions
        join prompts on prompts.id = interactions.prompt_id
"""


def insert_interaction(data: dict[str, Any]) -> int:
    inserted_interaction_id = run_sqlite_command(
        """
        insert into interactions
            (prompt_id, run_id, time, model, response, duration, token_usage, price)
        values (?, ?, ?, ?, ?, ?, ?, ?);
        """,
        (
            data["prompt_id"],
            data["run_id"],
            data["time"],
            data["model"],
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
        f"""
        {SELECT_INTERACTIONS_WITH_PROMPTS}
            where interactions.id = ?
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
    return fetch_all(SELECT_INTERACTIONS_WITH_PROMPTS)


def set_interaction_label(
    interaction_id: int,
    label: Literal["success", "refusal", "unclear"] | None,
) -> None:
    run_sqlite_command(
        """
        update interactions
            set manual_label = ?
            where id = ?
        """,
        (label, int(interaction_id)),
    )


def get_interactions_by_prompt(prompt_id: int) -> list[dict[str, Any]]:
    return fetch_all(
        f"""
        {SELECT_INTERACTIONS_WITH_PROMPTS}
            where interactions.prompt_id = ?
            order by interactions.time, interactions.id
        """,
        (prompt_id,),
    )

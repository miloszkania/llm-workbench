from typing import Any, Literal

from llm_workbench.db.connection import fetch_all, fetch_one, run_sqlite_command


def insert_preset(data: dict[str, Any]) -> int:
    inserted_prompt_id = run_sqlite_command(
        """
        insert into presets (prompt, system_prompt, categories)
            values (?, ?, ?);
        """,
        (data["prompt"], data["system_prompt"], data["categories"]),
    )

    if inserted_prompt_id is None:
        raise RuntimeError("Inserting a prompt did not work!")

    return inserted_prompt_id


def delete_preset(preset_id: int) -> None:
    run_sqlite_command(
        """
        delete from presets
        where id = ?
        """,
        [preset_id],
    )


def modify_preset(
    preset_id: int,
    column: Literal["categories", "prompt", "system_prompt"],
    new_value: object,
) -> None:
    if column in ["categories", "prompt", "system_prompt"]:  # only allowed columns
        run_sqlite_command(
            f"""
            update presets
                set {column} = ? -- column is already filtered, so it's injection-safe
                where id = ?
            """,
            (
                new_value,
                int(preset_id),
            ),
        )


def get_all_presets() -> list[dict[str, Any]]:
    return fetch_all("""
        select * from presets;
    """)


def get_preset_id_by_content(
    prompt: str,
    system_prompt: str | None,
    categories: str | None,
) -> int | None:
    result = fetch_one(
        """
        select id from presets
            where prompt = ?
            and system_prompt is ?
            and categories is ?
            limit 1
        """,
        (prompt, system_prompt, categories),
    )
    return result["id"] if result is not None else None

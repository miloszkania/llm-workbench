from typing import Any

from llm_workbench.db.connection import fetch_all, fetch_one, run_sqlite_command


def upsert_prompt(
    prompt: str,
    system_prompt: str,
    categories: str | None,
) -> int:
    # an existing prompt keeps its categories unless new ones are passed
    result = fetch_one(
        """
        insert into prompts (prompt, system_prompt, categories)
            values (?, ?, ?)
            on conflict (prompt, system_prompt)
                do update set categories = coalesce(excluded.categories, prompts.categories)
            returning id
        """,
        (prompt, system_prompt, categories),
    )

    if result is None:
        raise RuntimeError("Saving a prompt did not work!")

    return result["id"]


def get_prompt_by_id(prompt_id: int) -> dict[str, Any] | None:
    return fetch_one(
        """
        select * from prompts
            where id = ?
        """,
        (prompt_id,),
    )


def get_all_prompts() -> list[dict[str, Any]]:
    return fetch_all("""
        select * from prompts;
    """)


def set_prompt_categories(prompt_id: int, categories: str | None) -> None:
    run_sqlite_command(
        """
        update prompts
            set categories = ?
            where id = ?
        """,
        (categories, prompt_id),
    )


def set_prompt_title(prompt_id: int, title: str | None) -> None:
    run_sqlite_command(
        """
        update prompts
            set title = ?
            where id = ?
        """,
        (title, prompt_id),
    )


def delete_prompt(prompt_id: int) -> None:
    run_sqlite_command(
        """
        delete from prompts
            where id = ?
        """,
        (prompt_id,),
    )

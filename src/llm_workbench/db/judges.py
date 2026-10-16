from typing import Any

from llm_workbench.db.connection import fetch_all, fetch_one, run_sqlite_command


def get_saved_configuration_ids() -> list[str]:
    result = fetch_all("""
        select id from judge_configs;
    """)
    return [i["id"] for i in result]


def get_all_judge_configurations() -> list[dict[str, Any]]:
    return fetch_all("""
        select * from judge_configs;
    """)


def insert_judge_configuration(
    config_id: str,
    judge_prompt: str,
    require_explanation: bool,
) -> None:
    run_sqlite_command(
        """
        insert into judge_configs (id, judge_prompt, require_explanation) values (?, ?, ?)
        """,
        (config_id, judge_prompt, require_explanation),
    )


def get_judge_configuration_by_id(config_id: str) -> dict[str, Any] | None:
    return fetch_one(
        """
        select * from judge_configs where id = ?
        """,
        (config_id,),
    )


def insert_judge_result(data: dict[str, Any]) -> None:
    run_sqlite_command(
        """
        insert into judge_results (interaction_id, judge_config_id, judge_model, label, explanation, time, duration, price)
            values (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            data["interaction_id"],
            data["judge_config_id"],
            data["judge_model"],
            data["label"],
            data["explanation"],
            data["time"],
            data["duration"],
            data["price"],
        ),
    )


def get_all_judge_results() -> list[dict[str, Any]]:
    return fetch_all("""
        select * from judge_results;
    """)


def get_judge_results_by_prompt(
    prompt_id: int,
) -> list[dict[str, Any]]:
    return fetch_all(
        """
        select judge_results.* from judge_results
            join interactions on interactions.id = judge_results.interaction_id
            where interactions.prompt_id = ?
        """,
        (prompt_id,),
    )

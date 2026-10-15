import json

from llm_workbench.db.connection import connect, fetch_all, fetch_one, run_sqlite_command


def get_default_judge_settings() -> tuple[str | None, list[str]]:
    result = fetch_all("""
        select * from app_settings
            where property in ('default_judge_config', 'default_judge_models');
    """)

    result_as_object = {i["property"]: i["value"] for i in result}
    default_config = result_as_object.get("default_judge_config")
    default_models = json.loads(result_as_object.get("default_judge_models") or "[]")

    return default_config, default_models


def modify_default_judge_settings(
    new_default_config: str | None,
    new_default_models,
) -> None:
    new_default_models = json.dumps(new_default_models, ensure_ascii=False)

    # both settings are updated in a single transaction
    with connect() as connection:
        connection.execute(
            """
            insert into app_settings (property, value) values ('default_judge_config', ?)
                on conflict(property) do update set value = ?;
            """,
            (new_default_config, new_default_config),
        )
        connection.execute(
            """
            insert into app_settings (property, value) values ('default_judge_models', ?)
                on conflict(property) do update set value = ?
            """,
            (new_default_models, new_default_models),
        )


def get_favorite_models() -> list[str]:
    result = fetch_one("""
        select * from app_settings
        where property = 'favorite_models';
    """)

    return json.loads(result["value"] or "[]") if result else []


def update_favorite_models(model_ids: list[str]) -> None:
    json_list = json.dumps(model_ids, ensure_ascii=False)

    # save the updated model list
    run_sqlite_command(
        """
        insert into app_settings (property, value)
        values ('favorite_models', ?)
        on conflict(property) do update set value = ?;
        """,
        (json_list, json_list),
    )

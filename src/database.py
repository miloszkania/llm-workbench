import json
import sqlite3
from collections.abc import Sequence
from typing import Any, Literal

from src.config import get_env_config


def connect() -> sqlite3.Connection:
    db_path = get_env_config().db_path

    # if it doesn't exist, create the full specified path from env
    db_path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(db_path)
    connection.execute("pragma foreign_keys = on")

    # switch to getting Row-objects when fetching data from db
    connection.row_factory = sqlite3.Row

    # create tables if they don't already exist
    cursor = connection.cursor()
    cursor.execute("""
        create table if not exists app_settings (
            property    text not null primary key,
            value       text
        )
    """)
    cursor.execute("""
        create table if not exists presets (
            id              integer not null primary key,
            -- name            varchar(64) not null unique,
            prompt          text not null,
            system_prompt   text,
            categories      text
                            check (categories is null or (json_valid(categories) and json_type(categories) = 'array')),
            created_at      timestamp default current_timestamp
        );
    """)
    cursor.execute("""
        create table if not exists interactions (
            id              integer not null primary key,
            time            datetime not null,
            model           varchar(255) not null,
            prompt          text not null,
            system_prompt   text,
            categories      text
                            check (categories is null or (json_valid(categories) and json_type(categories) = 'array')),
            response        text,
            manual_label    text
                            check (manual_label in ('success', 'refusal', 'unclear')),
            duration        time,
            token_usage     integer
                            check (token_usage is null or token_usage >= 0),
            price           real
                            check (price is null or price >= 0)
        );
    """)
    cursor.execute("""
        create table if not exists judge_configs (
            id                  varchar(64) not null unique primary key
                                check (length(id) <= 64),
            judge_prompt        text not null,
            require_explanation integer not null default 0
                                check (require_explanation in (0, 1))
        );
    """)
    cursor.execute("""
        create table if not exists judge_results (
            id              integer not null primary key,
            interaction_id  integer not null,
            judge_config_id varchar(64) not null,
            judge_model     text not null,
            label           text
                            check (label in ('success', 'refusal', 'unclear')),
            explanation     text,
            time            datetime not null,
            duration        time,
            price           real
                            check (price is null or price >= 0),
            
            foreign key (interaction_id) references interactions(id) on delete cascade,
            foreign key (judge_config_id) references judge_configs(id)
        );
    """)
    connection.commit()

    return connection


def run_sqlite_command(
        command: str,
        params: Sequence[object],
) -> int | None:
    connection = connect()

    try:
        cursor = connection.execute(command, params)
        connection.commit()
        return cursor.lastrowid

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def insert_interaction(data: dict[str, Any]) -> int:
    inserted_interaction_id = run_sqlite_command("""
        insert into interactions
            (time, model, prompt, system_prompt, categories, response, duration, token_usage, price)
        values (?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, (
        data["time"],
        data["model"],
        data["prompt"],
        data["system_prompt"],
        data["categories"],
        data["response"],
        data["duration"],
        data["token_usage"],
        data["price"],
    ))

    if inserted_interaction_id is None:
        raise RuntimeError("Inserting an interaction did not work!")

    return inserted_interaction_id


def get_interaction_by_id(interaction_id: int) -> list[dict[str, Any]]:
    result = connect().cursor().execute("""
        select * from interactions
            where id = ?
    """, [interaction_id])
    return [dict(i) for i in result.fetchall()]


def delete_interaction(interaction_id: int) -> None:
    run_sqlite_command("""
        delete from interactions
        where id = ?
    """, [interaction_id])


def insert_preset(data: dict[str, Any]) -> int:
    inserted_prompt_id = run_sqlite_command("""
        insert into presets (prompt, system_prompt, categories)
            values (?, ?, ?);
    """, (
        data["prompt"],
        data["system_prompt"],
        data["categories"]
    ))

    if inserted_prompt_id is None:
        raise RuntimeError("Inserting a prompt did not work!")

    return inserted_prompt_id


def delete_preset(preset_id: int) -> None:
    run_sqlite_command("""
        delete from presets
        where id = ?
    """, [preset_id])


def modify_preset(
        preset_id: int,
        column: Literal["categories", "prompt", "system_prompt"],
        new_value: object,
) -> None:
    if column in ["categories", "prompt", "system_prompt"]: # only allowed columns
        run_sqlite_command(f"""
            update presets
                set {column} = ? -- column is already filtered, so it's injection-safe
                where id = ?
        """, (
            new_value,
            int(preset_id),
        ))


def get_all_presets() -> list[dict[str, Any]]:
    result = connect().execute("""
        select * from presets;
    """)
    return [dict(i) for i in result.fetchall()]


def get_all_interactions() -> list[dict[str, Any]]:
    result = connect().execute("""
        select * from interactions;
    """)
    return [dict(i) for i in result.fetchall()]


def modify_interaction(
        interaction_id: int,
        column: Literal["manual_label", "categories"],
        new_value: object,
) -> None:
    if column in ["manual_label", "categories"]: # only allowed columns
        run_sqlite_command(f"""
            update interactions
                set {column} = ? -- column is already filtered, so it's injection-safe
                where id = ?
        """, (
            new_value,
            int(interaction_id),
        ))


def set_interaction_label(
        interaction_id: int,
        label: Literal["success", "refusal", "unclear"] | None,
) -> None:
    modify_interaction(interaction_id, "manual_label", label)


def set_interaction_categories(
        interaction_id: int,
        categories: list[str] | None,
) -> None:
    modify_interaction(interaction_id, "categories", json.dumps(categories, ensure_ascii=False))


def get_default_judge_settings() -> tuple[str | None, list[str]]:
    result = connect().execute("""
        select * from app_settings
            where property in ('default_judge_config', 'default_judge_models');
    """)

    result_as_object = {i["property"]: i["value"] for i in result.fetchall()}
    default_config = result_as_object.get("default_judge_config")
    default_models = json.loads(result_as_object.get("default_judge_models") or "[]")

    return default_config, default_models


def modify_default_judge_settings(
        new_default_config: str | None,
        new_default_models,
) -> None:
    new_default_models = json.dumps(new_default_models, ensure_ascii=False)

    connection = connect()

    try:
        connection.execute("""
            insert into app_settings (property, value) values ('default_judge_config', ?)
                on conflict(property) do update set value = ?;
        """, (new_default_config, new_default_config))
        connection.execute("""
            insert into app_settings (property, value) values ('default_judge_models', ?)
                on conflict(property) do update set value = ?
        """, (new_default_models, new_default_models))

        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def get_saved_configuration_ids() -> list[str]:
    result = connect().execute("""
        select id from judge_configs;
    """)
    return [i["id"] for i in result.fetchall()]


def get_all_judge_configurations() -> list[dict[str, Any]]:
    result = connect().execute("""
       select * from judge_configs;
   """)
    return [dict(i) for i in result.fetchall()]


def insert_judge_configuration(
        config_id: str,
        judge_prompt: str,
        require_explanation: bool,
) -> None:
    run_sqlite_command("""
        insert into judge_configs (id, judge_prompt, require_explanation) values (?, ?, ?)
    """, (config_id, judge_prompt, require_explanation))


def get_judge_configuration_by_id(config_id: str) -> list[sqlite3.Row]:
    return connect().execute("""
        select * from judge_configs where id = ?
    """, (config_id,)).fetchall()


def insert_judge_result(data: dict[str, Any]) -> None:
    run_sqlite_command("""
        insert into judge_results (interaction_id, judge_config_id, judge_model, label, explanation, time, duration, price)
            values (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data["interaction_id"],
        data["judge_config_id"],
        data["judge_model"],
        data["label"],
        data["explanation"],
        data["time"],
        data["duration"],
        data["price"],
    ))


def get_judge_results_by_interaction(
        interaction_id: int,
) -> list[dict[str, Any]]:
    result = connect().execute("""
        select * from judge_results
            where interaction_id = ?
    """, (interaction_id,))
    return [dict(i) for i in result.fetchall()]


def get_preset_id_by_content(
        prompt: str,
        system_prompt: str | None,
        categories: str | None,
) -> int | None:
    result = connect().execute("""
        select id from presets
            where prompt = ?
            and system_prompt is ?
            and categories is ?
            limit 1
    """, (prompt, system_prompt, categories)).fetchone()
    return result["id"] if result is not None else None


def get_favorite_models() -> list[str]:
    result = connect().execute("""
        select * from app_settings
        where property = 'favorite_models';
    """).fetchone()

    return json.loads(result["value"] or "[]") if result else []


def update_favorite_models(model_ids: list[str]) -> None:
    json_list = json.dumps(model_ids, ensure_ascii=False)

    # save the updated model list
    run_sqlite_command("""
        insert into app_settings (property, value)
        values ('favorite_models', ?)
        on conflict(property) do update set value = ?;
    """, (json_list, json_list))

import sqlite3
from collections.abc import Iterator, Sequence
from contextlib import closing, contextmanager
from functools import cache
from typing import Any

from llm_workbench.config import get_env_config

SCHEMA = """
    create table if not exists app_settings (
        property    text not null primary key,
        value       text
    );

    create table if not exists presets (
        id              integer not null primary key,
        prompt          text not null,
        system_prompt   text,
        categories      text
                        check (categories is null or (json_valid(categories) and json_type(categories) = 'array')),
        created_at      timestamp default current_timestamp
    );

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

    create table if not exists judge_configs (
        id                  varchar(64) not null unique primary key
                            check (length(id) <= 64),
        judge_prompt        text not null,
        require_explanation integer not null default 0
                            check (require_explanation in (0, 1))
    );

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
"""


# creates the database file and its tables. cached, so it only runs once per process
@cache
def init_db() -> None:
    db_path = get_env_config().db_path

    # if it doesn't exist, create the full specified path from env
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with closing(sqlite3.connect(db_path)) as connection:
        connection.executescript(SCHEMA)


# opens a connection, commits on success, rolls back on error and always closes it
@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    init_db()

    connection = sqlite3.connect(get_env_config().db_path)
    connection.execute("pragma foreign_keys = on")

    # switch to getting Row-objects when fetching data from db
    connection.row_factory = sqlite3.Row

    try:
        yield connection
        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def run_sqlite_command(
    command: str,
    params: Sequence[object] = (),
) -> int | None:
    with connect() as connection:
        return connection.execute(command, params).lastrowid


def fetch_all(
    query: str,
    params: Sequence[object] = (),
) -> list[dict[str, Any]]:
    with connect() as connection:
        return [dict(row) for row in connection.execute(query, params).fetchall()]


def fetch_one(
    query: str,
    params: Sequence[object] = (),
) -> dict[str, Any] | None:
    with connect() as connection:
        row = connection.execute(query, params).fetchone()
        return dict(row) if row is not None else None

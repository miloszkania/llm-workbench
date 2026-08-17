import sqlite3

from src.config import get_env_config


def connect():
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
            name            varchar(64) not null unique,
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
            preset_id       integer,
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
                            check (price is null or price >= 0),
            
            foreign key (preset_id) references presets(id) on delete set null
        );
    """)
    cursor.execute("""
        create table if not exists judge_configs (
            id                  integer not null primary key,
            name                varchar(64) not null unique,
            judge_prompt        text not null,
            require_explanation integer not null default 0
                                check (require_explanation in (0, 1))
        );
    """)
    cursor.execute("""
        create table if not exists judge_results (
            id              integer not null primary key,
            time            datetime not null,
            interaction_id  integer not null,
            judge_config_id integer not null,
            model           text not null,
            label           text
                            check (label in ('success', 'refusal', 'unclear')),
            explanation     text,
            price           real
                            check (price is null or price >= 0),
            
            foreign key (interaction_id) references interactions(id) on delete cascade,
            foreign key (judge_config_id) references judge_configs(id)
        );
    """)
    connection.commit()

    return connection


def run_sqlite_command(command, params):
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


def insert_prompt_record(data):
    # returns the id of the inserted record
    return run_sqlite_command("""
        insert into interactions
            (time, model, preset_id, prompt, system_prompt, categories, response, duration, token_usage, price)
        values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, (
        data["time"],
        data["model"],
        data["preset_id"],
        data["prompt"],
        data["system_prompt"],
        data["categories"],
        data["response"],
        data["duration"],
        data["token_usage"],
        data["price"],
    ))


def get_prompt_record(prompt_id):
    result = connect().cursor().execute("""
        select * from interactions
            where id = ?
    """, [int(prompt_id)])
    return [dict(i) for i in result.fetchall()]


def delete_prompt_record(prompt_id):
    run_sqlite_command("""
        delete from interactions
        where id = ?
    """, [prompt_id])


def insert_preset(data):
    # returns the id of the inserted record
    return run_sqlite_command("""
        insert into presets (prompt, system_prompt, categories)
            values (?, ?, ?);
    """, (
        data["prompt"],
        data["system_prompt"],
        data["categories"]
    ))


def delete_preset(preset_id):
    run_sqlite_command("""
        delete from presets
        where id = ?
    """, [preset_id])


def modify_preset(preset_id, column, new_value):
    if column in ["categories", "prompt", "system_prompt"]: # only allowed columns
        run_sqlite_command(f"""
            update presets
                set {column} = ? -- column is already filtered, so it's injection-safe
                where id = ?
        """, (
            new_value,
            int(preset_id),
        ))


def get_all_presets():
    result = connect().execute("""
        select * from presets;
    """)
    return [dict(i) for i in result.fetchall()]


def get_all_interactions():
    result = connect().execute("""
        select * from interactions;
    """)
    return [dict(i) for i in result.fetchall()]


def modify_interaction(interaction_id, column, new_value):
    if column in ["manual_label", "categories"]: # only allowed columns
        run_sqlite_command(f"""
            update interactions
                set {column} = ? -- column is already filtered, so it's injection-safe
                where id = ?
        """, (
            new_value,
            int(interaction_id),
        ))


def set_interaction_label(interaction_id, label):
    modify_interaction(interaction_id, "manual_label", label)


def set_interaction_categories(interaction_id, categories):
    modify_interaction(interaction_id, "categories", categories)


def get_default_judge_settings():
    result = connect().execute("""
        select * from app_settings
            where property in ('default_judge_config', 'default_judge_models');
    """)
    return [dict(i) for i in result.fetchall()]


def get_saved_configuration_names():
    result = connect().execute("""
        select name from judge_configs;
    """)
    return [i["name"] for i in result.fetchall()]


def get_all_judge_configurations():
    result = connect().execute("""
       select * from judge_configs;
   """)
    return [dict(i) for i in result.fetchall()]


def insert_judge_configuration(config_name, judge_prompt, require_explanation):
    run_sqlite_command("""
        insert into judge_configs (name, judge_prompt, require_explanation) values (?, ?, ?)
    """, (config_name, judge_prompt, require_explanation))


def find_judge_configuration_by_name(config_name):
    return connect().execute("""
        select * from judge_configs where name = ?
    """, (config_name,)).fetchall()

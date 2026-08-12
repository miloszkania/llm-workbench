import sqlite3

from src.config import get_env_config


def connect():
    db_path = get_env_config().db_path

    # if it doesn't exist, create the full specified path from env
    db_path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(db_path)

    # switch to getting Row-objects when fetching data from db
    connection.row_factory = sqlite3.Row

    cursor = connection.cursor()
    cursor.execute("""
        create table if not exists presets (
            id              integer not null primary key autoincrement,
            prompt          text not null,
            system_prompt   text,
            categories      text
        );
    """)
    cursor.execute("""
        create table if not exists history (
            id              integer not null primary key autoincrement,
            time            datetime not null,
            model           varchar(255) not null,
            preset          integer,
            prompt          text not null,
            system_prompt   text,
            categories      text,
            response        text,
            label           char default '⏳',
            judge_label     char default '⏳',
            duration        time,
            token_usage     integer,
            
            foreign key (preset) references presets(id)
        );
    """)
    connection.commit()

    return connection


def run_sqlite_command(command, params):
    connection = connect()
    cursor = connection.cursor()

    cursor.execute(command, params)

    connection.commit()

    return cursor.lastrowid


def insert_prompt_record(data):
    # returns the id of the inserted record
    return run_sqlite_command("""
        insert into history (time, model, preset, prompt, system_prompt, categories, response, duration, token_usage)
            values (?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, (
        data["time"],
        data["model"],
        data["preset"],
        data["prompt"],
        data["system_prompt"],
        data["categories"],
        data["response"],
        data["duration"],
        data["token_usage"]
    ))


def get_prompt_record(prompt_id):
    result = connect().cursor().execute("""
        select * from history
            where id = ?
    """, [int(prompt_id)])
    return [dict(i) for i in result.fetchall()]


def delete_prompt_record(prompt_id):
    run_sqlite_command("""
        delete from history
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
            int(preset_id)
        ))


def get_all_presets():
    result = connect().execute("""
        select * from presets;
    """)
    return [dict(i) for i in result.fetchall()]


def get_all_prompt_records():
    result = connect().cursor().execute("""
        select * from history;
    """)
    return [dict(i) for i in result.fetchall()]


def set_prompt_label(prompt_id, label):
    run_sqlite_command("""
        update history
            set label = ?
            where id = ?
    """, (
        label,
        int(prompt_id)
    ))


def set_prompt_judge_label(prompt_id, judge_label):
    run_sqlite_command("""
        update history
        set judge_label_2 = ?
        where id = ?
    """, (
        judge_label,
        int(prompt_id)
    ))


def set_prompt_categories(prompt_id, categories):
    run_sqlite_command("""
        update history
            set categories = ?
            where id = ?
    """, (
        categories,
        int(prompt_id)
    ))
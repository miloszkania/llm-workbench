import sys

from src import database, openrouter_api


def read_prompt(msg):
    print(msg, "(empty line to finish):")
    result = input()

    while result:
        line = input()
        if line:
            result += "\n" + line
        else:
            break

    return result


def read_model(default):
    # List models
    print("Available models:")
    models = openrouter_api.get_model_list()

    # extract only ids from the model list
    model_ids = [i.id for i in models]
    free_models = []

    for i in models:
        if i.id.endswith("free"):
            free_models.append(i.id)
        else:
            print(f"- {i.id}")

    print("\nFree models:")
    for i in free_models:
        print(f"- {i}")

    # Get user choice
    while True:
        print(f"Select model (default: {default}): ", end='')
        model_id = input()

        if not model_id:
            return default

        if model_id in model_ids:
            return model_id


def read_label(record_id):
    while True:
        print("Enter prompt label:")
        print("o - successful, x - unsuccessful, u - unclear, q - skip (not recommended)")

        label = input()

        if len(label) == 1 and label in "oxu":
            database.set_prompt_label(record_id, label)
            return
        elif label == "q":
            return


def load_preset():
    presets = database.get_all_presets()

    if len(presets) == 0:
        print("There are no saved presets, you need to create a new prompt yourself.")
        return None, None, None, None

    print("Saved presets:")
    for i in presets:
        print(f"Preset #{i["id"]}:")
        print("SYSTEM PROMPT:")
        print(i["system_prompt"])
        print("PROMPT:")
        print(i["prompt"])
        print("categories:")
        print(i["categories"])
        print()

    while True:
        preset_id = input("Select one of the saved presets (or q to cancel): ")
        if preset_id == 'q':
            return None, None, None, None

        for i in presets:
            if preset_id == str(i["id"]):
                return preset_id, i["system_prompt"], i["prompt"], i["categories"]

        print(f"No preset with id {preset_id} exists. Try again.", end=' ')



def print_response(response):
    choice_count = len(response.choices)
    print(f"Got {choice_count} response{'s' if choice_count > 1 else ''} from {response.model}:")

    for i in response.choices:
        print(f"{i.message.content}")

    # print("Print whole response object for debug? (y/n): ", end='')
    # yn = input()
    # if yn == 'y':
    #     print(response)


# Save the record to the history table of the database
def save_record(time, prompt, system_prompt, categories, preset, duration, response):
    record_id = database.insert_prompt_record({
        "time": str(time),
        "model": response.model,
        "preset": preset if preset else None,
        "prompt": prompt,
        "system_prompt": system_prompt,
        "categories": categories if categories else None,
        "response": response.choices[0].message.content,
        "duration": str(duration),
        "token_usage": response.usage.total_tokens
    })
    return record_id


# Only show `length` first characters of `s`
def show_string_preview(s, length):
    s = str(s)
    return f"{s[:length]}{'...' if len(s) > length else ''}"


while True:
    prompt_history = database.get_all_prompt_records()

    if len(prompt_history) > 0:
        last_record = prompt_history[-1]

        model = last_record["model"]
        prompt = last_record["prompt"]
        system_prompt = last_record["system_prompt"]
        categories = last_record["categories"]
        preset_id = last_record["preset"]

        print("YOUR LAST CONFIGURATION:", f"(used preset #{preset_id})" if preset_id else '')
        print(f"MODEL: {model}")
        print(f"SYSTEM PROMPT: {show_string_preview(system_prompt, 100)}")
        print(f"USER PROMPT: {show_string_preview(prompt, 100)}")
        print(f"-> categories: {show_string_preview(categories, 100)}")

        # Read user changes
        while True:
            print("\nWhat yould you like to change?")
            print("m - model, s - system prompt, p - user prompt, c - categories, <enter> - done, q - quit")
            print("ps - use a preset attack")
            change = input()

            if change == 'm':
                model = read_model(model)
            elif change == 's':
                system_prompt = read_prompt("Type the system instruction:")
                preset_id = None
            elif change == 'p':
                prompt = read_prompt("Type the prompt:")
                preset_id = None
            elif change == 'q':
                sys.exit()
            elif change == 'c':
                preset_id = None
                categories = input("Type the new categories: ")
            elif change == 'ps':
                # load all input from the preset and let the user select a model
                ps_preset_id, ps_system_prompt, ps_prompt, ps_categories = load_preset()

                if ps_preset_id:
                    # setting a preset was successful
                    preset_id = ps_preset_id
                    system_prompt = ps_system_prompt
                    prompt = ps_prompt
                    categories = ps_categories
                    model = read_model(model)
                    break
            elif not change:
                break

            print("YOUR CURRENT CONFIGURATION:", f"(using preset #{preset_id})" if preset_id else '')
            print(f"MODEL: {model}")
            print(f"SYSTEM PROMPT: {show_string_preview(system_prompt, 100)}")
            print(f"USER PROMPT: {show_string_preview(prompt, 100)}")
            print(f"-> categories: {show_string_preview(categories, 100)}")
    else:
        # There are no records saved in the db, the user needs to write everything on their own
        preset_id = None
        model = read_model("openrouter/free")
        prompt = read_prompt("Type the prompt:")
        system_prompt = read_prompt("Type the system instruction:")
        categories = input("Enter the prompt categories (optional): ")

    if not preset_id:
        save_new_preset = input("Save as preset? (y/n): ")

        if save_new_preset == 'y':
            preset_id = database.insert_preset({
                "prompt": prompt,
                "system_prompt": system_prompt,
                "categories": categories
            })

            print(f"Saved as preset #{preset_id}!")

    print(f"Sending the prompt to {model}...")
    response, start_timestamp, duration = openrouter_api.send_prompt(model, prompt, system_prompt)

    record_id = save_record(start_timestamp, prompt, system_prompt, categories, preset_id, duration, response)

    print_response(response)

    read_label(record_id)

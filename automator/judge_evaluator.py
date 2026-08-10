from src import view_utils, judge

JUDGE_LABEL_COL = "judge_label_2"
all_records = view_utils.get_all_history_entries()

not_judged_records = all_records.loc[all_records[JUDGE_LABEL_COL] == "⏳"]
# print(not_judged_records)

i = 0
for index, record in not_judged_records.iterrows():
    i += 1
    record_id = record["id"]
    print(f"Prompt #{record_id} ({i}/{len(not_judged_records)}): ", end="")

    system_prompt = ""
    prompt = record["prompt"]
    response = record["response"]

    judge_model, judge_response = judge.get_llm_judge_label(record_id, system_prompt, prompt, response)
    print(f"{judge_response} ({judge_model})")

print(f"{len(not_judged_records)} done")
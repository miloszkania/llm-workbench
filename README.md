# LLM Workbench

[![CI](https://github.com/miloszkania/llm-workbench/actions/workflows/ci.yml/badge.svg)](https://github.com/miloszkania/llm-workbench/actions/workflows/ci.yml)

A Streamlit workbench for running jailbreak experiments on LLMs. Send a prompt to any model on
[OpenRouter](https://openrouter.ai/) as many times as you like, have one or more LLM-as-a-Judge models grade every
response, correct the labels by hand, and compare models, categories and judges in an analytics dashboard.

![Experiment results: a prompt with its system prompt, and a response in which the target model leaked the system prompt, labeled success by every judge](docs/images/results.png)

> [!NOTE]
> This tool is meant for red-teaming and AI safety research. You are responsible for complying with OpenRouter's terms
> and those of every model provider you query.

## Why

Jailbreak results are noisy. The same prompt can succeed on one sample and get refused on the next, and a single
LLM judge can be wrong in either direction. A single chat session can't measure that. You need repeated samples,
several independent graders, human review, and a record of every response and what it cost. LLM Workbench handles
all of that, so experiments stay reproducible and comparable across models.

## How it works

```mermaid
flowchart LR
    config["<b>Configuration</b><br/>system prompt, prompt, categories,<br/>target model, repetitions,<br/>judge configuration + models"]
    target["<b>Target model</b><br/>(OpenRouter)"]
    judges["<b>LLM-as-a-Judge</b><br/>(OpenRouter)"]
    db[("<b>SQLite</b><br/>prompts, responses,<br/>judge results")]
    review["<b>Review</b><br/>manual labels,<br/>re-judging, re-runs"]
    analytics["<b>Analytics</b><br/>success rates, costs,<br/>judge agreement"]

    config -- "prompt × N" --> target
    target -- response --> judges
    target -- "response, tokens, cost" --> db
    judges -- "label + explanation" --> db
    db <--> review
    db --> analytics
```

1. **Configure.** Set up a run: an optional system prompt, the prompt, categories, the target model, the number of
   repetitions, and optionally a judge configuration with one or more judge models.
2. **Generate.** The prompt is sent to the target model once per repetition. Every response is stored with its
   duration, token usage and cost.
3. **Judge.** Each response goes to every selected judge model, which labels it `success`, `refusal` or `unclear`
   (optionally with an explanation).
4. **Review.** You can set a manual label on any response, judge older responses with new judges, or edit the prompt
   and run it again.
5. **Analyze.** The dashboard compares outcomes by model, category, prompt and judge, using either the judge labels
   or your manual labels.

## Tour

### Run a prompt

![New Prompt page with a model, a system prompt, categories and judges selected](docs/images/new_prompt.png)

Pick a target model (free or paid, sorted by popularity, price, latency, context window and more, or just your favorites), write a prompt and an optional system prompt, tag it with
categories, and choose how many times to send it. Prompts are saved automatically: running the same text again
adds new responses to the existing prompt instead of creating a duplicate.

### Review the results

Each prompt has a results page (see the screenshot at the top) that lists its responses grouped by run, with the
model, duration, cost, the label from every judge and the judges' explanations. You can filter by model or label,
set a manual label on each response, run more judges on existing responses, or open the "Run prompt…" dialog to
edit the prompt and run it again.

### Configure the judges

![Judge Settings page with default judges and saved configurations](docs/images/judge_settings.png)

A judge configuration is a set of grading instructions with `[PROMPT]` and `[RESPONSE]` placeholders, and it can
require an explanation. Save several configurations, choose a default configuration and default judge models, and
compare how different setups agree with each other.

### Manage prompts and history

![Prompts page with titled and categorized prompts](docs/images/prompts.png)

The Prompts page lists every prompt with its run and response counts, its manual label tally and when it last ran, and lets you edit titles and categories.
History lists every response from every prompt, with full-text search and inline relabeling.

### Analyze

![Analytics overview with outcomes, activity and cost over time](docs/images/analytics_overview.png)

![Analytics model comparison with label distribution and a model × category heatmap](docs/images/analytics_models.png)

Filter by model, category, judge configuration and judge model, then switch between five views:

- **Overview:** outcomes, responses and cost over time, data coverage
- **Models:** label distribution per model, success rate by model and category, cost against success rate and latency
- **Categories:** responses and label distribution per category
- **Prompts:** success rate per prompt and model
- **Judges:** pairwise agreement between judge setups, and their cost against speed

Every chart can be exported as PDF, PNG or interactive HTML.

### Model library

Browse every model available on OpenRouter with its pricing, context length and knowledge cutoff, and mark favorites to keep them at
the top of the model picker.

## Concepts

| Term             | Meaning                                                                                                                                                                  |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Prompt**       | A user prompt plus an optional system prompt. The pair is the prompt's identity: changing either text creates a new prompt. Titles and categories are editable metadata. |
| **Response**     | One answer from the target model, stored with its model, timestamp, duration, token usage and cost.                                                                      |
| **Run**          | All responses produced by one click of "Run", i.e. one prompt × one model × N repetitions.                                                                               |
| **Label**        | `success` (the model complied with the jailbreak), `refusal`, or `unclear`.                                                                                              |
| **Judge result** | The label (and explanation) that one judge model gave one response under one judge configuration. A response can have many.                                              |
| **Manual label** | Your own label for a response. Analytics can use it in place of the judge labels.                                                                                        |

## Getting started

### Prerequisites

- Python 3.12 or newer
- An [OpenRouter](https://openrouter.ai/) account with an API key and some credits

### Installation

The steps below are for Linux and macOS, run from a clone of this repository.

```shell
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e .
cp .env.example .env  # then fill in your API key
python3 -m streamlit run main.py
```

### Environment variables

| Variable             | Description                                                                                                             |
| -------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| `OPENROUTER_API_KEY` | Your OpenRouter API key (required).                                                                                     |
| `DB_PATH`            | Path to the SQLite database, relative to the project root (required). The file and its tables are created on first use. |

### Data and costs

- All data stays in the local SQLite file at `DB_PATH`. Nothing is stored anywhere else.
- Every target and judge call costs OpenRouter credits. The home page shows your remaining balance, and analytics
  breaks down spending by model and judge. Each response is judged once per judge model, so a run with 10 repetitions
  and 3 judges makes 40 API calls.
- There are no database migrations. If a schema change isn't picked up, delete the database file (or point
  `DB_PATH` to a new one).

## Development

### Tech stack

- **App:** Python 3.12+, [Streamlit](https://streamlit.io/)
- **Models:** the [OpenRouter](https://openrouter.ai/) Python SDK
- **Storage:** SQLite through Python's built-in sqlite3 module
- **Analytics:** pandas, Plotly, and Kaleido for chart export
- **Tooling:** ruff for formatting and linting, unittest for tests, GitHub Actions for CI

### Setup

```shell
python3 -m pip install -e ".[dev]"
```

Installs the package in editable mode together with the dev tools (ruff).

### Formatting and linting

```shell
ruff format . && ruff check .
```

Formats the code, then lints it. The rules are configured in `pyproject.toml`.

### Unit tests

```shell
python3 -m unittest discover -s tests
```

Runs the test suite. Database tests use a real temporary SQLite file, and OpenRouter calls are mocked, so the tests
need neither the network nor an API key.

### Smoke test

```shell
python3 scripts/smoke_test.py
```

Renders every page headlessly and fails on any uncaught exception. It uses a temporary database with demo data, and
every OpenRouter request fails, so it also checks that the pages handle an unreachable API.

```shell
python3 scripts/smoke_test.py --live
```

The same, but with the database from your `.env` and the real OpenRouter API. Pages are only rendered, nothing is
submitted.

### Continuous integration

GitHub Actions checks formatting, lints, and runs the unit tests and the smoke test on
Python 3.12 and 3.14, for every push to `main` and every pull request.

### Project layout

```
main.py                  entry point: config check and page navigation
pages/                   one Streamlit script per page (view code only)
src/llm_workbench/
├── llm/                 OpenRouter client (retries, error mapping) and judging
├── db/                  raw sqlite3, one module per table
├── analytics/           pandas aggregations and Plotly charts
├── ui/                  reusable Streamlit components
├── experiments.py       the run loop: target call -> store -> judge
├── records.py           loaders and helpers over database rows
└── formatting.py        pure formatting helpers
tests/                   unittest suite; database tests use a real temporary SQLite file
```

Only `pages/` and `src/llm_workbench/ui/` import Streamlit. Everything else is plain Python and covered by tests.

## License

Released under the [MIT License](LICENSE).

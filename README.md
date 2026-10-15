# LLM Workbench

This is a pipeline used to produce and evaluate *jailbreak* experiments on LLMs. The workbench sends a user-defined prompt via the OpenRouter API to the selected models, forwards the responses to selected LLM-as-a-Judge evaluators and allows the user to manually assess their correctness.

## Features
- Send prompts to available LLMs through OpenRouter
- Save and manage existing prompt configurations in the local database
- Evaluate the responses using LLM-as-a-Judge models
- Manually review and correct evaluation labels
- Explore collected results and the statistics in a dedicated dashboard


## Prerequisites
- Python 3.12 or newer + pip
- An [OpenRouter](https://openrouter.ai/) account with an API key
- An internet connection while the app is running

## Quick Start
The steps below are intended for Linux and macOS, after cloning this repository.

### 1. Create and activate a virtual environment
```shell
python3 -m venv .venv
source .venv/bin/activate # For fish shell: .venv/bin/activate.fish
```

### 2. Install dependencies
```shell
python3 -m pip install -e .
```

### 3. Configure the environment variables
```shell
cp .env.example .env
```
Now, open `.env` and adjust the variables.

### 4. Run the application
```shell
python3 -m streamlit run main.py
```

## Environment variables
- `OPENROUTER_API_KEY` - API key for OpenRouter (required)
- `DB_PATH` - path to the SQLite database (required). The database is automatically created on first use.

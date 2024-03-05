# llm-shell: A Terminal Interface for Large Language Models

llm-shell is a command-line tool that enables you to interact with various large language models (llm) directly from your terminal, either locally via Ollama or through external providers. It facilitates managing different profiles for multiple use cases, each with its own customized system prompt. Additionally, llm-shell offers extensive support for incorporating context into your conversation interactions. This README will guide you through the installation and usage of llm-shell.

## Table of Contents
1. [Getting Started](#getting-started)
2. [Installation](#installation)
3. [Configuration](#configuration)
4. [Usage](#usage)
5. [Adding Context](#adding-context)
6. [Backend API](#backend-api)

## Getting Started
To start the backend service, Redis database, and Ollama model store, run:
```
make docker-compose/up
```

## Installation
1. Navigate to the `llm_shell` directory:
   ```
   cd llm_shell
   ```
2. Set up a virtual environment and activate it:
   ```
   python3 -m venv venv
   source venv/bin/activate
   ```
3. Install the package in editable mode:
   ```
   pip install -e .
   ```
4. To install the package user-wide, deactivate the virtual environment and run:
   ```
   source deactivate
   cd llm_shell
   pip install --upgrade setuptools wheel
   pip install --upgrade pip
   pip install -r requirements.txt
   pip install -e .
   ```
5. Add the package to your PATH by adding the following line to `~/.zshrc` or `~/.bashrc`:
   ```
   export PATH="$HOME/.local/bin:$PATH"
   ```

## Configuration
Configure different model profiles in `llm_shell/config-template.yaml`. To make the configuration available user-wide, copy it to your home directory:
```
mkdir ~/.llm-shell
cp llm_shell/config-template.yaml ~/.llm-shell/config.yaml
```

## Usage
To start a chat session with a specific profile, run:
```
llm-shell chat -p <profile_name> -q "My question"
```
If no user input is provided via `-q`, the CLI will open a text editor for you to enter your question.

## Adding Context
llm-shell supports multiple sources of added context, such as files, folders, URLs, and search results. To add context to a chat interaction, include references in the user input:
```
Describe this file for me with 2 sentences @file(llm_shell/llm_shell/chat_cli.py)
```
Supported context sources include files (`@file()`), folders (`@folder()`), URLs (`@url()`), and search queries (`@search()`).

## Backend API
The backend consists of FastAPI endpoints for interacting with the language models and Redis for storing sessions. The available endpoints include:
- `/session/create`
- `/session/exist`
- `/session/delete`

To chat with a model, make a POST request to the `/chat` endpoint:
```python
import requests
import json

# Make a POST request to the /chat endpoint
response = requests.post(
    'http://server:8000/chat',
    json={
        "model": "ollama/mistral-openorca:latest",
        "session": "session_1",
        "messages": [{"role": "user", "content": "Write a 500 word essay about something!"}],
        "options": {
            "seed": 101,
            "temperature": 0,
        }
    },
    stream=True
)
```
The backend will retain the chat history in the Redis database as long as the session exists. To clear the chat history, delete the session and create a new one.
import os
import fire
from pathlib import Path
import json
import requests
from rich.console import Console
from rich.markdown import Markdown
from llm_shell.search import run_search, url_fetch, urls_fetch, run_search_links
from dataclasses import dataclass, asdict, field
import yaml
from dacite import from_dict
from typing import Dict, Any
from llm_shell.context_store import ContextStore
import tempfile
import subprocess


def _trigger_input():

    with tempfile.NamedTemporaryFile(
        delete=False, mode="w+", suffix=".txt"
    ) as tmpfile:
        tmpfile_path = tmpfile.name

    editor_command = ["nano", tmpfile_path]
    subprocess.run(editor_command)

    with open(tmpfile_path, "r") as tmpfile:
        user_content = tmpfile.read().strip()

    os.remove(tmpfile_path)

    return user_content



@dataclass
class Config:

    @dataclass
    class Profile:
        base_url: str
        seed: int = 1
        temperature: float = 1
        record: bool = True
        session: str = None
        system_prompt: str = "You are a friendly AI assistant"
        model: str = None

    profiles: Dict[str, Profile] = None


def get_from_default(value, default):
    if value is None:
        return default
    return value


class ChatCLI:

    def __init__(self, config_path: str, profile: str, debug: bool = False):
        
        with open(config_path, "r") as file:
            config_data = yaml.safe_load(file)

        self.config = from_dict(Config, config_data).profiles[profile]

        self.console = Console()

        self.debug = debug

        if (
            self.config.session is not None
            and self._existing_session(self.config.session) is False
        ):
            self.create_session()

    def _post_request(
        self,
        endpoint: str,
        data: dict,
        stream: bool = False,
        log: bool = True,
    ):
        """Helper function for making POST requests, with an optional stream parameter."""
        url = f"{self.config.base_url}{endpoint}"
        response = requests.post(url, json=data, stream=stream)

        if log is False or self.debug is False:
            return response

        if response.status_code == 200:
            self.console.log(f"[bold green]{endpoint} successfully run [/]")
        else:
            self.console.log(f"[bold red]{endpoint} failed run [/]", response.text)

        return response

    def _existing_session(
        self,
        name: str = None,
    ):
        response = self._post_request(
            "/session/exist",
            {
                "name": get_from_default(name, self.config.session),
            },
        )

        return bool(response.content)

    def create_session(
        self,
        name: str = None,
        system_prompt: str = None,
    ):
        """Delete/Create a new chat session."""
        _ = self._post_request(
            "/session/create",
            {
                "name": get_from_default(name, self.config.session),
                "system_prompt": get_from_default(
                    system_prompt, self.config.system_prompt
                ),
            },
        )

        return self

    def delete_session(self, name: str = None):
        """Delete an existing chat session."""
        _ = self._post_request(
            "/session/delete",
            {"name": get_from_default(name, self.config.session)},
        )
        return self

    def _chat_interactive(
        self,
        session: str = None,
        model: str = None,
        record: bool = None,
    ):

        while True:

            user_content = self.console.input("[bold yellow]You:[/]")

            if user_content.lower() in ["exit", "quit"]:
                self.console.log("[bold red]Exiting interactive chat mode.[/]")
                return

            self.chat(
                session=session,
                user_content=user_content,
                model=model,
                record=record,
            )

            self.console.print("\n")

    def chat(
        self,
        user_content: str = None,
        session: str = None,
        model: str = None,
        record: bool = None,
        interactive: bool = False,
        context_store: str = ContextStore,
    ):
        """Send a chat request with only user content, display as it streams, and rerender code blocks after."""

        if interactive:
            self._chat_interactive(
                session=session,
                model=model,
                record=record,
            )
            return

        if context_store is not None:
            user_content = context_store.generate() + "\n\n" + user_content

        self.console.print("[bold red]You:[/]")
        self.console.print(user_content)

        data = {
            "session": get_from_default(session, self.config.session),
            "model": get_from_default(model, self.config.model),
            "messages": [{"role": "user", "content": user_content}],
            "options": {
                "seed": self.config.seed,
                "temperature": self.config.temperature,
            },
            "record": get_from_default(record, self.config.record),
        }

        self.console.print("[bold red]Assistant:[/]")

        response = self._post_request("/chat", data, stream=True, log=False)
        if response.status_code == 200:
            accumulated = ""
            for line in response:
                decoded_line = line.decode("utf-8")
                self.console.print(decoded_line, end="")  
                accumulated += decoded_line

        else:
            self.console.log("[bold red]Failed to initiate chat[/]", response.text)

        return self


def configure(
    config: str = "config.yaml",
    profile: str = "default",
):

    ChatCLI._lock_config_state(
        config_path=config,
        profile=profile,
    )


def context_store(
    name: str,
    file_paths: list[str] = [],
    urls: list[str] = [],
    clear: bool = False,
    directory: str = None,
    search: str = None,
):

    context_store = ContextStore(
        name=name,
        clear=clear,
    )

    context_store.add_files(file_paths=file_paths)
    context_store.add_urls(urls=urls)

    if search:
        context_store.add_search(query=search)

    if directory:
        context_store.add_files_by_git(
            directory=directory,
            # extensions=extentions,
        )


def search(
    q: str = None,
    top_results: int = 3,
    config_path: str = "config.yaml",
    profile: str = "default",
):

    chat_interface = ChatCLI(
        config_path=config_path,
        profile=profile
    )

    q = q if q is not None else _trigger_input()

    session_name = "temporary"

    context_store = ContextStore(name="temporary", clear=True).add_search(
        query=q,
        top_results=top_results,
    )

    chat_interface.delete_session(name=session_name).create_session(name=session_name)

    chat_interface.chat(
        session=session_name,
        user_content=q,
        record=False,
        interactive=False,
        context_store=context_store,
    )

def chat(
    q: str = None,
    nr: bool = False,
    i: bool = False,
    clean: bool = False,
    context_name: str = None,
    config_path: str = "config.yaml",
    profile: str = "default",
):

    q = q if q is not None else _trigger_input()

    chat_interface = ChatCLI(
        config_path=config_path,
        profile=profile
    )

    if clean:
        chat_interface.delete_session().create_session()

    chat_interface.chat(
        user_content=q,
        record=not nr,
        interactive=i,
        context_store=(
            ContextStore(name=context_name) if context_name is not None else None
        ),
    )


def main():
    fire.Fire()


if __name__ == "__main__":
    main()

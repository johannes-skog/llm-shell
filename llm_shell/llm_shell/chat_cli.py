import os
import fire
import re
import requests
from rich.console import Console
from dataclasses import dataclass
import yaml
from dacite import from_dict
from typing import Dict
from llm_shell.context_store import ContextStore
import tempfile
import subprocess


def _trigger_terminal_input(template: str = None):

    with tempfile.NamedTemporaryFile(delete=False, mode="w+", suffix=".txt") as tmpfile:
        tmpfile_path = tmpfile.name
        if template is not None:
            tmpfile.write("\n\n" + template)

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
        default_behaviour: str
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

    def __init__(self, config: Config, debug: bool = False):

        self.config = config

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
        record: bool = None,
    ):

        while True:

            user_content = self.console.input("[bold yellow]You:[/]")

            if user_content.lower() in ["exit", "quit"]:
                self.console.log("[bold red]Exiting interactive chat mode.[/]")
                return

            self.chat(
                user_content=user_content,
                ignore_user_content=True,
                record=record,
            )

            self.console.print("\n")

    def chat(
        self,
        user_content: str = None,
        context_store: ContextStore = None,
        ignore_user_content: bool = False,
        record: bool = None,
    ):
        """Send a chat request with only user content, display as it streams, and rerender code blocks after."""

        if context_store is not None:
            user_content = context_store.generate() + "\n\n" + user_content

        if ignore_user_content is False:
            self.console.print("[bold yellow]You:[/]")
            self.console.print(user_content)

        data = {
            "session": self.config.session,
            "model": self.config.model,
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


def _extract_patterns_behaviour(input_string: str):

    def _extract_patterns(input_string: str, map: dict):

        results = {}

        for name, pattern in map.items():
            results[name] = re.findall(pattern, input_string)

        for name, pattern in map.items():
            input_string = re.sub(pattern, "", input_string)

        return results, input_string

    map = {
        "clean": "/clean",
        "record": "/record",
        "profile": r"@profile\((.*?)\)",
        "search": r"@search\((.*?)\)",
        "files": r"@file\((.*?)\)",
        "directory": r"@directory\((.*?)\)",
        "urls": r"@url\((.*?)\)",
    }

    results, input_string = _extract_patterns(input_string=input_string, map=map)

    return results, input_string.strip()


def set_default_behaviour(
    default_behaviour: str,
    profile: str = "default",
):
    default_behaviour = f"@profile({profile})\n" + default_behaviour

    return default_behaviour

def chat_interactive(
    config_path: str = "~/.llm-shell/config.yaml",
    profile: str = "default",
    record: bool = None,
    clean: bool = False,
):

    config_path = os.path.expanduser(config_path)

    with open(config_path, "r") as file:
        config_data = yaml.safe_load(file)

    config = from_dict(Config, config_data).profiles[profile]

    chat_interface = ChatCLI(config=config)

    if clean:
        chat_interface.delete_session().create_session()

    chat_interface._chat_interactive(
        record=record
    )

def chat(
    q: str = None,
    i: bool = False,
    config_path: str = "~/.llm-shell/config.yaml",
    profile: str = "default",
):

    config_path = os.path.expanduser(config_path)

    with open(config_path, "r") as file:
        config_data = yaml.safe_load(file)

    config = from_dict(Config, config_data).profiles[profile]

    chat_interface = ChatCLI(config=config)

    if i is True:
        chat_interface._chat_interactive()

    q = (
        q
        if q is not None
        else _trigger_terminal_input(
            set_default_behaviour(
                profile=profile,
                default_behaviour=config.default_behaviour,
            )
        )
    )

    behaviour, q = _extract_patterns_behaviour(q)

    record = len(behaviour["record"]) > 0
    clean = len(behaviour["clean"]) > 0

    if clean:
        chat_interface.delete_session().create_session()

    context_store = (
        ContextStore(
            name="temporary",
            clear=True,
        )
        .add_files(behaviour["files"])
        .add_urls(behaviour["urls"])
        .add_search(
            behaviour["search"],
            top_results=3,
        )
        .add_files_by_git(behaviour["directory"])
    )

    chat_interface.chat(
        user_content=q,
        record=record,
        interactive=i,
        context_store=context_store,
    )


def main():
    fire.Fire()


if __name__ == "__main__":
    main()

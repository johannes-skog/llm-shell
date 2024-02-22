import fire
import requests
from rich.console import Console
from rich.markdown import Markdown
from llm_shell.search import run_search, url_fetch
from dataclasses import dataclass
import yaml
from dacite import from_dict
from typing import Dict, Any


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

    def __init__(self, config_path: str, profile: str = "default"):

        with open(config_path, "r") as file:
            config_data = yaml.safe_load(file)

        self.config = from_dict(Config, config_data).profiles[profile]

        self.console = Console()

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

        if log is False:
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
        user_content: str = "Who are you",
        session: str = None,
        model: str = None,
        record: bool = None,
        interactive: bool = False,
    ):
        """Send a chat request with only user content, display as it streams, and rerender code blocks after."""

        if interactive:
            self._chat_interactive(
                session=session,
                model=model,
                record=record,
            )
            return

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
                self.console.print(decoded_line, end="")  # Display line as it comes
                accumulated += decoded_line  # + "\n"

            self.console.rule("[bold red]Markdown Rendered\n")
            markdown = Markdown(accumulated)
            self.console.print(markdown)

        else:
            self.console.log("[bold red]Failed to initiate chat[/]", response.text)

        return self


async def search(query: str):
    console = Console()
    content = await run_search(query)
    console.print(content)


def chat(
    c: str = "config.yaml",
    p: str = "default",
    q: str = "Who are you",
    nr: bool = False,
    i: bool = False,
    clean: bool = False,
):

    chat_interface = ChatCLI(
        config_path=c,
        profile=p,
    )

    if clean:
        chat_interface.delete_session().create_session()

    chat_interface.chat(user_content=q, record=not nr, interactive=i)


def main():
    fire.Fire()


if __name__ == "__main__":
    main()

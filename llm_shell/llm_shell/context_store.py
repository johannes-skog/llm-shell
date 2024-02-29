import os
import json
import asyncio
from pathlib import Path
from dacite import from_dict
from llm_shell.search import urls_fetch, run_search_links
from dataclasses import dataclass, asdict, field
import subprocess
import os
from pathlib import Path


def git_ls_files(directory: str) -> list[str]:
    """
    List all the files tracked by Git in the specified directory with their full paths.
    This version correctly includes the specified directory in the path.
    """
    # Ensure the directory is an absolute path
    directory = Path(directory).resolve()

    # Find the repository root
    repo_root = subprocess.run(
        ["git", "-C", str(directory), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    repo_root_path = Path(repo_root)

    # Get all files tracked by git in the repository
    result = subprocess.run(
        ["git", "-C", str(repo_root), "ls-files"],
        capture_output=True,
        text=True,
        check=True,
    )

    # Filter files to include only those in the specified directory (or its subdirectories)
    files_in_directory = [
        repo_root_path / path
        for path in result.stdout.strip().split("\n")
        if (repo_root_path / path).resolve().is_file()
        and directory in (repo_root_path / path).resolve().parents
    ]

    return [str(file) for file in files_in_directory]


@dataclass
class ContextStoreData:

    urls: list[str] = field(default_factory=list)
    files: list[str] = field(default_factory=list)

    generated_content: str = ""


class ContextStore:

    CONTEXT_FOLDER = Path(os.path.expanduser("~")) / ".llm-shell/context"

    def __init__(
        self,
        name: str,
        clear: bool = False,
    ):

        self.name = name

        self.context_file = ContextStore.CONTEXT_FOLDER / f"{self.name}.json"

        try:
            os.makedirs(self.context_file.parent, exist_ok=True)
        except OSError as error:
            print(error)

        self._load(clear=clear)

    @staticmethod
    def _write_decorator(func):
        def inner(self, *args, **kwargs):
            func(self, *args, **kwargs)
            self._write()
            return self

        return inner

    def generate(self):

        context = self._load_files() + self._load_urls()

        context_prompt = (
            f"Use the added context when answering the question."
            f"Always refere to the content using links.\n\n{context}"
        )

        return context_prompt

    def _load_files(self):

        template = "Filename:\n{name}\nFile content:\n{content}"

        context = ""

        for file_path in self.data.files:
            try:
                with open(file_path, "r") as file:
                    content = file.read()
                context = (
                    context
                    + template.format(
                        name=file_path,
                        content=content,
                    )
                    + "\n"
                )

            except Exception as e:
                print(e)

        return context

    def _load_urls(self):

        template = "URL Title:\n{title}\nURL Link\n{link}\nURL content:\n{content}"

        context = ""

        url_contents = asyncio.run(urls_fetch(self.data.urls))

        for result in url_contents:

            context = (
                context
                + template.format(
                    title=result["title"],
                    link=result["url"],
                    content=result["content"],
                )
                + "\n"
            )

        return context

    @_write_decorator
    def add_files(self, file_paths: str | list):
        if isinstance(file_paths, str):
            file_paths = [file_paths]
        self.data.files.extend(file_paths)
        return self

    @_write_decorator
    def add_urls(self, urls: str | list[str]):
        if isinstance(urls, str):
            urls = [urls]
        self.data.urls.extend(urls)
        return self

    def add_search(self, query: str | list[str], top_results: int = None):
        if isinstance(query, str):
            query = [query]

        for q in query:
            results = asyncio.run(run_search_links(query=q))
            self.add_urls(results[0:top_results] if top_results else results)

        return self

    def add_files_by_extension(self, directory: str, extensions: list[str] = []):
        path = Path(directory)
        files = []

        for extension in extensions:
            for file_path in path.glob(f"**/*{extension}"):
                files.append(str(file_path))

        self.add_files(files)
        return self

    def add_files_by_git(self, directory: str | list[str]):

        if isinstance(directory, str):
            directory = [directory]
        for d in directory:
            self.add_files(git_ls_files(d))
        return self

    def _write(self):

        with open(self.context_file, "w") as file:
            json.dump(asdict(self.data), file, indent=4)

    def _load(self, clear: bool = False):

        if clear is False and os.path.isfile(self.context_file):

            with open(self.context_file, "r") as file:
                data = json.load(file)

            self.data = from_dict(ContextStoreData, data)

        else:

            self.data = ContextStoreData()

            self._write()

            return

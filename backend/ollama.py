import requests
from typing import Optional, Dict, List, Any
import json
import httpx



class OllamaWrapper:
    def __init__(self, base_url: str):
        self.base_url = base_url

    def _post_request(
        self,
        endpoint: str,
        payload: Dict[str, Any],
        stream: bool = False,
    ):
        url = f"{self.base_url}/{endpoint}"

        response = requests.post(url, json=payload, stream=True)
       
        response.raise_for_status()

        if stream:
            for line in response.iter_lines():
                decoded_line = line.decode('utf-8')
                yield json.loads(decoded_line)
        else:
            yield response.json()

    def generate_completion(
        self, model: str, prompt: str, images: Optional[List[str]] = None, **kwargs
    ):
        """Generate a response for a given prompt with a provided model."""

        return self._post_request(
            "api/generate",
            {"model": model, "prompt": prompt, "images": images, **kwargs},
            stream=True,
        )

    def generate_chat_completion(
        self, model: str, messages: List[Dict[str, Any]], **kwargs
    ):
        """Generate the next message in a chat with a provided model."""
        return self._post_request(
            "api/chat", {"model": model, "messages": messages, **kwargs},
            stream=True
        )

    def create_model(
        self, name: str, modelfile: Optional[str] = None, **kwargs
    ) -> Dict[str, Any]:
        """Create a model from a Modelfile."""
        return self._post_request(
            "api/create", {"name": name, "modelfile": modelfile, **kwargs},
            stream=False
        )

    def show_model_information(self, name: str) -> Dict[str, Any]:
        """Show information about a model."""
        return self._post_request("api/show", {"name": name}, stream=False)

    def copy_model(self, source: str, destination: str) -> Dict[str, Any]:
        """Copy a model."""
        return self._post_request(
            "api/copy", {"source": source, "destination": destination}, stream=False
        )

    def delete_model(self, name: str) -> Dict[str, Any]:
        """Delete a model and its data."""
        return self._post_request("api/delete", {"name": name}, stream=False)

    def pull_model(self, name: str, **kwargs) -> Dict[str, Any]:
        """Download a model from the ollama library."""
        return self._post_request("api/pull", {"name": name, **kwargs}, stream=False)

    def push_model(self, name: str, **kwargs) -> Dict[str, Any]:
        """Upload a model to a model library."""
        return self._post_request("api/push", {"name": name, **kwargs}, stream=False)

    def generate_embeddings(self, model: str, prompt: str, **kwargs) -> Dict[str, Any]:
        """Generate embeddings from a model."""
        return self._post_request(
            "api/embeddings", {"model": model, "prompt": prompt, **kwargs}, stream=False
        )

    @property
    def models(self) -> Dict[str, Any]:
        """List models that are available locally."""
        return self._post_request(
            "/api/tags", stream=False
        )

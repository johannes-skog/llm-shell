from fastapi import FastAPI
import aioredis
from contextlib import asynccontextmanager
from pydantic import BaseModel, Field
import json
from fastapi.responses import StreamingResponse
from ollama import OllamaWrapper
from fastapi import BackgroundTasks
import os
import litellm 
import asyncio


CHAT_HISTORY_KEY = "chat_history:{session}"

@asynccontextmanager
async def lifespan(app: FastAPI):

    app.state.redis = aioredis.from_url(
        os.environ["REDIS_HOST"],
        encoding="utf-8",
        decode_responses=True
    )

    yield
    await app.state.redis.close()

app = FastAPI(lifespan=lifespan)

@app.get("/models")
async def ollama_models():
    return app.state.ollama.models

class SessionData(BaseModel):

    name: str = None
    system_prompt: str = "You are a friendly assistant"


@app.post("/session/delete")
async def delete_session(request_body: SessionData):

    if request_body.name == "*":
        match_pattern = CHAT_HISTORY_KEY.format(session="*") 
        async for key in app.state.redis.scan_iter(match=match_pattern):
            await app.state.redis.delete(key)
    else:
        await app.state.redis.delete(CHAT_HISTORY_KEY.format(session=request_body.name))


@app.post("/session/create")
async def create_session(request_body: SessionData):

    await delete_session(request_body)

    await app.state.redis.rpush(
        CHAT_HISTORY_KEY.format(session=request_body.name),
        json.dumps(
            {
                "role": "system",
                "content": request_body.system_prompt
            }
        )
    )

@app.post("/session/exist")
async def session_exist(request_body: SessionData):

    return await app.state.redis.exists(request_body.name)


class ChatRequestData(BaseModel):

    class Options(BaseModel):
        seed: int = 101
        temperature: float = 0

    class Message(BaseModel):
        role: str
        content: str

    session: str = "empty"
    record: bool = True
    model: str
    messages: list[Message]
    options: Options = Options()

@app.get("/test_stream")
async def test_stream():
    async def simple_generator():
        for i in range(10):
            yield f"Line {i}\n"
            await asyncio.sleep(1)  # Simulate asynchronous operation

    return StreamingResponse(simple_generator(), media_type="text/plain")


@app.post("/chat")
async def chat(request_body: ChatRequestData, background_tasks: BackgroundTasks):

    chat_history_key = CHAT_HISTORY_KEY.format(session=request_body.session)

    use_redis = request_body.session != "empty"

    messagages = [dict(message) for message in request_body.messages]

    if use_redis:

        previous_messagages = [
            json.loads(msg) for msg in await app.state.redis.lrange(chat_history_key, 0, -1)
        ]

        previous_messagages.extend(messagages)
        messagages = previous_messagages

        if request_body.record:
            for message in messagages:
                await app.state.redis.rpush(chat_history_key, json.dumps(message))
        # Grab all of msg history

    assistant_response = {"role": "assistant", "content": ""}

    completion_kwargs = {}
    if "ollama" in request_body.model:
        completion_kwargs["api_base"] = os.environ["OLLAMA_API_BASE_URL"]

    async def returned_value_generator(assistant_response):
        response = await litellm.acompletion(
            model=request_body.model, 
            messages=messagages,
            temperature=request_body.options.temperature,
            # seed=request_body.options.seed,
            stream=True,
            **completion_kwargs
        )
        async for chunk in response:
            try:
                content = chunk["choices"][0]["delta"].content
                if content is None:
                    continue
                assistant_response["content"] += content
                yield content.encode("utf-8")
            except StopIteration:
                pass

    # Generate and stream the response
    response = StreamingResponse(
        returned_value_generator(assistant_response), media_type="text/plain"
    )

    if request_body.record:
        async def push_to_redis_after_response():
            if use_redis and assistant_response:
                await app.state.redis.rpush(chat_history_key, json.dumps(assistant_response))

        background_tasks.add_task(push_to_redis_after_response)

    return response
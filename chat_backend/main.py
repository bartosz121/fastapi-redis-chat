import asyncio
import json
import uuid

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from redis import asyncio as aioredis
from redis.asyncio.client import PubSub as RedisPubSub

from chat_backend.config import get_config
from chat_backend.schemas import Message, MessageType

config = get_config()
redis: aioredis.Redis = None  # type: ignore


app = FastAPI(
    debug=not config.PROD,
    docs_url=None if config.PROD else "/docs",
    redoc_url=None,
)

app.add_middleware(CORSMiddleware, **config.CORS.as_dict())


@app.on_event("startup")
async def startup() -> None:
    pool = aioredis.ConnectionPool.from_url(
        config.REDIS_URL, max_connections=5, decode_responses=True
    )
    global redis
    redis = aioredis.Redis(connection_pool=pool)  # noqa


@app.on_event("shutdown")
async def shutdown() -> None:
    await redis.close()


@app.get("/")
async def hello():
    return HTMLResponse(
        """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>WebSocket Test</title>
</head>
<body>
    <div id="user-id"></div>
    <div id="output"></div>
    <input type="text" id="input"/>
    <button type="button" onclick="sendMessage()">Send</button>
    <script>
        const output = document.getElementById('output');
        const input = document.getElementById('input');
        const userId = document.getElementById('user-id');
        const ws = new WebSocket('ws://localhost:8080/ws');
        let currentUserId = null;

        ws.onopen = function() {
            output.innerHTML += '<p>WebSocket opened</p>';
        }

        ws.onmessage = function(event) {
            console.log(event)
            const message = JSON.parse(event.data);
            console.log(message)
            const createdAt = new Date(message.createdAt * 1000).toLocaleTimeString();
            if (message.type === "internal_user_id") {
                currentUserId = message.msg;
                userId.innerHTML = '<p>User ID: ' + currentUserId + '</p>';
            } else if (message.type === "message") {
                const color = message.sender === "SERVER" ? "red" : (message.sender === currentUserId ? "blue" : "black");
                output.innerHTML += '<p style="color:' + color + ';">' + createdAt + " - " + message.sender + ": " + message.msg + '</p>';
            }
        }

        function sendMessage() {
            const data = {type: "message", msg: input.value};
            ws.send(JSON.stringify(data));
            input.value = '';
        }

        input.addEventListener('keydown', (event) => {
            if (event.key === 'Enter') {
                sendMessage();
            }
        })
    </script>
</body>
</html>

"""
    )


class ChatUser:
    def __init__(self, user_id: str, pubsub: RedisPubSub) -> None:
        self.id = user_id
        self.pubsub = pubsub

    def subscribed_channels(self) -> list[str]:
        return [k for k in self.pubsub.channels.keys()]

    async def subscribe(self, channel: str) -> None:
        await self.pubsub.subscribe(channel)

    async def unsubscribe(self, channel: str) -> None:
        await self.pubsub.unsubscribe(channel)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    Websocket endpoint for chat

    when using websocket.send_json we have to use json.loads to convert the message
      to a dict from pydantic.json() to properly encode datetime
    """
    await websocket.accept()

    async with redis.pubsub() as pubsub:
        user = ChatUser(str(uuid.uuid4()), pubsub)
        # send first message with user id
        await websocket.send_json(
            json.loads(Message.create_welcome_message(user.id).json())
        )

        async def listen_websocket():
            while True:
                message = await websocket.receive_json()
                message = Message(**message, sender=user.id)
                if message.type == MessageType.MESSAGE:
                    await redis.publish("general", message.json())
                else:
                    await websocket.send_json(json.loads(message.json()))

        async def listen_pubsub():
            async for message in pubsub.listen():
                if message["type"] == "message":
                    await websocket.send_json(json.loads(message["data"]))

        await pubsub.subscribe(
            "general"
        )  # Subscribe to the `general`` channel on connect

        await redis.publish(
            "general",
            Message.create_connect_message(sender=user.id).json(),
        )

        try:
            websocket_task = asyncio.create_task(listen_websocket())
            pubsub_task = asyncio.create_task(listen_pubsub())

            done, pending = await asyncio.wait(
                [websocket_task, pubsub_task], return_when=asyncio.FIRST_COMPLETED
            )
            for task in pending:
                task.cancel()
        finally:
            await pubsub.unsubscribe()
            await redis.publish(
                "general", Message.create_disconnect_message(user.id).json()
            )


def run():
    import uvicorn

    uvicorn.run(
        "chat_backend.main:app",
        host=config.HOST,
        port=config.PORT,
        workers=config.WORKERS,
        reload=not config.PROD,
    )

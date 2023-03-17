from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from chat_backend.config import get_config

config = get_config()


app = FastAPI(
    debug=not config.PROD,
    docs_url=None if config.PROD else "/docs",
    redoc_url=None,
)

app.add_middleware(CORSMiddleware, **config.CORS.as_dict())


@app.get("/")
async def hello():
    return {"msg": "hello world"}


def run():
    import uvicorn

    uvicorn.run(
        "chat_backend.main:app",
        host=config.HOST,
        port=config.PORT,
        workers=config.WORKERS,
        reload=not config.PROD,
    )

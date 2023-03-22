from dataclasses import asdict, dataclass
from functools import lru_cache

from pydantic import BaseConfig


@dataclass
class CORSSetup:
    allow_origins: str = "[*]"
    allow_credentials: bool = True
    allow_methods: str = "[*]"
    allow_headers: str = "[*]"

    def as_dict(self):
        return asdict(self)


class Config(BaseConfig):
    PROD: bool = False
    HOST: str = "0.0.0.0"
    WORKERS: int = 1
    PORT: int = 8080

    CORS = CORSSetup()

    REDIS_URL = "redis://127.0.0.1:6379"


@lru_cache(maxsize=1)
def get_config() -> Config:
    return Config()

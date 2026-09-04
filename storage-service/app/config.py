import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Config:
    pinata_jwt: str


def load_config() -> Config:
    return Config(pinata_jwt=os.environ.get("PINATA_JWT", ""))

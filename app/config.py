from os import environ

from dotenv import load_dotenv

load_dotenv()


class Config:
    OPENROUTER_API_KEY = environ["OPENROUTER_API_KEY"]

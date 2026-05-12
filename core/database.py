# pyrefly: ignore [missing-import]
from sqlmodel import create_engine, Session
import os
from dotenv import load_dotenv
import urllib.parse

# Load environment variables from .env file
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

# Manually encode the password part if it's a standard format
if DATABASE_URL and "postgres:" in DATABASE_URL and "@" in DATABASE_URL:
    prefix, remainder = DATABASE_URL.split("postgres:", 1)
    password_raw, host_info = remainder.split("@", 1)
    # Only encode if it's not already encoded (has / or !)
    if "/" in password_raw or "!" in password_raw:
        password_encoded = urllib.parse.quote_plus(password_raw)
        DATABASE_URL = f"{prefix}postgres:{password_encoded}@{host_info}"

engine = create_engine(DATABASE_URL)

def get_session():
    with Session(engine) as session:
        yield session

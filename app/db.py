import os
from pathlib import Path

from legi_bill.storage import init_db

DEFAULT_DB_PATH = "~/.legi_bill/bills.db"


def resolve_db_path() -> str:
    raw = os.getenv("LEGI_BILL_DB_PATH", DEFAULT_DB_PATH)
    return str(Path(raw).expanduser())


def get_conn():
    return init_db(resolve_db_path())

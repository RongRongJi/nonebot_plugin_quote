from pydantic import BaseModel, Extra
from typing import List, Dict


class Config(BaseModel, extra=Extra.ignore):
    record_path: str = 'record.json'
    inverted_index_path: str = 'inverted_index.json'
    quote_superuser: Dict[str, List[str]] = {}
    global_superuser: List[str] = []
    quote_needat: bool = True
    quote_startcmd: str = ''
from pydantic import BaseModel, Extra
from typing import List, Dict


class Config(BaseModel, extra=Extra.ignore):
    record_path: str = ''
    inverted_index_path: str = ''
    quote_superuser: Dict[str, List[str]] = {}
    global_superuser: List[str] = []
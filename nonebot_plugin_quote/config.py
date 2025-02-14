from pydantic import BaseModel, Extra
from typing import List, Dict


class Config(BaseModel, extra=Extra.ignore):
    record_path: str = 'record.json'
    inverted_index_path: str = 'inverted_index.json'
    quote_superuser: Dict[str, List[str]] = {}
    global_superuser: List[str] = []
    quote_needat: bool = True
    quote_startcmd: str = ''
    quote_path: str = 'quote'
    font_path: str = 'font1'
    author_font_path: str = 'font2'

def check_font(font_path, author_font_path):
    # 判断字体是否配置
    return not (font_path == 'font1' or author_font_path == 'font2')
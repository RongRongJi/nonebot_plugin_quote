"""
配置文件，定义了插件的配置项和默认值。
"""
from typing import List, Dict

from pydantic import BaseModel


class Config(BaseModel, extra='ignore'):
    """配置类，定义了插件的配置项和默认值。
    
    record_path: 语录记录文件的路径，默认为 'record.json'。
    inverted_index_path: 反向索引文件的路径，默认为 'inverted_index.json'。
    quote_superuser: 语录管理员列表，默认为空字典。
    global_superuser: 全局管理员列表，默认为空列表。
    superusers: 语录管理员和全局管理员的集合。
    quote_needat: 是否需要@机器人才能触发语录，默认为True。
    quote_startcmd: 语录指令的起始命令，默认为空字符串。
    quote_path: 语录数据文件夹的路径，默认为 './data'。
    quote_needprefix: 是否需要指令前缀才能触发语录，默认为True。
    font_path: 语录字体文件的路径，默认为 'font1'。
    author_font_path: 语录作者字体文件的路径，默认为 'font2'。
    quote_upload: 是否允许上传语录，默认为True。
    quote_delete: 是否允许删除语录，默认为True。
    quote_modify_tags: 是否允许修改语录标签，默认为True。
    quote_enable_ocr: 是否启用OCR功能，默认为True。
    """
    record_path: str = 'record.json'
    inverted_index_path: str = 'inverted_index.json'
    quote_superuser: Dict[str, List[str]] = {}
    global_superuser: List[str] = []
    superusers: set[str]
    quote_needat: bool = True
    quote_startcmd: str = ''
    quote_path: str = './data'
    quote_needprefix: bool = True
    font_path: str = 'font1'
    author_font_path: str = 'font2'
    quote_upload: bool = True
    quote_delete: bool = True
    quote_modify_tags: bool = True
    quote_enable_ocr : bool = True

def check_font(font_path, author_font_path):
    """判断字体是否配置"""
    return not (font_path == 'font1' or author_font_path == 'font2')

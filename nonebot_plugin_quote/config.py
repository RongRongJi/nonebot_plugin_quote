from pydantic import BaseModel, Extra

class Config(BaseModel, extra=Extra.ignore):
    ocr_url : str = 'http://localhost:8089/api/tr-run/'
    record_path: str
    inverted_index_path: str
    tmp_dir: str



# external_data = {
#     'ocr_url':  'http://localhost:8089/api/tr-run/',
#     'record': '',
#     'inverted_index': '',
#     'tmp_dir': ''
# }


# config_data = Config(**external_data)



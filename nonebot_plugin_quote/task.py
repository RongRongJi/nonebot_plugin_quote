import asyncio
import pathlib
import os
import random
import hashlib
import json

import jieba
import httpx

from rapidocr import RapidOCR

from nonebot import get_driver
from nonebot.log import logger

from .config import Config

inverted_index_path = pathlib.Path(
    Config.model_validate(get_driver().config.model_dump()).inverted_index_path
)
record_path = pathlib.Path(
    Config.model_validate(get_driver().config.model_dump()).record_path
)
inverted_index = {}
record_dict = {}

if record_path.exists():
    record_dict = json.load(record_path.open(encoding="UTF-8", mode="r"))
    logger.info("nonebot_plugin_quote 路径配置成功")
else:
    json.dump(
        record_dict,
        record_path.open(encoding="UTF-8", mode="w"),
        indent=2,
        separators=(",", ": "),
        ensure_ascii=False,
    )
    logger.warning("已创建 json 文件")

if inverted_index_path.exists():
    inverted_index = json.load(inverted_index_path.open(encoding="UTF-8", mode="r"))
    logger.info("nonebot_plugin_quote 路径配置成功")
else:
    json.dump(
        inverted_index,
        inverted_index_path.open(encoding="UTF-8", mode="w"),
        indent=2,
        separators=(",", ": "),
        ensure_ascii=False,
    )
    logger.warning("已创建 json 文件")


# 倒排索引 转 正向索引
def inverted2forward(index):
    result = {}
    for qq_group in index.keys():
        result[qq_group] = {}
        for word, imgs in index[qq_group].items():
            for img in imgs:
                result[qq_group].setdefault(img, set()).add(word)
    return result


forward_index = inverted2forward(inverted_index)


def offer(group_id, img_file: pathlib.Path, content):
    """
    向语录库添加新的图片

    :param group_id: 群号
    :param img_file: 图片文件路径
    :type img_file: pathlib.Path
    :param content: 图片内容（用于分词）
    """

    # 分词
    cut_words = cut_sentence(content)
    # 群号是否在表中
    if group_id not in inverted_index:
        inverted_index[group_id] = {}
        forward_index[group_id] = {}

    forward_index[group_id][str(img_file)] = set(cut_words)
    # 分词是否在群的hashmap里
    for word in cut_words:
        if word not in inverted_index[group_id]:
            inverted_index[group_id][word] = [str(img_file)]
        else:
            inverted_index[group_id][word].append(str(img_file))

    if group_id not in record_dict:
        record_dict[group_id] = [str(img_file.absolute())]
    else:
        if str(img_file.absolute()) not in record_dict[group_id]:
            record_dict[group_id].append(str(img_file.absolute()))
    return inverted_index, forward_index


def quote_exists(group_id):
    """
    判断一个群是否有语录

    :param group_id: 群号
    """
    return group_id in record_dict and len(record_dict[group_id]) > 0

def image_exists(group_id, img_path):
    """
    判断一个图片是否在语录库中

    :param group_id: 群号
    :param img_path: 图片路径
    """
    return quote_exists(group_id) and img_path in record_dict[group_id]

# 倒排索引表查询图片
def random_quote(sentence, group_id) -> str:
    """
    随机选取一张图片返回

    :param sentence: 关键词。空串表示随机返回一个图片。
    :param group_id: 群号
    """
    if sentence == "":
        return random.choice(record_dict[group_id])
    if sentence.startswith("#"):
        cut_words = [sentence[1:]]
    else:
        cut_words = jieba.lcut_for_search(sentence)
        cut_words = list(set(cut_words))
    hash_map = inverted_index[group_id]
    count_map = {}
    result_pool = []
    for word in cut_words:
        if word not in hash_map:
            continue
        for img in hash_map[word]:
            if img not in count_map:
                count_map[img] = 1
            else:
                count_map[img] += 1
            if count_map[img] == len(cut_words):
                result_pool.append(img)

    if len(result_pool) == 0:
        return ""
    else:
        return random.choice(result_pool)


# 删除内容
def delete(img_name, group_id):
    check = False
    try:
        keys = list(inverted_index[group_id].keys())
        for key in keys:
            check = _remove(inverted_index[group_id][key], img_name) or check
            if len(inverted_index[group_id][key]) == 0:
                del inverted_index[group_id][key]

        check = _remove(record_dict[group_id], img_name) or check
        if len(record_dict[group_id]) == 0:
            del record_dict[group_id]

        for key in forward_index[group_id].keys():
            file_name = os.path.basename(key)
            if file_name.startswith(img_name):
                del forward_index[group_id][key]
                break

        return check, record_dict, inverted_index, forward_index
    except KeyError:
        return check, record_dict, inverted_index, forward_index


def _remove(arr, ele):
    old_len = len(arr)
    for name in arr:
        file_name = os.path.basename(name)
        if file_name.startswith(ele):
            arr.remove(name)
            break

    return len(arr) < old_len


def cut_sentence(sentence):
    cut_words = jieba.lcut_for_search(sentence)
    cut_words = list(set(cut_words))
    remove_set = set(
        [
            ".",
            ",",
            "!",
            "?",
            ":",
            ";",
            "。",
            "，",
            "！",
            "？",
            "：",
            "；",
            "%",
            "$",
            "\n",
            " ",
            "[",
            "]",
        ]
    )
    new_words = [word for word in cut_words if word not in remove_set]

    return new_words


# 输出所有tag
def findAlltag(img_name, group_id):
    for key, value in forward_index[group_id].items():
        file_name = os.path.basename(key)
        if file_name.startswith(img_name):
            return value


# 添加tag
def addTag(tags, img_name, group_id):
    # 是否存在
    path = None
    for key in forward_index[group_id].keys():
        file_name = os.path.basename(key)
        if file_name.startswith(img_name):
            path = key
            for tag in tags:
                forward_index[group_id][key].add(tag)
            break
    if path is None:
        return None, forward_index, inverted_index
    for tag in tags:
        inverted_index[group_id].setdefault(tag, []).append(path)
    return path, forward_index, inverted_index


# 删除tag
def delTag(tags, img_name, group_id):
    path = None
    for key in forward_index[group_id].keys():
        file_name = os.path.basename(key)
        if file_name.startswith(img_name):
            path = key
            for tag in tags:
                forward_index[group_id][key].discard(tag)
            break
    if path is None:
        return None, forward_index, inverted_index
    keys = list(inverted_index[group_id].keys())
    for tag in tags:
        if tag in keys and path in inverted_index[group_id][tag]:
            inverted_index[group_id][tag].remove(path)
            if len(inverted_index[group_id][tag]) == 0:
                del inverted_index[group_id][tag]
    return path, forward_index, inverted_index


IMAGE_EXTENSIONS = [".jpg", ".jpeg", ".png", ".gif"]


def copy_images_files(source, destinate):
    image_files = []
    destination_path = pathlib.Path(destinate)
    if not destination_path.exists():
        destination_path.mkdir(parents=True, exist_ok=True)
    for extension in IMAGE_EXTENSIONS:
        for file in pathlib.Path(source).rglob(f"*{extension}"):
            # 获得md5
            md5 = get_img_md5(str(file))
            tname = md5 + extension
            # 复制到目录
            file.copy(destination_path / tname)
            image_files.append((md5, tname))
    return image_files


def get_img_md5(img_path):
    """
    return: 图片的 md5 值

    :param img_path: 图片路径
    """
    return hashlib.md5(pathlib.Path(img_path).read_bytes()).hexdigest()


engine = RapidOCR()


def get_ocr_content(image_path):
    try:
        r = engine(image_path)
        if getattr(r, "txts", None) is None:
            return ""
        result = getattr(r, "txts")
        if result:
            ocr_content = " ".join([line for line in result])

            logger.info(f"RapidOCR 识别结果: {ocr_content}")

            return ocr_content.strip()
    except Exception as e:
        logger.warning(f"RapidOCR 识别失败喵: {e}")

    return ""


def dump_data():
    """
    dump data to json file
    """
    json.dump(
        record_dict,
        record_path.open(encoding="UTF-8", mode="w"),
        indent=2,
        separators=(",", ": "),
        ensure_ascii=False,
    )
    json.dump(
        inverted_index,
        inverted_index_path.open(encoding="UTF-8", mode="w"),
        indent=2,
        separators=(",", ": "),
        ensure_ascii=False,
    )


async def download_url(url: str) -> bytes:
    """
    从 url 下载图片，返回图片的二进制内容
    
    :param url: 说明
    :type url: str
    :return: 说明
    :rtype: bytes
    """
    async with httpx.AsyncClient() as client:
        for i in range(3):
            try:
                response = await client.get(url, timeout=10)
                response.raise_for_status()
                return response.content
            except httpx.HTTPError as e:
                logger.warning(f"Error downloading {url}, retry {i}/3: {e}")
                await asyncio.sleep(3)
    raise httpx.NetworkError(f"{url} 下载失败！")
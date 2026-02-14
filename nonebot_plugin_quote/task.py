import pathlib
import jieba
import os
import random
import hashlib

from rapidocr_onnxruntime import RapidOCR

# 向语录库添加新的图片
def offer(group_id, img_file: pathlib.Path, content, inverted_index, forward_index):
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

    return inverted_index, forward_index


# 倒排索引表查询图片
def query(sentence, group_id, inverted_index):
    if sentence.startswith("#"):
        cut_words = [sentence[1:]]
    else:
        cut_words = jieba.lcut_for_search(sentence)
        cut_words = list(set(cut_words))
    if group_id not in inverted_index:
        return {"status": -1}
    hash_map = inverted_index[group_id]
    count_map = {}
    result_pool = []
    for word in cut_words:
        if word not in hash_map:
            return {"status": 2}
        for img in hash_map[word]:
            if img not in count_map:
                count_map[img] = 1
            else:
                count_map[img] += 1
            if count_map[img] == len(cut_words):
                result_pool.append(img)

    if len(result_pool) == 0:
        return {"status": 2}
    idx = random.randint(0, len(result_pool) - 1)
    return {"status": 1, "msg": result_pool[idx]}


# 删除内容
def delete(img_name, group_id, record, inverted_index, forward_index):
    check = False
    try:
        keys = list(inverted_index[group_id].keys())
        for key in keys:
            check = _remove(inverted_index[group_id][key], img_name) or check
            if len(inverted_index[group_id][key]) == 0:
                del inverted_index[group_id][key]

        check = _remove(record[group_id], img_name) or check
        if len(record[group_id]) == 0:
            del record[group_id]

        for key in forward_index[group_id].keys():
            file_name = os.path.basename(key)
            if file_name.startswith(img_name):
                del forward_index[group_id][key]
                break

        return check, record, inverted_index, forward_index
    except KeyError:
        return check, record, inverted_index, forward_index


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


# 倒排索引 转 正向索引
def inverted2forward(inverted_index):
    forward_index = {}
    for qq_group in inverted_index.keys():
        forward_index[qq_group] = {}
        for word, imgs in inverted_index[qq_group].items():
            for img in imgs:
                forward_index[qq_group].setdefault(img, set()).add(word)
    return forward_index


# 输出所有tag
def findAlltag(img_name, forward_index, group_id):
    for key, value in forward_index[group_id].items():
        file_name = os.path.basename(key)
        if file_name.startswith(img_name):
            return value


# 添加tag
def addTag(tags, img_name, group_id, forward_index, inverted_index):
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
def delTag(tags, img_name, group_id, forward_index, inverted_index):
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
        result, _ = engine(image_path)

        if result:
            ocr_content = " ".join([line[1] for line in result])

            logger.info(f"RapidOCR 识别结果: {ocr_content}")

            return ocr_content.strip()
    except Exception as e:
        logger.warning(f"RapidOCR 识别失败喵: {e}")

    return ""

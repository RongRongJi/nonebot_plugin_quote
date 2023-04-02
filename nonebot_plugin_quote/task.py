import json
import jieba
import os
import random
import hashlib
import shutil


# 向语录库添加新的图片
def offer(group_id, img_file, content, inverted_index, forward_index):
    # 分词
    cut_words = cut_sentence(content)
    # 群号是否在表中
    if group_id not in inverted_index:
        inverted_index[group_id] = {}
        forward_index[group_id] = {}
        
    forward_index[group_id][img_file] = set(cut_words)
    # 分词是否在群的hashmap里
    for word in cut_words:
        if word not in inverted_index[group_id]:
            inverted_index[group_id][word] = [img_file]
        else:
            inverted_index[group_id][word].append(img_file)
    
    return inverted_index, forward_index


# 倒排索引表查询图片
def query(sentence, group_id, inverted_index):
    if sentence.startswith('#'):
        cut_words = [sentence[1:]]
    else:
        cut_words = jieba.lcut_for_search(sentence)
        cut_words = list(set(cut_words))
    if group_id not in inverted_index:
        return {'status': -1}
    hash_map = inverted_index[group_id]
    count_map = {}
    result_pool = []
    for word in cut_words:
        if word not in hash_map:
            return {'status': 2}
        for img in hash_map[word]:
            if img not in count_map:
                count_map[img] = 1
            else:
                count_map[img] += 1
            if count_map[img] == len(cut_words):
                    result_pool.append(img)
        
    if len(result_pool) == 0:
        return {'status': 2}
    idx = random.randint(0, len(result_pool)-1)
    return {'status': 1, 'msg': result_pool[idx]}


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



def handle_ocr_text(texts):
    _len_ = len(texts)
    if _len_ == 0:
        return ''
    ret = texts[0]['text']
    for i in range(1, _len_):
        _last_vectors = texts[i-1]['coordinates']
        _cur_vectors = texts[i]['coordinates']
        _last_width = _last_vectors[1]['x'] - _last_vectors[0]['x']
        _cur_width = _cur_vectors[1]['x'] - _cur_vectors[0]['x']
        _last_start = _last_vectors[0]['x']
        _cur_start = _cur_vectors[0]['x']

        _last_end = _last_vectors[1]['x']
        _cur_end = _cur_vectors[1]['x']
        # 起始点判断 误差在15以内 
        # 长度判断 上一句比下一句长 误差在5以内
        if abs(_cur_start - _last_start) <= 15 and _last_width + 5 > _cur_width:
            # 判定为长句换行了
            ret += texts[i]['text']
        # 终点判断 误差在15以内
        # 长度判断 上一句比下一句短 误差在5以内
        elif abs(_cur_end - _last_end) <= 15 and _cur_width + 5 > _last_width:
            # 判定为长句换行了
            ret += texts[i]['text']
        else:
            ret += '\n' + texts[i]['text']
    
    return ret


def cut_sentence(sentence):
    cut_words = jieba.lcut_for_search(sentence)
    cut_words = list(set(cut_words))
    remove_set = set(['.',',','!','?',':',';','。','，','！','？','：','；','%','$','\n',' ','[',']'])
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


IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.gif']
def copy_images_files(source, destinate):
    image_files = []
    for root,_,files in os.walk(source):
        for filename in files:
            extension = os.path.splitext(filename)[1].lower()
            if extension in IMAGE_EXTENSIONS:
                image_path = os.path.join(root, filename)
                # 获得md5
                md5 = get_img_md5(image_path) + '.image'
                tname = md5 + extension
                # 复制到目录
                destination_path = os.path.join(destinate, tname)
                shutil.copy(image_path, destination_path)
                image_files.append((md5, tname))
    return image_files


def get_img_md5(img_path):
    with open(img_path, 'rb') as f:
        img_data = f.read()
    md5 = hashlib.md5(img_data).hexdigest()
    return md5
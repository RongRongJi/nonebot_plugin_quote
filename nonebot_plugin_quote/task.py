import json
import jieba
import os
import random


# 向语录库添加新的图片
def offer(group_id, img_file, content, inverted_index):
    # 分词
    cut_words = jieba.lcut_for_search(content)
    cut_words = list(set(cut_words))
    # 群号是否在表中
    if group_id not in inverted_index:
        inverted_index[group_id] = {}
        
    # 分词是否在群的hashmap里
    for word in cut_words:
        if word not in inverted_index[group_id]:
            inverted_index[group_id][word] = [img_file]
        else:
            inverted_index[group_id][word].append(img_file)
    
    return inverted_index


# 倒排索引表查询图片
def query(sentence, group_id, inverted_index):
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
def delete(img_name, group_id, record, inverted_index):
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

        return check, record, inverted_index
    except KeyError:
        return check, record, inverted_index


def _remove(arr, ele):
    try:
        arr.remove(ele)
        return True
    except ValueError:
        return False



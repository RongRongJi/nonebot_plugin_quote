from nonebot import on_command, on_keyword, on_startswith, get_driver, on_regex
from nonebot.rule import to_me
from nonebot.matcher import Matcher
from nonebot.adapters import Message
from nonebot.params import Arg, ArgPlainText, CommandArg, Matcher
from nonebot.adapters.onebot.v11 import Bot, Event, Message, MessageEvent, PrivateMessageEvent, MessageSegment, GroupMessageEvent, exception
from nonebot.typing import T_State  
import nonebot
import re
import json
import base64
import random
import subprocess
import sys
import os
import shutil
from .task import offer, query, delete, handle_ocr_text, inverted2forward, findAlltag, addTag, delTag
from .task import copy_images_files
from .config import Config
from nonebot.log import logger
import time

# v0.3.5

plugin_config = Config.parse_obj(get_driver().config)

need_at = {}
if plugin_config.quote_needat:
    need_at['rule'] = to_me()


record_dict = {}
inverted_index = {}

# 首次运行时导入表
try:
    with open(plugin_config.record_path, 'r', encoding='UTF-8') as fr:
        record_dict = json.load(fr)

    with open(plugin_config.inverted_index_path, 'r', encoding='UTF-8') as fi:
        inverted_index = json.load(fi)
    logger.info('nonebot_plugin_quote路径配置成功')
except Exception as e:
    with open(plugin_config.record_path, 'w', encoding='UTF-8') as f:
        json.dump(record_dict, f, indent=2, separators=(',', ': '), ensure_ascii=False)

    with open(plugin_config.inverted_index_path, 'w', encoding='UTF-8') as fc:
        json.dump(inverted_index, fc, indent=2, separators=(',',': '), ensure_ascii=False)
    logger.warning('已创建json文件')


forward_index = inverted2forward(inverted_index)


# 回复信息处理
async def reply_handle(bot, errMsg, raw_message, groupNum, user_id, listener):

    # print(raw_message)
    if 'reply' not in raw_message:
        await bot.call_api('send_group_msg', **{
            'group_id':int(groupNum),
            'message': '[CQ:at,qq='+user_id+']' + errMsg
        })
        await listener.finish()
    
    # reply之后第一个等号，到数字后第一个非数字
    idx = raw_message.find('reply')
    reply_id = ''
    for i in range(idx, len(raw_message)):
        if raw_message[i] == '=':
            idx = i
            break
    for i in range(idx+1, len(raw_message)):
        if raw_message[i] != '-' and not raw_message[i].isdigit():
            break
        reply_id += raw_message[i]

    # print(reply_id)

    resp = await bot.get_msg(message_id=reply_id)

    img_msg = str(resp['message'])
    # print(img_msg)

    if '.image' not in img_msg:
        await bot.call_api('send_group_msg', **{
            'group_id':int(groupNum),
            'message': '[CQ:at,qq='+user_id+']' + errMsg
        })
        await listener.finish()
    
    idx = img_msg.find('.image')
    img = '.image'
    for i in range(0,32):
        img = img_msg[idx-i-1] + img
    
    # print(img)
    return img



 # 语录库
record = on_command("{}上传".format(plugin_config.quote_startcmd), priority=10, block=True, rule=to_me())
end_conversation = ['stop', '结束', '上传截图', '结束上传']


@record.handle()
async def _(event: MessageEvent, args: Message = CommandArg()):
    if isinstance(event, PrivateMessageEvent):
        await record.finish()

    plain_text = args.extract_plain_text()
    if plain_text:
        record.set_arg("prompt", message=args)


@record.got("prompt", prompt="请上传语录(图片形式)")
async def record_upload(bot: Bot, event: MessageEvent, prompt: Message = Arg(), msg: Message = Arg("prompt")):

    global inverted_index
    global record_dict
    global forward_index

    session_id = event.get_session_id()
    message_id = event.message_id

    if str(msg) in end_conversation:
        await record.finish('上传会话已结束')

    rt = r"\[CQ:image,file=(.*?),url=[\S]*\]"

    files = re.findall(rt, str(msg))
    files = [file.replace("&amp;", "&") for file in files]

    if len(files) == 0:
        resp = "请上传图片"
        await record.reject_arg('prompt', MessageSegment.reply(message_id) + resp)

    resp =  await bot.call_api('get_image',  **{'file':files[0]})

    # OCR分词
    try:
        ocr = await bot.ocr_image(image=files[0])

        ocr_content = handle_ocr_text(ocr['texts'])
    except exception.ActionFailed:
        ocr_content = ''


    if 'group' in session_id:
        tmpList = session_id.split('_')
        groupNum = tmpList[1]

        resp['file'] = resp['file'].replace('data/','../')

        inverted_index, forward_index = offer(groupNum, resp['file'], ocr_content, inverted_index, forward_index)

        if groupNum not in record_dict:
            record_dict[groupNum] = [resp['file']]
        else:
            if resp['file'] not in record_dict[groupNum]:
                record_dict[groupNum].append(resp['file'])


        with open(plugin_config.record_path, 'w', encoding='UTF-8') as f:
            json.dump(record_dict, f, indent=2, separators=(',', ': '), ensure_ascii=False)

        with open(plugin_config.inverted_index_path, 'w', encoding='UTF-8') as fc:
            json.dump(inverted_index, fc, indent=2, separators=(',',': '), ensure_ascii=False)

    # await record.reject_arg('prompt', MessageSegment.reply(message_id) + '上传成功')
    await bot.call_api('send_group_msg', **{
            'group_id':int(groupNum),
            'message': MessageSegment.reply(message_id) + '上传成功'
        })
    await record.finish('上传会话已结束')


record_pool = on_startswith('{}语录'.format(plugin_config.quote_startcmd), priority=2, block=True, **need_at)


@record_pool.handle()
async def record_pool_handle(bot: Bot, event: Event, state: T_State):

    session_id = event.get_session_id()
    user_id = str(event.get_user_id())

    global inverted_index
    global record_dict

    if 'group' in session_id:

        search_info = str(event.get_message()).strip()
        search_info = search_info.replace('{}语录'.format(plugin_config.quote_startcmd),'').replace(' ','')

        tmpList = session_id.split('_')
        groupNum = tmpList[1]

        if search_info == '':
            if groupNum not in record_dict:
                msg = '当前无语录库'
            else:
                length = len(record_dict[groupNum])
                idx = random.randint(0, length-1)
                msg = '[CQ:image,file={}]'.format(record_dict[groupNum][idx])
        else:
            ret = query(search_info, groupNum, inverted_index)

            if ret['status'] == -1:
                msg = '当前无语录库'
            elif ret['status'] == 2:
                if groupNum not in record_dict:
                    msg = '当前无语录库'
                else:
                    length = len(record_dict[groupNum])
                    idx = random.randint(0, length-1)
                    msg = '当前查询无结果, 为您随机发送。\n[CQ:image,file={}]'.format(record_dict[groupNum][idx])
            elif ret['status'] == 1:
                msg = '[CQ:image,file={}]'.format(ret['msg'])
            else:
                msg = ret.text

        await bot.call_api('send_group_msg', **{
            'group_id':int(groupNum),
            'message': msg
        })

    await record_pool.finish()


record_help = on_keyword({"语录"}, priority=10, rule=to_me())

@record_help.handle()
async def record_help_handle(bot: Bot, event: Event, state: T_State):

    session_id = event.get_session_id()
    user_id = str(event.get_user_id())
    raw_msg = str(event.get_message())
    if '怎么用' not in raw_msg and '如何' not in raw_msg:
        await record_help.finish()

    msg = '''您可以通过at我+上传, 开启上传语录通道; 再发送图片上传语录。您也可以直接发送【语录】指令, 我将随机返回一条语录。'''

    if 'group' in session_id:
        tmpList = session_id.split('_')
        groupNum = tmpList[1]

        await bot.call_api('send_group_msg', **{
            'group_id':int(groupNum),
            'message': '[CQ:at,qq='+user_id+']' + msg
        })

    await record_help.finish()


delete_record = on_command('{}删除'.format(plugin_config.quote_startcmd), aliases={'delete'}, **need_at)

@delete_record.handle()
async def delete_record_handle(bot: Bot, event: Event, state: T_State):

    global inverted_index
    global record_dict
    global forward_index

    session_id = event.get_session_id()
    user_id = str(event.get_user_id())

    if 'group' not in session_id:
        await delete_record.finish()
    
    groupNum = session_id.split('_')[1]
    if user_id not in plugin_config.global_superuser:
        if groupNum not in plugin_config.quote_superuser or user_id not in plugin_config.quote_superuser[groupNum]:  
            await bot.call_api('send_group_msg', **{
                'group_id':int(groupNum),
                'message': '[CQ:at,qq='+user_id+'] 非常抱歉, 您没有删除权限TUT'
            })
            await delete_record.finish()

    raw_message = str(event)

    errMsg = '请回复需要删除的语录, 并输入删除指令'
    imgs = await reply_handle(bot, errMsg, raw_message, groupNum, user_id, delete_record)
    
    # 搜索
    is_Delete, record_dict, inverted_index, forward_index = delete(imgs, groupNum, record_dict, inverted_index, forward_index)

    if is_Delete:
        with open(plugin_config.record_path, 'w', encoding='UTF-8') as f:
            json.dump(record_dict, f, indent=2, separators=(',', ': '), ensure_ascii=False)
        with open(plugin_config.inverted_index_path, 'w', encoding='UTF-8') as fc:
            json.dump(inverted_index, fc, indent=2, separators=(',',': '), ensure_ascii=False)
        msg = '删除成功'
    else:
        msg = '该图不在语录库中'


    await bot.call_api('send_group_msg', **{
        'group_id':int(groupNum),
        'message': '[CQ:at,qq='+user_id+']' + msg
    })

    await delete_record.finish()



alltag = on_command('{}alltag'.format(plugin_config.quote_startcmd), aliases={'{}标签'.format(plugin_config.quote_startcmd),'{}tag'.format(plugin_config.quote_startcmd)}, **need_at)

@alltag.handle()
async def alltag_handle(bot: Bot, event: Event, state: T_State):

    global inverted_index
    global record_dict
    global forward_index

    session_id = event.get_session_id()
    user_id = str(event.get_user_id())

    if 'group' not in session_id:
        await alltag.finish()

    groupNum = session_id.split('_')[1]
    raw_message = str(event)

    errMsg = '请回复需要指定语录'
    imgs = await reply_handle(bot, errMsg, raw_message, groupNum, user_id, alltag)

    tags = findAlltag(imgs, forward_index, groupNum)
    if tags is None:
        msg = '该语录不存在'
    else:
        msg = '该语录的所有Tag为: '
        for tag in tags:
            msg += tag + ' '

    await bot.call_api('send_group_msg', **{
        'group_id':int(groupNum),
        'message': '[CQ:at,qq='+user_id+']' + msg
    })

    await alltag.finish()


addtag = on_regex(pattern="^{}addtag\ ".format(plugin_config.quote_startcmd), **need_at)

@addtag.handle()
async def addtag_handle(bot: Bot, event: Event, state: T_State):

    global inverted_index
    global record_dict
    global forward_index

    session_id = event.get_session_id()
    user_id = str(event.get_user_id())
    tags = str(event.get_message()).replace('{}addtag'.format(plugin_config.quote_startcmd), '').strip().split(' ')

    if 'group' not in session_id:
        await addtag.finish()

    groupNum = session_id.split('_')[1]
    raw_message = str(event)

    errMsg = '请回复需要指定语录'
    imgs = await reply_handle(bot, errMsg, raw_message, groupNum, user_id, addtag)

    flag, forward_index, inverted_index = addTag(tags, imgs, groupNum, forward_index, inverted_index)
    with open(plugin_config.inverted_index_path, 'w', encoding='UTF-8') as fc:
        json.dump(inverted_index, fc, indent=2, separators=(',',': '), ensure_ascii=False)

    if flag is None:
        msg = '该语录不存在'
    else:
        msg = '已为该语录添加上{}标签'.format(tags)

    await bot.call_api('send_group_msg', **{
        'group_id':int(groupNum),
        'message': '[CQ:at,qq='+user_id+']' + msg
    })

    await addtag.finish()


deltag = on_regex(pattern="^{}deltag\ ".format(plugin_config.quote_startcmd), **need_at)

@deltag.handle()
async def deltag_handle(bot: Bot, event: Event, state: T_State):

    global inverted_index
    global record_dict
    global forward_index

    session_id = event.get_session_id()
    user_id = str(event.get_user_id())
    tags = str(event.get_message()).replace('{}deltag'.format(plugin_config.quote_startcmd), '').strip().split(' ')

    if 'group' not in session_id:
        await addtag.finish()

    groupNum = session_id.split('_')[1]
    raw_message = str(event)

    errMsg = '请回复需要指定语录'
    imgs = await reply_handle(bot, errMsg, raw_message, groupNum, user_id, deltag)

    flag, forward_index, inverted_index = delTag(tags, imgs, groupNum, forward_index, inverted_index)
    with open(plugin_config.inverted_index_path, 'w', encoding='UTF-8') as fc:
        json.dump(inverted_index, fc, indent=2, separators=(',',': '), ensure_ascii=False)

    if flag is None:
        msg = '该语录不存在'
    else:
        msg = '已移除该语录的{}标签'.format(tags)

    await bot.call_api('send_group_msg', **{
        'group_id':int(groupNum),
        'message': '[CQ:at,qq='+user_id+']' + msg
    })

    await deltag.finish()


script_batch = on_regex(pattern="^{}batch_upload".format(plugin_config.quote_startcmd), **need_at)

@script_batch.handle()
async def script_batch_handle(bot: Bot, event: Event, state: T_State):

    global inverted_index
    global record_dict
    global forward_index

    session_id = event.get_session_id()
    user_id = str(event.get_user_id())

    # 必须是超级管理员群聊
    if user_id not in plugin_config.global_superuser:
        await script_batch.finish()
    if 'group' not in session_id:
        await script_batch.finish('该功能暂不支持私聊')

    groupNum = session_id.split('_')[1]

    rqqid = r"qqgroup=(.*)\s"
    ryour_path =  r"your_path=(.*)\s"
    rgocq_path =  r"gocq_path=(.*)\s"
    rtags =  r"tags=(.*)"

    raw_msg = str(event.get_message())
    raw_msg = raw_msg.replace('\r','')
    group_id = re.findall(rqqid, raw_msg)
    your_path = re.findall(ryour_path, raw_msg)
    gocq_path = re.findall(rgocq_path, raw_msg)
    tags = re.findall(rtags, raw_msg)
    # print(group_id, your_path, gocq_path, tags)
    instruction = '''指令如下:
batch_upload
qqgroup=123456
your_path=/home/xxx/images
gocq_path=/home/xxx/gocq/data/cache
tags=aaa bbb ccc'''
    if len(group_id) == 0 or len(your_path) == 0 or len(gocq_path) == 0:
        await script_batch.finish(instruction)
    # 获取图片
    # image_files = copy_images_files('/home/sr/project/data','/home/sr/newgocq/data/cache')
    image_files = copy_images_files(your_path[0], gocq_path[0])
    # print(image_files)

    total_len = len(image_files)
    idx = 0

    for (imgid, img) in image_files:
        save_file = '../cache/' + img
        idx += 1
        msg_id = await bot.send_msg(group_id=int(groupNum), message='[CQ:image,file={}]'.format(save_file))
        time.sleep(2)
        if group_id[0] in forward_index and save_file in forward_index[group_id[0]]:
            await bot.send_msg(group_id=int(groupNum), message='上述图片已存在')
            continue
        try:
            ocr = await bot.ocr_image(image=imgid)
            ocr_content = handle_ocr_text(ocr['texts'])
        except exception.ActionFailed:
            await bot.send_msg(group_id=int(groupNum), message='该图片ocr失败')
            continue
        
        time.sleep(1)
        inverted_index, forward_index = offer(group_id[0], save_file, ocr_content, inverted_index, forward_index)
        if group_id[0] not in record_dict:
            record_dict[group_id[0]] = [save_file]
        else:
            if save_file not in record_dict[group_id[0]]:
                record_dict[group_id[0]].append(save_file)
        
        if len(tags) != 0:
            tags = tags[0].strip().split(' ')
            flag, forward_index, inverted_index = addTag(tags, imgid, group_id[0], forward_index, inverted_index)
        
        # 每5张语录持久化一次
        if idx % 5 == 0:
            with open(plugin_config.record_path, 'w', encoding='UTF-8') as f:
                json.dump(record_dict, f, indent=2, separators=(',', ': '), ensure_ascii=False)

            with open(plugin_config.inverted_index_path, 'w', encoding='UTF-8') as fc:
                json.dump(inverted_index, fc, indent=2, separators=(',',': '), ensure_ascii=False)
            
            await bot.send_msg(group_id=int(groupNum), message='当前进度{}/{}'.format(idx, total_len))

    with open(plugin_config.record_path, 'w', encoding='UTF-8') as f:
        json.dump(record_dict, f, indent=2, separators=(',', ': '), ensure_ascii=False)

    with open(plugin_config.inverted_index_path, 'w', encoding='UTF-8') as fc:
        json.dump(inverted_index, fc, indent=2, separators=(',',': '), ensure_ascii=False)

    await bot.send_msg(group_id=int(groupNum), message='批量导入完成')
    await script_batch.finish()



copy_batch = on_regex(pattern="^{}batch_copy".format(plugin_config.quote_startcmd), **need_at)

@copy_batch.handle()
async def copy_batch_handle(bot: Bot, event: Event, state: T_State):

    session_id = event.get_session_id()
    user_id = str(event.get_user_id())

    # 必须是超级管理员群聊
    if user_id not in plugin_config.global_superuser:
        await copy_batch.finish()


    ryour_path =  r"your_path=(.*)\s"
    rgocq_path =  r"gocq_path=(.*)"

    raw_msg = str(event.get_message())
    raw_msg = raw_msg.replace('\r','')
    your_path = re.findall(ryour_path, raw_msg)
    gocq_path = re.findall(rgocq_path, raw_msg)
    # print(your_path, gocq_path)
    instruction = '''指令如下:
batch_copy
your_path=/home/xxx/images
gocq_path=/home/xxx/gocq/data/cache'''
    if len(your_path) == 0 or len(gocq_path) == 0:
        await copy_batch.finish(instruction)

    global record_dict

    try:
        for value in record_dict.values():
            for img in value:
                num = len(img) - 8
                name = img[-num:]
                shutil.copyfile(gocq_path[0] + name, your_path[0] + name)
    except FileNotFoundError:
        await copy_batch.finish("路径不正确")
    await copy_batch.finish("备份完成")

from nonebot import on_command, on_keyword, on_startswith, get_driver, on_regex
from nonebot.rule import to_me
from nonebot.adapters import Message
from nonebot.params import Arg, ArgPlainText, CommandArg
from nonebot.adapters.onebot.v11 import Bot, Event, Message, MessageEvent, PrivateMessageEvent, MessageSegment, exception
from nonebot.typing import T_State  
from nonebot.plugin import PluginMetadata
import re
import json
import random
import os
import shutil
from .task import offer, query, delete, handle_ocr_text, inverted2forward, findAlltag, addTag, delTag
from .task import copy_images_files
from .config import Config, check_font
from nonebot.log import logger
import time
from paddleocr import PaddleOCR
from PIL import Image
import io
import httpx
import hashlib
import uuid
from .make_image import generate_quote_image

# v0.4.2

__plugin_meta__ = PluginMetadata(
    name='群聊语录库',
    description='一款QQ群语录库——支持上传聊天截图为语录，随机投放语录，关键词搜索语录精准投放',
    usage='语录 上传 删除',
    type="application",
    homepage="https://github.com/RongRongJi/nonebot_plugin_quote",
    config=Config,
    supported_adapters={"~onebot.v11"},
    extra={
        'author': 'RongRongJi',
        'version': 'v0.4.2',
    },
)

plugin_config = Config.parse_obj(get_driver().config.dict())

need_at = {}
if (plugin_config.quote_needat):
    need_at['rule'] = to_me()

record_dict = {}
inverted_index = {}
quote_path = plugin_config.quote_path
font_path = plugin_config.font_path
author_font_path = plugin_config.author_font_path 

# 判断参数配置情况
if quote_path == 'quote':
    quote_path = './data'
    logger.warning('未配置quote文件路径，使用默认配置: ./data')
os.makedirs(quote_path, exist_ok=True)

if not check_font(font_path, author_font_path):
    logger.warning('未配置字体路径，部分功能无法使用')
    
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
        json.dump(inverted_index, fc, indent=2, separators=(',', ': '), ensure_ascii=False)
    logger.warning('已创建json文件')


forward_index = inverted2forward(inverted_index)


# 回复信息处理
async def reply_handle(bot, errMsg, raw_message, groupNum, user_id, listener):
    print(raw_message)
    if 'reply' not in raw_message:
        await bot.call_api('send_group_msg', **{
            'group_id': int(groupNum),
            'message': '[CQ:at,qq=' + user_id + ']' + errMsg
        })
        await listener.finish()

    # reply之后第一个等号，到数字后第一个非数字
    idx = raw_message.find('reply')
    reply_id = ''
    for i in range(idx, len(raw_message)):
        if raw_message[i] == '=':
            idx = i
            break
    for i in range(idx + 1, len(raw_message)):
        if raw_message[i] != '-' and not raw_message[i].isdigit():
            break
        reply_id += raw_message[i]

    resp = await bot.get_msg(message_id=reply_id)
    img_msg = resp['message']

    # 检查消息中是否包含图片
    image_found = False
    for msg_part in img_msg:
        if msg_part['type'] == 'image':
            image_found = True
            file_name = msg_part['data']['file']
            if file_name.startswith('http'):
                raw_filename = msg_part['data'].get('filename', 'image.jpg').upper()
                name, _ = os.path.splitext(raw_filename)
                file_name = name + ".png"
                break
            image_info = await bot.call_api('get_image', file=file_name)
            file_name = os.path.basename(image_info['file'])
            break
            
    if not image_found:
        await bot.send_msg(group_id=int(groupNum), message=MessageSegment.at(user_id) + errMsg)
        await listener.finish()

    return file_name

 # 语录库

save_img = on_regex(pattern="^{}上传$".format(re.escape(plugin_config.quote_startcmd)), **need_at)

@save_img.handle()
async def save_img_handle(bot: Bot, event: MessageEvent, state: T_State):

    session_id = event.get_session_id()
    message_id = event.message_id

    global inverted_index
    global record_dict
    global forward_index

    print(event.reply.message)
    if event.reply:
        raw_message = str(event.reply.message)
        match = re.search(r'file=([^,]+)', raw_message)
        if match:
            file_name = match.group(1).strip('"\'')
        else:
            await make_record.finish("未检测到图片，请回复所需上传的图片消息来上传语录")
    else:
        await make_record.finish("请回复所需上传的图片消息来上传语录")

    try:
        resp = await bot.call_api('get_image', **{'file': file_name})
        image_path = resp['file']
        shutil.copy(image_path, os.path.join(quote_path, os.path.basename(image_path)))
    
    except Exception as e:
        logger.warning(f"bot.call_api 失败，可能在使用Lagrange，使用 httpx 进行下载: {e}")
        image_url = file_name
        match = re.search(r'filename=([^,]+)', raw_message)
        file_name = match.group(1).strip('"\'')
        async with httpx.AsyncClient() as client:
            image_url = image_url.replace('&amp;', '&')
            response = await client.get(image_url)
            if response.status_code == 200:
                image_path = os.path.join(quote_path, file_name)
                with open(image_path, "wb") as f:
                    f.write(response.content)
                resp = {"file": image_path}
            else:
                raise Exception("httpx 下载失败")
    
    image_path = os.path.abspath(os.path.join(quote_path, os.path.basename(image_path)))
    logger.info(f"图片已保存到 {image_path}")
    # OCR分词
    # 初始化PaddleOCR
    ocr = PaddleOCR(use_angle_cls=True, lang='ch')
    try:
        # 使用PaddleOCR进行OCR识别
        ocr_result = ocr.ocr(image_path, cls=True)
        # 处理OCR识别结果
        ocr_content = ''
        for line in ocr_result:
            for word in line:
                ocr_content += word[1][0] + ' '
    except Exception as e:
        ocr_content = ''
        print(f"OCR识别失败: {e}")


    if 'group' in session_id:
        tmpList = session_id.split('_')
        groupNum = tmpList[1]

        inverted_index, forward_index = offer(groupNum, image_path, ocr_content, inverted_index, forward_index)

        if groupNum not in record_dict:
            record_dict[groupNum] = [image_path]
        else:
            if image_path not in record_dict[groupNum]:
                record_dict[groupNum].append(image_path)


        with open(plugin_config.record_path, 'w', encoding='UTF-8') as f:
            json.dump(record_dict, f, indent=2, separators=(',', ': '), ensure_ascii=False)

        with open(plugin_config.inverted_index_path, 'w', encoding='UTF-8') as fc:
            json.dump(inverted_index, fc, indent=2, separators=(',', ': '), ensure_ascii=False)

    await bot.call_api('send_group_msg', **{
            'group_id': int(groupNum),
            'message': MessageSegment.reply(message_id) + '保存成功'
        })


record_pool = on_startswith('{}语录'.format(plugin_config.quote_startcmd), priority=2, block=True, **need_at)

@record_pool.handle()
async def record_pool_handle(bot: Bot, event: Event, state: T_State):

    session_id = event.get_session_id()
    user_id = str(event.get_user_id())

    global inverted_index
    global record_dict

    if 'group' in session_id:

        search_info = str(event.get_message()).strip()
        search_info = search_info.replace('{}语录'.format(plugin_config.quote_startcmd), '').replace(' ', '')

        tmpList = session_id.split('_')
        groupNum = tmpList[1]

        if search_info == '':
            if groupNum not in record_dict:
                msg = '当前无语录库'
            else:
                length = len(record_dict[groupNum])
                idx = random.randint(0, length - 1)
                msg = MessageSegment.image(file=record_dict[groupNum][idx])
        else:
            ret = query(search_info, groupNum, inverted_index)

            if ret['status'] == -1:
                msg = '当前无语录库'
            elif ret['status'] == 2:
                if groupNum not in record_dict:
                    msg = '当前无语录库'
                else:
                    length = len(record_dict[groupNum])
                    idx = random.randint(0, length - 1)
                    msg = '当前查询无结果, 为您随机发送。'
                    msg_segment = MessageSegment.image(file=record_dict[groupNum][idx])
                    msg = msg + msg_segment
            elif ret['status'] == 1:
                msg = MessageSegment.image(file=ret['msg'])
            else:
                msg = ret.text

        response = await bot.call_api('send_group_msg', **{
            'group_id': int(groupNum),
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

    msg = '''您可以通过回复指定图片, 发送【上传】指令上传语录。您也可以直接发送【语录】指令, 我将随机返回一条语录。'''

    if 'group' in session_id:
        tmpList = session_id.split('_')
        groupNum = tmpList[1]

        await bot.call_api('send_group_msg', **{
            'group_id': int(groupNum),
            'message': MessageSegment.at(user_id) + msg
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
                'group_id': int(groupNum),
                'message': MessageSegment.at(user_id) + ' 非常抱歉, 您没有删除权限TUT'
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
            json.dump(inverted_index, fc, indent=2, separators=(',', ': '), ensure_ascii=False)
        msg = '删除成功'
    else:
        msg = '该图不在语录库中'

    await delete_record.finish(group_id=int(groupNum), message=MessageSegment.at(user_id) + msg)


alltag = on_command('{}alltag'.format(plugin_config.quote_startcmd), aliases={'{}标签'.format(plugin_config.quote_startcmd), '{}tag'.format(plugin_config.quote_startcmd)}, **need_at)

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

    await alltag.finish(group_id=int(groupNum), message=MessageSegment.at(user_id) + msg)

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
        json.dump(inverted_index, fc, indent=2, separators=(',', ': '), ensure_ascii=False)

    if flag is None:
        msg = '该语录不存在'
    else:
        msg = '已为该语录添加上{}标签'.format(tags)

    await addtag.finish(group_id=int(groupNum), message=MessageSegment.at(user_id) + msg)


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
        await deltag.finish()

    groupNum = session_id.split('_')[1]
    raw_message = str(event)

    errMsg = '请回复需要指定语录'
    imgs = await reply_handle(bot, errMsg, raw_message, groupNum, user_id, deltag)

    flag, forward_index, inverted_index = delTag(tags, imgs, groupNum, forward_index, inverted_index)
    with open(plugin_config.inverted_index_path, 'w', encoding='UTF-8') as fc:
        json.dump(inverted_index, fc, indent=2, separators=(',', ': '), ensure_ascii=False)

    if flag is None:
        msg = '该语录不存在'
    else:
        msg = '已移除该语录的{}标签'.format(tags)
    await deltag.finish(group_id=int(groupNum), message=MessageSegment.at(user_id) + msg)


make_record = on_regex(pattern="^{}记录$".format(re.escape(plugin_config.quote_startcmd)))

@make_record.handle()
async def make_record_handle(bot: Bot, event: MessageEvent, state: T_State):

    if not check_font(font_path, author_font_path):
        # 字体没配置就返回
        logger.warning('未配置字体路径，部分功能无法使用')
        await make_record.finish()

    global inverted_index
    global record_dict
    global forward_index

    if event.reply:
        size = 640
        qqid = event.reply.sender.user_id
        raw_message = event.reply.message.extract_plain_text().strip()
        card = event.reply.sender.card if event.reply.sender.card not in (None, '') else event.reply.sender.nickname
        session_id = event.get_session_id()
    else:
        await make_record.finish("请回复所需的消息")

    if str(qqid) == str(event.get_user_id()):
        await make_record.finish("不能记录自己的消息")

    if raw_message:

        url = f"http://q1.qlogo.cn/g?b=qq&nk={qqid}&s={size}"

        async def download_url(url: str) -> bytes:
            async with httpx.AsyncClient() as client:
                for i in range(3):
                    try:
                        resp = await client.get(url, timeout=10)
                        resp.raise_for_status()
                        return resp.content
                    except Exception as e:
                        logger.warning(f"Error downloading {url}, retry {i}/3: {e}")
                        await asyncio.sleep(3)
            raise NetworkError(f"{url} 下载失败！")

        data = await download_url(url)
        if hashlib.md5(data).hexdigest() == "acef72340ac0e914090bd35799f5594e":
            url = f"http://q1.qlogo.cn/g?b=qq&nk={qqid}&s=100"
            data = await download_url(url)

        if data:
            image_file = io.BytesIO(data)
            img_data = generate_quote_image(image_file, raw_message, card, font_path, author_font_path)

            image_name = hashlib.md5(img_data).hexdigest() + '.png'

            image_path = os.path.abspath(os.path.join(quote_path, os.path.basename(image_name)))

            with open(image_path, "wb") as file:
                file.write(img_data)

            if 'group' in session_id:
                tmpList = session_id.split('_')
                groupNum = tmpList[1]

                inverted_index, forward_index = offer(groupNum, image_path, card + ' ' + raw_message, inverted_index, forward_index)

                if groupNum not in record_dict:
                    record_dict[groupNum] = [image_path]
                else:
                    if image_path not in record_dict[groupNum]:
                        record_dict[groupNum].append(image_path)

                with open(plugin_config.record_path, 'w', encoding='UTF-8') as f:
                    json.dump(record_dict, f, indent=2, separators=(',', ': '), ensure_ascii=False)

                with open(plugin_config.inverted_index_path, 'w', encoding='UTF-8') as fc:
                    json.dump(inverted_index, fc, indent=2, separators=(',', ': '), ensure_ascii=False)

            msg = MessageSegment.image(img_data)
            response = await bot.call_api('send_group_msg', **{
                'group_id': int(groupNum),
                'message': msg
            })
    else:
        await make_record.send('空内容')
    await make_record.finish()

render_quote = on_regex(pattern="^{}生成$".format(re.escape(plugin_config.quote_startcmd)))

@render_quote.handle()
async def render_quote_handle(bot: Bot, event: MessageEvent, state: T_State):

    if not check_font(font_path, author_font_path):
        # 字体没配置就返回
        logger.warning('未配置字体路径，部分功能无法使用')
        await make_record.finish()

    global inverted_index
    global record_dict
    global forward_index

    if event.reply:
        size = 640
        qqid = event.reply.sender.user_id
        raw_message = event.reply.message.extract_plain_text().strip()
        card = event.reply.sender.card if event.reply.sender.card not in (None, '') else event.reply.sender.nickname
        session_id = event.get_session_id()
    else:
        await make_record.finish("请回复所需的消息")

    if raw_message:

        url = f"http://q1.qlogo.cn/g?b=qq&nk={qqid}&s={size}"

        async def download_url(url: str) -> bytes:
            async with httpx.AsyncClient() as client:
                for i in range(3):
                    try:
                        resp = await client.get(url, timeout=10)
                        resp.raise_for_status()
                        return resp.content
                    except Exception as e:
                        logger.warning(f"Error downloading {url}, retry {i}/3: {e}")
                        await asyncio.sleep(3)
            raise NetworkError(f"{url} 下载失败！")

        data = await download_url(url)
        if hashlib.md5(data).hexdigest() == "acef72340ac0e914090bd35799f5594e":
            url = f"http://q1.qlogo.cn/g?b=qq&nk={qqid}&s=100"
            data = await download_url(url)

        if data:
            image_file = io.BytesIO(data)
            img_data = generate_quote_image(image_file, raw_message, card, font_path, author_font_path)
            
            msg = MessageSegment.image(img_data)
            response = await bot.call_api('send_group_msg', **{
                'group_id': int(session_id.split('_')[1]),
                'message': msg
            })
    else:
        await render_quote.send('空内容')

    await render_quote.finish()




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
    raw_msg = raw_msg.replace('\r', '')
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
    image_files = copy_images_files(your_path[0], gocq_path[0])


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
            # 将image文件转换为PIL Image对象
            image = Image.open(io.BytesIO(imgid), 'utf-8')
            # 将PIL Image对象保存到临时路径
            temp_image_path = 'temp_image.jpg'
            image.save(temp_image_path)
            ocr = PaddleOCR(use_angle_cls=True, lang='ch')
            # 使用PaddleOCR进行OCR识别
            ocr_result = ocr.ocr(temp_image_path, cls=True)
            # 处理OCR识别结果
            ocr_content = ''
            for line in ocr_result:
                for word in line:
                    ocr_content += word[1][0] + ' '
            ocr_content = handle_ocr_text(ocr_content)

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
                json.dump(inverted_index, fc, indent=2, separators=(',', ': '), ensure_ascii=False)
            
            await bot.send_msg(group_id=int(groupNum), message='当前进度{}/{}'.format(idx, total_len))

    with open(plugin_config.record_path, 'w', encoding='UTF-8') as f:
        json.dump(record_dict, f, indent=2, separators=(',', ': '), ensure_ascii=False)

    with open(plugin_config.inverted_index_path, 'w', encoding='UTF-8') as fc:
        json.dump(inverted_index, fc, indent=2, separators=(',', ': '), ensure_ascii=False)

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
    rgocq_path =  r"gocq_path=(.*)\s"

    raw_msg = str(event.get_message())
    raw_msg = raw_msg.replace('\r', '')
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

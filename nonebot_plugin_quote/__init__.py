import time
import io
import hashlib
import re
import json
import asyncio
import os
import shutil
import pathlib
import httpx

from nonebot import (
    on_command,
    on_keyword,
    on_startswith,
    get_driver,
    on_regex,
    on_message,
    require,
)
from nonebot.rule import to_me
from nonebot.adapters.onebot.v11 import (
    Bot,
    Event,
    Message,
    MessageEvent,
    MessageSegment,
    GroupMessageEvent,
)
from nonebot.plugin import PluginMetadata
from nonebot.log import logger

require("nonebot_plugin_apscheduler")

# pylint: disable=wrong-import-position
from nonebot_plugin_apscheduler import scheduler

from .task import (
    offer,
    random_quote,
    delete,
    findAlltag,
    addTag,
    delTag,
    get_ocr_content,
    copy_images_files,
    quote_exists,
    download_url,
    image_exists,
    dump_data,
)

from .config import Config, check_font
from .make_image import generate_quote_image


__plugin_meta__ = PluginMetadata(
    name="群聊语录库",
    description="一款QQ群语录库——支持上传聊天截图为语录，随机投放语录，关键词搜索语录精准投放",
    usage="语录 上传 删除",
    type="application",
    homepage="https://github.com/RongRongJi/nonebot_plugin_quote",
    config=Config,
    supported_adapters={"~onebot.v11"},
    extra={
        "author": "RongRongJi",
        "version": "v0.4.3",
    },
)

driver = get_driver()

plugin_config = Config.model_validate(driver.config.model_dump())
plugin_config.global_superuser = list(
    {*plugin_config.global_superuser, *plugin_config.superusers}
)

need_at = {}
if plugin_config.quote_needat:
    need_at["rule"] = to_me()

QUOTE_PATH = pathlib.Path(plugin_config.quote_path)
font_path = plugin_config.font_path
author_font_path = plugin_config.author_font_path

# 判断参数配置情况
(QUOTE_PATH.mkdir(exist_ok=True))

if not check_font(font_path, author_font_path):
    logger.warning("未配置字体路径，部分功能无法使用")

# 首次运行时导入表


async def reply_handle(bot, error_message, raw_message, group_id, user_id, listener):
    """
    处理回复信息
    """
    print(raw_message)
    if "reply" not in raw_message:
        await bot.call_api(
            "send_group_msg",
            **{
                "group_id": int(group_id),
                "message": "[CQ:at,qq=" + user_id + "]" + error_message,
            },
        )
        await listener.finish()

    # reply之后第一个等号，到数字后第一个非数字
    idx = raw_message.find("reply")
    reply_id = ""
    for i in range(idx, len(raw_message)):
        if raw_message[i] == "=":
            idx = i
            break
    for i in range(idx + 1, len(raw_message)):
        if raw_message[i] != "-" and not raw_message[i].isdigit():
            break
        reply_id += raw_message[i]

    resp = await bot.get_msg(message_id=reply_id)
    img_msg = resp["message"]

    # 检查消息中是否包含图片
    image_found = False
    file_name = ""
    for msg_part in img_msg:
        if msg_part["type"] == "image":
            image_found = True
            file_name = msg_part["data"]["file"]
            if file_name.startswith("http"):
                raw_filename = msg_part["data"].get("filename", "image.jpg").upper()
                name, _ = os.path.splitext(raw_filename)
                file_name = name + ".png"
                break
            image_info = await bot.call_api("get_image", file=file_name)
            file_name = os.path.basename(image_info["file"])
            break

    if not image_found:
        await bot.send_msg(
            group_id=int(group_id), message=MessageSegment.at(user_id) + error_message
        )
        await listener.finish()

    return file_name


def random_quote_handle(sentence, group_id):
    """
    随机选取一张图片返回

    :param sentence: 关键词。空串表示随机返回一个图片。
    :param group_id: 群号
    """
    if not quote_exists(group_id):
        return "当前无语录库"
    image = random_quote(sentence, group_id)
    message = ""
    if image == "":
        message = "当前查询无结果, 为您随机发送。"
        image = random_quote("", group_id)
    return message + MessageSegment.image(file=image)


# 语录库

save_img = on_regex(
    pattern=f"^{re.escape(plugin_config.quote_startcmd)}上传$", **need_at
)


@save_img.handle()
async def save_img_handle(bot: Bot, event: MessageEvent):
    """
    处理保存图片请求。
    """
    if not plugin_config.quote_upload:
        await save_img.finish("管理员已关闭上传功能TUT")

    session_id = event.get_session_id()
    message_id = event.message_id

    file_name = ""
    if event.reply:
        raw_message = str(event.reply.message)
        logger.debug(raw_message)
        match = re.search(r"file=([^,]+)", raw_message)
        if match:
            file_name = match.group(1).strip("\"'")
        else:
            await save_img.finish("未检测到图片，请回复所需上传的图片消息来上传语录")
    else:
        await save_img.finish("请回复所需上传的图片消息来上传语录")

    try:
        response = await bot.get_image(file=file_name)
        source_path = pathlib.Path(response["file"])
        source_path.copy_into(QUOTE_PATH)
        image_path = QUOTE_PATH / source_path.name
    except Exception as e:
        logger.warning(
            f"bot.call_api 失败，可能在使用Lagrange，使用 httpx 进行下载: {e}"
        )
        image_url = file_name
        async with httpx.AsyncClient() as client:
            image_url = image_url.replace("&amp;", "&")
            response = await client.get(image_url)
            response.raise_for_status()
            image_path = QUOTE_PATH / file_name
            image_path.write_bytes(response.content)

    image_path = image_path.absolute()
    logger.info(f"图片已保存到 {image_path}")
    # OCR分词
    # 初始化PaddleOCR
    if plugin_config.quote_enable_ocr:
        ocr_content = get_ocr_content(image_path)
    else:
        ocr_content = ""

    if "group" in session_id:
        group_id = session_id.split("_")[1]

        offer(group_id, pathlib.Path(image_path), ocr_content)

    await save_img.finish(message=MessageSegment.reply(message_id) + "保存成功")


record_pool = on_startswith(
    f"{plugin_config.quote_startcmd}语录", priority=2, block=True, **need_at
)


@record_pool.handle()
async def record_pool_handle(event: GroupMessageEvent):
    """
    处理“语录”指令。

    :param bot: 收到指令的 bot。
    :param event: 收到的事件对象，包含消息内容、发送者信息等。
    """

    session_id = event.get_session_id()

    if "group" in session_id:

        search_info = str(event.get_message()).strip()
        search_info = search_info.replace(
            f"{plugin_config.quote_startcmd}语录", ""
        ).replace(" ", "")

        group_id = session_id.split("_")[1]

        await record_pool.finish(Message(random_quote_handle(search_info, group_id)))


record_help = on_keyword({"语录"}, priority=10, rule=to_me())


@record_help.handle()
async def record_help_handle(bot: Bot, event: Event):

    session_id = event.get_session_id()
    user_id = str(event.get_user_id())
    raw_msg = str(event.get_message())
    if "怎么用" not in raw_msg and "如何" not in raw_msg:
        await record_help.finish()

    msg = """您可以通过回复指定图片, 发送【上传】指令上传语录。您也可以直接发送【语录】指令, 我将随机返回一条语录。"""

    if "group" in session_id:
        tmpList = session_id.split("_")
        group_id = tmpList[1]

        await bot.call_api(
            "send_group_msg",
            **{"group_id": int(group_id), "message": MessageSegment.at(user_id) + msg},
        )

    await record_help.finish()


delete_record = on_regex(
    pattern=r"^{}删除$".format(re.escape(plugin_config.quote_startcmd)), **need_at
)


@delete_record.handle()
async def delete_record_handle(bot: Bot, event: Event):
    if not plugin_config.quote_delete:
        await delete_record.finish("管理员已关闭删除功能TUT")

    session_id = event.get_session_id()
    user_id = str(event.get_user_id())

    if "group" not in session_id:
        await delete_record.finish()

    group_id = session_id.split("_")[1]
    if user_id not in plugin_config.global_superuser:
        if (
            group_id not in plugin_config.quote_superuser
            or user_id not in plugin_config.quote_superuser[group_id]
        ):
            await bot.call_api(
                "send_group_msg",
                **{
                    "group_id": int(group_id),
                    "message": MessageSegment.at(user_id)
                    + " 非常抱歉, 您没有删除权限TUT",
                },
            )
            await delete_record.finish()

    raw_message = str(event)

    errMsg = "请回复需要删除的语录, 并输入删除指令"
    imgs = await reply_handle(
        bot, errMsg, raw_message, group_id, user_id, delete_record
    )

    # 搜索
    is_delete, _, _, _ = delete(imgs, group_id)

    if is_delete:
        msg = "删除成功"
    else:
        msg = "该图不在语录库中"

    await delete_record.finish(
        group_id=int(group_id), message=MessageSegment.at(user_id) + msg
    )


alltag = on_command(
    f"{plugin_config.quote_startcmd}alltag".format(),
    aliases={
        f"{plugin_config.quote_startcmd}标签",
        f"{plugin_config.quote_startcmd}tag",
    },
    **need_at,
)


@alltag.handle()
async def alltag_handle(bot: Bot, event: Event):

    session_id = event.get_session_id()
    user_id = str(event.get_user_id())

    if "group" not in session_id:
        await alltag.finish()

    group_id = session_id.split("_")[1]
    raw_message = str(event)

    errMsg = "请回复需要指定语录"
    imgs = await reply_handle(bot, errMsg, raw_message, group_id, user_id, alltag)
    tags = findAlltag(imgs, group_id)
    if tags is None:
        msg = "该语录不存在"
    else:
        msg = "该语录的所有Tag为: "
        for tag in tags:
            msg += tag + " "

    await alltag.finish(
        group_id=int(group_id), message=MessageSegment.at(user_id) + msg
    )


addtag = on_regex(pattern=f"^{plugin_config.quote_startcmd}addtag\\ ", **need_at)


@addtag.handle()
async def addtag_handle(bot: Bot, event: Event):
    if not plugin_config.quote_modify_tags:
        await alltag.finish("管理员已关闭修改标签功能TUT")

    session_id = event.get_session_id()
    user_id = str(event.get_user_id())
    tags = (
        str(event.get_message())
        .replace("{}addtag".format(plugin_config.quote_startcmd), "")
        .strip()
        .split(" ")
    )

    if "group" not in session_id:
        await addtag.finish()

    group_id = session_id.split("_")[1]
    raw_message = str(event)

    errMsg = "请回复需要指定语录"
    imgs = await reply_handle(bot, errMsg, raw_message, group_id, user_id, addtag)

    flag, _, _ = addTag(tags, imgs, group_id)

    if flag is None:
        msg = "该语录不存在"
    else:
        msg = "已为该语录添加上{}标签".format(tags)

    await addtag.finish(
        group_id=int(group_id), message=MessageSegment.at(user_id) + msg
    )


deltag = on_regex(pattern=f"^{plugin_config.quote_startcmd}deltag\\ ", **need_at)


@deltag.handle()
async def deltag_handle(bot: Bot, event: Event):
    if not plugin_config.quote_modify_tags:
        await alltag.finish("管理员已关闭修改标签功能TUT")
    session_id = event.get_session_id()
    user_id = str(event.get_user_id())
    tags = (
        str(event.get_message())
        .replace(f"{plugin_config.quote_startcmd}deltag", "")
        .strip()
        .split(" ")
    )

    if "group" not in session_id:
        await deltag.finish()

    group_id = session_id.split("_")[1]
    raw_message = str(event)

    errMsg = "请回复需要指定语录"
    imgs = await reply_handle(bot, errMsg, raw_message, group_id, user_id, deltag)

    flag, _, _ = delTag(tags, imgs, group_id)

    if flag is None:
        msg = "该语录不存在"
    else:
        msg = f"已移除该语录的{tags}标签"
    await deltag.finish(
        group_id=int(group_id), message=MessageSegment.at(user_id) + msg
    )


make_record = on_regex(
    pattern=f"^{re.escape(plugin_config.quote_startcmd)}记录$", **need_at
)


@make_record.handle()
async def make_record_handle(event: MessageEvent):
    """
    处理“记录”指令。
    """
    if not check_font(font_path, author_font_path):
        # 字体没配置就返回
        logger.warning("未配置字体路径，部分功能无法使用")
        await make_record.finish()
    if not event.reply:
        await make_record.finish("请回复所需的消息")
    size = 640
    user_id = event.reply.sender.user_id
    raw_message = event.reply.message.extract_plain_text().strip()
    card = (
        event.reply.sender.card
        if event.reply.sender.card not in (None, "")
        else event.reply.sender.nickname
    )
    if card is None:
        await make_record.finish("无法获取用户昵称，请设置群名片或昵称后重试")
    session_id = event.get_session_id()

    if str(user_id) == str(event.get_user_id()):
        await make_record.finish("不能记录自己的消息")

    if not raw_message:
        await make_record.finish("空内容")

    url = f"http://q1.qlogo.cn/g?b=qq&nk={user_id}&s={size}"

    data = await download_url(url)
    if hashlib.md5(data).hexdigest() == "acef72340ac0e914090bd35799f5594e":
        url = f"http://q1.qlogo.cn/g?b=qq&nk={user_id}&s=100"
        data = await download_url(url)

    image_file = io.BytesIO(data)
    img_data = generate_quote_image(
        image_file, raw_message, card, font_path, author_font_path
    )

    image_name = hashlib.md5(img_data).hexdigest() + ".png"

    image_path = pathlib.Path(QUOTE_PATH).joinpath(image_name)

    image_path.write_bytes(img_data)

    if "group" in session_id:
        group_id = session_id.split("_")[1]

        offer(
            group_id,
            image_path,
            card + " " + raw_message,
        )

    await make_record.finish(Message(MessageSegment.image(image_path)))


render_quote = on_regex(pattern=f"^{re.escape(plugin_config.quote_startcmd)}生成$")


@render_quote.handle()
async def render_quote_handle(event: MessageEvent):
    """
    处理“生成”指令。
    """
    if not check_font(font_path, author_font_path):
        # 字体没配置就返回
        logger.warning("未配置字体路径，部分功能无法使用")
        await make_record.finish()
    if not event.reply:
        await make_record.finish("请回复所需的消息")

    size = 640

    user_id = event.reply.sender.user_id
    raw_message = event.reply.message.extract_plain_text().strip()
    card = (
        event.reply.sender.card
        if event.reply.sender.card not in (None, "")
        else event.reply.sender.nickname
    )
    session_id = event.get_session_id()

    if not raw_message:
        await render_quote.finish("空内容")

    url = f"http://q1.qlogo.cn/g?b=qq&nk={user_id}&s={size}"

    data = await download_url(url)
    if hashlib.md5(data).hexdigest() == "acef72340ac0e914090bd35799f5594e":
        url = f"http://q1.qlogo.cn/g?b=qq&nk={user_id}&s=100"
        data = await download_url(url)

    image_file = io.BytesIO(data)
    img_data = generate_quote_image(
        image_file, raw_message, card, font_path, author_font_path
    )

    await render_quote.finish(MessageSegment.image(img_data))


script_batch = on_regex(
    pattern=f"^{plugin_config.quote_startcmd}batch_upload", **need_at
)


@script_batch.handle()
async def script_batch_handle(bot: Bot, event: Event):
    """
    处理批量上传
    """

    session_id = event.get_session_id()
    user_id = str(event.get_user_id())

    # 必须是超级管理员群聊
    if user_id not in plugin_config.global_superuser:
        await script_batch.finish()
    if "group" not in session_id:
        await script_batch.finish("该功能暂不支持私聊")

    group_id = session_id.split("_")[1]

    rqqid = r"qqgroup=(.*)\s"
    ryour_path = r"your_path=(.*)\s"
    rtags = r"tags=(.*)"

    raw_msg = str(event.get_message())
    raw_msg = raw_msg.replace("\r", "")
    dest_group_list = re.findall(rqqid, raw_msg)
    your_path = re.findall(ryour_path, raw_msg)
    tags = re.findall(rtags, raw_msg)

    instruction = """指令如下:
batch_upload
qqgroup=123456
your_path=/home/xxx/images
tags=aaa bbb ccc"""
    if len(group_id) == 0 or len(your_path) == 0:
        await script_batch.finish(instruction)
    # 获取图片
    image_files = copy_images_files(your_path[0], QUOTE_PATH)

    total_len = len(image_files)
    idx = 0

    for imgid, img in image_files:
        save_file = pathlib.Path(QUOTE_PATH).joinpath(img).absolute()
        idx += 1
        await bot.send_msg(
            group_id=int(group_id),
            message=Message(MessageSegment.image(f"{save_file.as_uri()}")),
        )
        time.sleep(2)

        rest_group = []

        for dest_group in dest_group_list:
            if image_exists(dest_group, str(save_file)):
                await bot.send_msg(
                    group_id=int(group_id),
                    message=f"图片已存在于 {dest_group} 群的语录库中",
                )
            # FIXME: 应当当图片已存在于目标群时，检查标签是否一致，若不一致则进行标签更新，而非简单地跳过不处理
            else:
                rest_group.append(dest_group)

        if not rest_group:
            continue

        ocr_content = get_ocr_content(save_file)

        for dest_group_id in rest_group:
            offer(dest_group_id, save_file, ocr_content)

        if len(tags) != 0:
            tags = tags[0].strip().split(" ")
            for dest_group_id in rest_group:
                addTag(tags, imgid, dest_group_id)

        # 每5张语录持久化一次
        if idx % 5 == 0:
            await bot.send_msg(
                group_id=int(group_id), message=f"当前进度{idx}/{total_len}"
            )

    await bot.send_msg(group_id=int(group_id), message="批量导入完成")
    await script_batch.finish()


copy_batch = on_regex(pattern=f"^{plugin_config.quote_startcmd}batch_copy", **need_at)


@copy_batch.handle()
async def copy_batch_handle(event: Event):
    await copy_batch.finish("该功能已废弃，请直接备份 data 文件夹")

    # TODO: 实现批量复制语录到指定路径的功能，方便用户备份和迁移语录库

    user_id = str(event.get_user_id())

    # 必须是超级管理员群聊
    if user_id not in plugin_config.global_superuser:
        await copy_batch.finish()

    ryour_path = r"your_path=(.*)\s"
    rgocq_path = r"gocq_path=(.*)\s"

    raw_msg = str(event.get_message())
    raw_msg = raw_msg.replace("\r", "")
    your_path = re.findall(ryour_path, raw_msg)
    gocq_path = re.findall(rgocq_path, raw_msg)
    # print(your_path, gocq_path)
    instruction = """指令如下:
batch_copy
your_path=/home/xxx/images
gocq_path=/home/xxx/gocq/data/cache"""
    if len(your_path) == 0 or len(gocq_path) == 0:
        await copy_batch.finish(instruction)

    try:
        for value in record_dict.values():
            for img in value:
                num = len(img) - 8
                name = img[-num:]
                shutil.copyfile(gocq_path[0] + name, your_path[0] + name)
    except FileNotFoundError:
        await copy_batch.finish("路径不正确")
    await copy_batch.finish("备份完成")


if not plugin_config.quote_needprefix:
    message_handler = on_message(block=False, **need_at)

    @message_handler.handle()
    async def handle_all_messages(event: GroupMessageEvent):
        message_text = event.get_plaintext().strip()
        group_id = str(event.group_id)

        if not quote_exists(group_id):
            await message_handler.finish()

        image = random_quote(message_text, group_id)

        if image != "":
            await message_handler.finish(Message(MessageSegment.image(file=image)))
        await message_handler.finish()


@scheduler.scheduled_job("interval", minutes=5, id="dump_quote_data")
async def dump_quote_data():
    """
    定时将内存中的语录数据持久化到磁盘，防止数据丢失。
    """
    logger.info("正在持久化语录数据...")
    dump_data()
    logger.info("语录数据持久化完成")


@driver.on_shutdown
async def shutdown_event():
    """
    在插件关闭时执行的函数，用于持久化数据。
    """
    logger.info("插件正在关闭，正在持久化语录数据...")
    dump_data()
    logger.info("语录数据持久化完成")

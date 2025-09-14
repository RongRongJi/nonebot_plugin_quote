from jinja2 import Environment, FileSystemLoader
from playwright.async_api import async_playwright
import os,requests
from nonebot.adapters.onebot.v11 import Bot

env = Environment(loader=FileSystemLoader(os.path.dirname(os.path.abspath(__file__))))
template = env.get_template('template.html')

async def generate_emulating_native_qq_style_image(userid: int, groupid: int, fontpath: str,  raw_message: str, bot: Bot, max_width=600, scale=3) -> bytes:
    response = await bot.call_api('get_group_member_info', **{
                'group_id': groupid,
                'user_id': userid
            })
    data = {
        "messages": [
            {
                "username": response['card_or_nickname'],
                "level": int(response['level']),
                "user_type": response['role'],
                "avatar": f"https://q.qlogo.cn/g?b=qq&nk={userid}&s=640",
                "message": raw_message
            }
        ],
        "font_path": fontpath
    }

    print (data)

    html_content = template.render(**data)

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={'width': max_width, 'height': 100}, device_scale_factor=scale)

        await page.set_content(html_content, wait_until='networkidle')

        dimensions = await page.evaluate('''() => {
            const wrapper = document.querySelector(".chat-wrapper");
            return {
                width: wrapper.scrollWidth,
                height: wrapper.scrollHeight
            };
        }''')

        actual_width = min(max(dimensions['width'], 300), max_width)
        await page.set_viewport_size({'width': int(actual_width), 'height': int(dimensions['height'])})

        img = await page.screenshot()
        await browser.close()
        return img

from PIL import Image, ImageDraw, ImageFont, ImageEnhance
import textwrap
from .pilmoji import Pilmoji
from .pilmoji.source import *
import httpx
import io

# 裁剪图片为正方形并调整大小
def make_square(image, size):
    width, height = image.size
    new_size = min(width, height)
    left = (width - new_size) // 2
    top = (height - new_size) // 2
    right = (width + new_size) // 2
    bottom = (height + new_size) // 2
    cropped_image = image.crop((left, top, right, bottom))
    return cropped_image.resize((size, size), Image.LANCZOS)

# 创建渐变图像
def create_gradient(size):
    gradient = Image.new("RGBA", size)
    draw = ImageDraw.Draw(gradient)
    for x in range(size[0]):
        # 使用非线性透明度变化公式
        alpha = int(255 * (1 - (1 - x / size[0]))**2)  # 更快的渐变
        draw.line((x, 0, x, size[1]), fill=(0, 0, 0, alpha))
    return gradient

def generate_quote_image(avatar_bytes, text, author,  font_path, author_font_path):

    def transbox(bbox):
        return bbox[2] - bbox[0], bbox[3] - bbox[1]

    text = "　　「" + text + "」"
    # 固定高度为400像素，长宽比3:1
    fixed_height = 400
    canvas_width = fixed_height * 3

    # 裁剪头像为正方形并调整大小
    avatar_size = fixed_height
    avatar = Image.open(avatar_bytes)
    avatar = make_square(avatar, avatar_size)

    # 创建画布
    canvas = Image.new("RGBA", (canvas_width, fixed_height), (0, 0, 0, 0))
    canvas.paste(avatar, (0, 0))

    # 创建渐变
    gradient = create_gradient((avatar_size, fixed_height))
    canvas.paste(gradient, (0, 0), gradient)

    # 设置文字区域
    text_area_width = canvas_width - avatar_size
    text_area_height = fixed_height
    text_area = Image.new("RGBA", (text_area_width, text_area_height), (0, 0, 0, 255))

    # 设置字体
    font_size = 80
    font = ImageFont.truetype(font_path, font_size)

    # 动态调整字体大小和自动换行
    max_text_width = text_area_width - 40  # 留出边距
    max_text_height = text_area_height  # 留出边距
    line_spacing = 10  # 添加额外的行间距

    wrapped_text = []

    if text:
        # 使用 textwrap 自动换行
        wrapped_lines = textwrap.wrap(text, width=25, drop_whitespace=False)  # 调整宽度以适应
        lines = []
        current_line = []
        for word in wrapped_lines:
            current_line.append(word)
            if transbox(font.getbbox(''.join(current_line)))[0] >= max_text_width:
                lines.append(''.join(current_line[:-1]))
                current_line = [current_line[-1]]
        if current_line:
            lines.append(''.join(current_line))
        wrapped_text = lines

        # 调整字体大小直到文字宽度合适
        while True:
            current_width = max(transbox(font.getbbox(line))[0] for line in wrapped_text)
            line_height = transbox(font.getbbox("A"))[1]
            current_height = len(wrapped_text) * line_height + ((len(lines) - 1) * line_spacing)

            if current_width <= max_text_width * 0.9 and current_height <= max_text_height:
                break

            font_size -= 1
            font = ImageFont.truetype(font_path, font_size)
            wrapped_text = textwrap.wrap(text, width=25, drop_whitespace=False)
            # 重新分词
            lines = []
            current_line = []
            for word in wrapped_text:
                current_line.append(word)
                if transbox(font.getbbox(''.join(current_line)))[0] >= max_text_width:
                    lines.append(''.join(current_line[:-1]))
                    current_line = [current_line[-1]]
            if current_line:
                lines.append(''.join(current_line))
            wrapped_text = lines

            if font_size <= 1:
                break

    quote_content = "\n".join(wrapped_text) 

    y = 0
    lines = quote_content.split("\n")
    line_height = transbox(font.getbbox("A"))[1]

    if len(lines) == 1:
        lines[0] = lines[0][2:]

    # 计算文字总高度
    total_content_height = len(lines) * line_height + ((len(lines) - 1) * line_spacing)

    # 计算居中垂直偏移量
    vertical_offset = (text_area_height - total_content_height) // 2 - 30

    # 计算文字左侧居中偏移量
    total_text_width = max(transbox(font.getbbox(line))[0] for line in lines)
    left_offset = (text_area_width - total_text_width) // 2 - 20

    # 绘制文本
    for line in lines:
        text_width = transbox(font.getbbox(line))[0]
        x = left_offset + 20  # 保留20像素左内边距
        with Pilmoji(text_area, source=GoogleEmojiSource) as pilmoji:
            pilmoji.text((x, vertical_offset + y), line, font=font, fill=(255, 255, 255, 255))
        y += line_height + line_spacing

    # 绘制作者名字
    author_font = ImageFont.truetype(author_font_path, 40)
    author_text = "— " + author
    author_width = transbox(author_font.getbbox(author_text))[0]
    author_x = text_area_width - author_width - 40
    author_y = text_area_height - transbox(author_font.getbbox("A"))[1] - 40
    with Pilmoji(text_area, source=GoogleEmojiSource) as pilmoji:
        pilmoji.text((author_x, author_y), author_text, font=author_font, fill=(255, 255, 255, 255))

    # 将文字区域粘贴到画布
    canvas.paste(text_area, (avatar_size, 0))

    # 将画布保存为字节流
    img_byte_arr = io.BytesIO()
    canvas.save(img_byte_arr, format='PNG')
    img_byte_arr = img_byte_arr.getvalue()

    return img_byte_arr 

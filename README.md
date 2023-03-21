<div align="center">
  <img src="https://s2.loli.net/2022/06/16/opBDE8Swad5rU3n.png" width="180" height="180" alt="NoneBotPluginLogo">
  <br>
  <p><img src="https://s2.loli.net/2022/06/16/xsVUGRrkbn1ljTD.png" width="240" alt="NoneBotPluginText"></p>
</div>

<div align="center">

# nonebot-plugin-quote

_✨ QQ群聊 语录库 ✨_

🧬 支持OCR识别，关键词搜索 | 一起记录群友的逆天言论吧！🎉 

<p align="center">
  <img src="https://img.shields.io/github/license/EtherLeaF/nonebot-plugin-colab-novelai" alt="license">
  <img src="https://img.shields.io/badge/python-3.8+-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/nonebot-2.0.0r4+-red.svg" alt="NoneBot">
  <a href="https://pypi.org/project/nonebot-plugin-quote/">
      <img src="https://img.shields.io/pypi/v/nonebot-plugin-quote.svg" alt="pypi">
  </a>
</p>
</div>


## 📖 介绍

一款适用于QQ群聊天的语录库插件。

- [x] 上传聊天截图
- [x] 随机投放聊天语录
- [x] 根据关键词投放聊天语录 
- [x] 支持白名单内用户删除语录


## 🎉 使用

### 上传

@机器人，发送**上传**指令，开启上传通道。

以图片的形式发送聊天语录，即可将语录上传至语录库中。

<img src="https://github.com/RongRongJi/nonebot_plugin_quote/raw/main/screenshot/upload.jpg" width="40%" />

### 随机发送语录

@机器人，发送**语录**指令，机器人将从语录库中随机挑选一条语录发送。

<img src="https://github.com/RongRongJi/nonebot_plugin_quote/raw/main/screenshot/random.jpg" width="40%" />

### 关键词检索语录

@机器人，发送**语录**+关键词指令，机器人将从语录库中进行查找。若有匹配项，将从匹配项中随机一条发送；若无匹配项，将从整个语录库中随机挑选一条发送。

<img src="https://github.com/RongRongJi/nonebot_plugin_quote/raw/main/screenshot/select.jpg" width="40%" />
<img src="https://github.com/RongRongJi/nonebot_plugin_quote/raw/main/screenshot/non.jpg" width="40%" />

### 删除语录

回复机器人发出的语录，发送**删除**指令，机器人将执行删除操作。（该操作只允许设置的白名单用户进行，如何设置白名单请看下方配置）

<img src="https://github.com/RongRongJi/nonebot_plugin_quote/raw/main/screenshot/delete.jpg" width="40%" />


### 详细命令

默认配置下，@机器人加指令即可。


| 指令 | 需要@ | 范围 | 说明 |
|:-----:|:----:|:------:|:-----------:|
| 上传/开始上传/上传开始 | 是 | 群聊 | 开启语录上传通道 |
| 语录上传通道开启后直接发送图片 | 否 | 群聊 | 上传图片至语录库 |
| 语录 + 关键词(可选) | 是 | 群聊 | 根据关键词返回一个符合要求的图片, 没有关键词时随机返回 |
| 回复机器人 + 删除 | 是 | 群聊 | 删除该条语录 |
| 语句中包含语录 | 是 | 群聊 | 对如何使用语录进行说明 |


## 💿 安装

### 下载

1. 通过包管理器安装，可以通过nb，pip，或者poetry等方式安装，以pip为例

```
pip install nonebot-plugin-quote -U
```

2. 手动安装

```
git clone https://github.com/RongRongJi/nonebot_plugin_quote.git
```

3. 使用nb-cli安装

```
nb plugin install nonebot-plugin-quote
```

## ⚙️ 配置

在 nonebot2 项目的 `.env` 文件中添加下表中的必填配置


| 配置项 | 必填 | 默认值 | 说明 |
|:-----:|:----:|:----:|:----:|
| RECORD_PATH | 是 | 空字符串 | 必要的json文件路径, 示例"/data/record.json" |
| INVERTED_INDEX_PATH | 是 | 空字符串 | 必要的json文件路径, 示例"/data/inverted_index.json" |
| QUOTE_SUPERUSER | 否 | 空字典 | 白名单字典(分群) |
| GLOBAL_SUPERUSER | 否 | 空数组 | 全局管理员(可以删除每个群的语录) |


其中，需要在`RECORD_PATH`和`INVERTED_INDEX_PATH`中手动创建两个json文件，并在其中填入`{}`以确保其能够正确运行，如下图所示：

<img src="https://github.com/RongRongJi/nonebot_plugin_quote/raw/main/screenshot/data.jpg" width="40%" />

`QUOTE_SUPERUSER`的示例如下:

```json
{"群号1":["语录管理员qq号","语录管理员qq号"],"群号2":["语录管理员qq号"]}
```

`GLOBAL_SUPERUSER`的示例如下:

```json
["全局管理员qq号"]
```

**完整的`.env`配置可以参考以下内容**

```
 # linux环境下路径
RECORD_PATH=/home/your_name/your_path/record.json      
INVERTED_INDEX_PATH=/home/your_name/your_path/inverted_index.json   

# Windows环境下路径
RECORD_PATH=D:\your_path\record.json       
INVERTED_INDEX_PATH=D:\your_path\inverted_index.json  

QUOTE_SUPERUSER={"12345":["123456"],"54321":["123456","654321]}
GLOBAL_SUPERUSER=["6666666"]
```


随后，在项目的`pyproject.toml`或`bot.py`中加上如下代码，加载插件（根据版本而定）

`pyproject.toml`中添加

```
# pip install的填这个
plugins = ["nonebot_plugin_quote"]

# 手动安装的填这个
plugin_dirs = ["nonebot_plugin_quote"]
```

或

`bot.py`中添加

```
# pip install的填这个
nonebot.load_plugin("nonebot_plugin_quote")

# 手动安装的填这个
nonebot.load_plugins("src/plugins", "nonebot_plugin_quote")
```

## Change Log

### v0.2.0 (2023/3/20)

- 删除了对Docker OCR的依赖，现在无需使用Docker，直接安装插件运行即可
- 增加了删除语录功能，只有在白名单中的用户拥有删除权限
- 增加了部分gif的OCR能力，但目前并不准确

### v0.2.2 (2023/3/21)

- 增加了全局管理员的设置，全局管理员拥有删除每个群语录库的权限
- 修复了一个关于上传后缀名不匹配的bug

### v0.2.3 (2023/3/22)

- 在OCR识别文字后增加了换行长文字与不同文字段的识别，使分词更加准确


## 🎉 鸣谢

- [NoneBot2](https://github.com/nonebot/nonebot2)：本插件使用的开发框架。
- [go-cqhttp](https://github.com/Mrs4s/go-cqhttp)：稳定完善的 CQHTTP 实现。
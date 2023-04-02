## 🎉 如何使用批量导入功能

### 适配版本

v0.3.3+

### 功能简介

如果您的个人电脑上保存有许多群聊天记录截图，想要直接接入本机器人插件，成为群语录库，**批量导入**可以帮助你实现这一功能。

### 使用方法

1. 批量导入功能只有超级管理员用户才能使用

超级管理员用户需要在 nonebot2 项目的 `.env` 文件中添加配置

```
GLOBAL_SUPERUSER=["6666666"]
```

2. 受私聊和群聊API方法不同的限制，该功能只能走**群聊**。建议超级管理员创建一个新的群聊，只拉入机器人，再进行以下操作。


3. 在群聊窗口中直接一次性输入下面内容，即可进行开启批量通道。

```
batch_upload
qqgroup=123456
your_path=/home/name/project/data
gocq_path=/home/name/gocq/data/cache
tags=aaa bbb ccc
```

上述内容解释如下:

向群号为123456的qq群批量上传语录。将保存在/home/name/project/data/目录下的所有聊天截图上传，你所使用的go-cqhttp下的data/cache目录为/home/name/gocq/data/cache/。这一批截图除了进行OCR自动识别标签外，还将全部额外附上aaa、bbb、ccc三个标签（每个标签用空格分开）。

### 注意

*该功能目前处于测试阶段，欢迎反馈
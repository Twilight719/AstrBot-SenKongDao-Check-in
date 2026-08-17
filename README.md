# AstrBot Plugin - 森空岛签到

[![Build and Release](https://github.com/Azincc/astrbot_plugin_skland/actions/workflows/release.yml/badge.svg)](https://github.com/Azincc/astrbot_plugin_skland/actions/workflows/release.yml)

森空岛自动签到插件，支持明日方舟和终末地签到。

## 功能

- **skd** (群聊):        查看群内所有绑定用户的签到状态
- **skd** (私聊):        查看自己的签到状态
- **skdlogin** (私聊):   使用 token 登录并立即签到
- **skdlogout** (私聊):  登出并移除 token
- **skdusers** (全部):   查询用户统计，普通用户仅显示签到人数和名额

## 使用

### 获取 Token

1. 登录 [森空岛](https://www.skland.com/)
2. 访问 [森空岛/account/info/hg](https://web-api.skland.com/account/info/hg)
3. 找到返回的 JSON 中的 `{"content":"XXX"}`
4. 复制 `XXX` 部分

### 登录与签到

1. 私聊发送 `/skdlogin XXX` 进行登录
2. 登录成功后会自动执行一次签到
3. 之后可以发送 `/skd` 查看签到状态

## 安装

### 方式一：从 Release 下载

1. 前往 [Releases](https://github.com/Azincc/astrbot_plugin_skland/releases) 页面
2. 下载最新的 `astrbot_plugin_skland-vX.X.X.zip`
3. 解压到 AstrBot 的 `plugins` 目录

### 方式二：使用 Git

```bash
cd /path/to/astrbot/plugins
git clone https://github.com/Azincc/astrbot_plugin_skland.git
```

## 依赖

插件依赖已在 `requirements.txt` 中列出，AstrBot 会自动安装。

## 本地改进（v1.4.0）

在原作者 Azincc v1.3.0 基础上的本地增强：

- **AI 自然语言触发**：新增 LLM 函数工具 `skland_sign_in`（为当前会话用户签到）与 `skland_sign_status`（查询绑定游戏与最近签到日期），可直接对机器人说"帮我签到森空岛"等。token 不经过 AI，绑定仍走 `/skdlogin` 或 WebUI。
- **WebUI 管理页**：新增 `pages/manage/` 插件页（dashboard 插件页中打开），支持账号列表查看、绑定新账号（验证 token 并立即签到）、解绑、单个/全部手动签到、自动签到设置修改。接口不回传 token。
- **Bug 修复**：移除 `/skd` 群聊模式中恒为 False 的昵称滚动更新死代码（`users_data.get("umo")` 判断）。

## 许可

MIT License

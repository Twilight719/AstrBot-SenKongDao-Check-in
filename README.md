# AstrBot Plugin - 森空岛签到

[![Build and Release](https://github.com/Azincc/astrbot_plugin_skland/actions/workflows/release.yml/badge.svg)](https://github.com/Azincc/astrbot_plugin_skland/actions/workflows/release.yml)

AstrBot 森空岛自动签到插件，支持**明日方舟**和**明日方舟：终末地**的每日签到。

> 本仓库是在原作者 [Azincc/astrbot_plugin_skland](https://github.com/Azincc/astrbot_plugin_skland) v1.3.0 基础上的改进版（v1.4.0），新增了 WebUI 管理页和 AI 对话签到能力，详见[本地改进](#本地改进v140)。

## 功能一览

| 指令 / 入口 | 适用场景 | 说明 |
|---|---|---|
| `/skdlogin <token>` | 私聊 | 绑定森空岛账号并立即签到一次 |
| `/skdlogout` | 私聊 | 解绑并移除 token |
| `/skd` | 私聊 | 查看自己的签到状态并手动签到 |
| `/skd` | 群聊 | 查看群内所有绑定用户的签到状态 |
| `/skdusers` | 全部 | 查询用户统计（普通用户仅显示签到人数和名额） |
| `/skdhelp` | 全部 | 查看帮助 |
| WebUI 管理页 | 浏览器 | 网页绑定/解绑账号、手动签到、查看状态 |
| AI 对话 | 全部 | 直接对机器人说"帮我签到森空岛"即可 |

## 安装

### 方式一：从 Release 下载

1. 前往本仓库的 Releases 页面
2. 下载最新的 `astrbot_plugin_skland-vX.X.X.zip`
3. 解压到 AstrBot 的 `data/plugins` 目录
4. 在 AstrBot WebUI 的插件页确认插件已启用

### 方式二：使用 Git

```bash
cd /path/to/AstrBot/data/plugins
git clone https://github.com/Twilight719/AstrBot-SenKongDao-Check-in.git astrbot_plugin_skland
```

插件依赖已在 `requirements.txt` 中列出，AstrBot 加载时会自动安装。

## 第一步：获取森空岛 Token

绑定账号前需要先拿到森空岛的 token（约 24 位字符串）：

1. 用浏览器登录 [森空岛官网](https://www.skland.com/)
2. **保持登录状态**，在同一个浏览器里新开一个标签页，访问：
   [https://web-api.skland.com/account/info/hg](https://web-api.skland.com/account/info/hg)
3. 页面会显示一段 JSON，找到其中的 `{"content":"XXX"}` 字段
4. 复制 `XXX` 部分（不含引号）——这就是你的 token

> 注意：token 等同于你的森空岛登录凭证，**不要发到群聊或泄露给他人**。如果怀疑泄露，在森空岛退出登录即可使其失效。

## 第二步：绑定账号（三种方式任选）

### 方式 A：私聊指令绑定

1. **私聊**机器人发送：`/skdlogin XXX`（把 XXX 换成你的 token）
2. 绑定成功后会**自动执行一次签到**，并返回签到结果
3. 之后随时可以发 `/skd` 查看状态或再次手动签到

> 请务必在私聊中使用，避免 token 泄露。

### 方式 B：WebUI 网页绑定（本改进版新增）

1. 打开 AstrBot 的 WebUI 管理面板
2. 在插件页面列表中找到本插件的管理页（森空岛签到管理）
3. 在"绑定新账号"区域粘贴 token，可选填 QQ 号作为标识（留空会自动生成 `webui_` 前缀标识）
4. 点击**绑定并签到**——插件会先验证 token，验证通过即完成绑定并立即签到一次

管理页还支持：查看所有已绑定账号及其游戏/最近签到日期、单个或全部手动签到、解绑账号、修改自动签到设置。接口不会回传 token，网页上也看不到已保存的 token。

### 方式 C：AI 对话签到（本改进版新增）

绑定完成后，可以直接用自然语言让机器人操作，例如：

- "帮我签到森空岛"
- "帮我看看森空岛签了没"
- "给我明日方舟签个到"

机器人会调用 `skland_sign_in`（签到）和 `skland_sign_status`（查询状态）两个函数工具完成操作。token 不经过 AI 模型，绑定仍需要通过方式 A 或 B 完成。

## 自动签到

插件支持每天定时为所有已绑定账号自动签到，在 AstrBot WebUI 的插件配置中修改：

| 配置项 | 默认值 | 说明 |
|---|---|---|
| `auto_sign_enabled` | 关 | 自动签到总开关 |
| `auto_sign_hour` | 9 | 每天执行自动签到的小时（0-23） |
| `auto_sign_delay` | 10 | 签到时随机向后延迟的秒数，防止风控（0 为不延迟） |
| `show_player_name` | 开 | 签到结果中显示森空岛昵称（关闭则显示 QQ 昵称） |
| `max_users` | 10 | 最大绑定账号数量，防止风控（0 为不限制） |

开启后，到点会自动签到并把结果**私发**给对应用户。

## 常见问题

**绑定失败 / 签到失败？**

- 确认 token 复制完整，没有多余的引号、空格或换行
- token 会过期：重新登录森空岛官网后再按上面步骤取一次新 token
- 运行 AstrBot 的服务器/电脑需要能访问 `web-api.skland.com`，如果 AstrBot 日志里报网络错误，检查本机网络或代理
- WebUI 页面提示 "Failed to fetch" 通常是浏览器到 AstrBot 面板的连接问题，刷新页面或确认 AstrBot 正在运行

**群聊里能看到别人的 token 吗？**

不能。绑定只能在私聊或 WebUI 进行，签到结果中也不会包含 token。

## 本地改进（v1.4.0）

在原作者 Azincc v1.3.0 基础上的增强：

- **AI 自然语言触发**：新增 LLM 函数工具 `skland_sign_in`（为当前会话用户签到）与 `skland_sign_status`（查询绑定游戏与最近签到日期），可直接对机器人说"帮我签到森空岛"等。token 不经过 AI，绑定仍走 `/skdlogin` 或 WebUI。
- **WebUI 管理页**：新增 `pages/manage/` 插件页（dashboard 插件页中打开），支持账号列表查看、绑定新账号（验证 token 并立即签到）、解绑、单个/全部手动签到、自动签到设置修改。接口不回传 token。
- **Bug 修复**：移除 `/skd` 群聊模式中恒为 False 的昵称滚动更新死代码（`users_data.get("umo")` 判断）。

## 致谢

- 原作者：[Azincc](https://github.com/Azincc) — [astrbot_plugin_skland](https://github.com/Azincc/astrbot_plugin_skland)

## 许可

MIT License（与上游保持一致）

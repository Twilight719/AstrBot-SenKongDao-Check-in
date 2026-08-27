# AstrBot Plugin - 森空岛签到

[![Build and Release](https://github.com/Twilight719/AstrBot-SenKongDao-Check-in/actions/workflows/release.yml/badge.svg)](https://github.com/Twilight719/AstrBot-SenKongDao-Check-in/actions/workflows/release.yml)

AstrBot 森空岛自动签到插件，支持**明日方舟**和**明日方舟：终末地**的每日签到。

> 本仓库是在原作者 [Azincc/astrbot_plugin_skland](https://github.com/Azincc/astrbot_plugin_skland) v1.3.0 基础上的改进版，新增了 WebUI 管理页、AI 对话签到和明日方舟理智提醒，详见[本地改进](#本地改进)。各版本变更记录见 [CHANGELOG.md](CHANGELOG.md)。

## 功能一览

| 指令 / 入口 | 适用场景 | 说明 |
|---|---|---|
| `/skdlogin <token>` | 私聊 | 绑定森空岛账号并立即签到一次 |
| `/skdlogout` | 私聊 | 解绑并移除 token |
| `/skd` | 私聊 | 查看自己的签到状态并手动签到 |
| `/skd` | 群聊 | 查看群内所有绑定用户的签到状态 |
| `/skdusers` | 全部 | 查询用户统计（普通用户仅显示签到人数和名额） |
| `/skdhelp` | 全部 | 查看帮助 |
| WebUI 管理页 | 浏览器 | 网页绑定/解绑账号、手动签到、查看状态、理智提醒设置 |
| AI 对话 | 全部 | 直接对机器人说"帮我签到森空岛"即可 |
| AI 对话 | 全部 | 说"我现在多少理智"查询理智，说"理智满了叫我"开启回满提醒 |

## 安装

### 方式一：从 Release 下载

1. 前往本仓库的 Releases 页面
2. 下载最新的 `astrbot_plugin_skland_remind-vX.X.X.zip`
3. 解压到 AstrBot 的 `data/plugins` 目录
4. 在 AstrBot WebUI 的插件页确认插件已启用

### 方式二：使用 Git

```bash
cd /path/to/AstrBot/data/plugins
git clone https://github.com/Twilight719/AstrBot-SenKongDao-Check-in.git astrbot_plugin_skland_remind
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
3. 在"绑定新账号"区域粘贴 token，可选填 QQ 号作为标识（留空会自动生成 `webui_` 前缀标识）；忘记怎么获取 token 可点旁边的「绑定教程」按钮查看图文步骤
4. 点击**绑定并签到**——插件会先验证 token，验证通过即完成绑定并立即签到一次

> 注意：通过 WebUI 绑定的账号**没有 QQ 私聊通道**，自动签到结果和理智回满提醒无法私聊推送。绑定后请在 QQ 里私聊机器人发送任意一条消息（比如 `/skd`），插件会自动补全私聊通道，之后提醒即可正常送达。

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
| `ap_remind_enabled` | 开 | 理智回满私聊提醒总开关（仅明日方舟） |
| `ap_check_interval` | 15 | 理智检查间隔（分钟，5-120，建议 10-30，过短可能触发风控） |

开启后，到点会自动签到并把结果**私发**给对应用户。

## 理智回满提醒（明日方舟 + 终末地）

插件会按设定间隔（默认 15 分钟）检查所有已绑定账号的理智，**任一游戏理智回满时私聊提醒**。

- 明日方舟理智按 6 分钟/点、终末地按 7.2 分钟/点从回满时刻实时推算（接口返回的 current 是上次同步的旧值，不能直接用）
- 防重复：每个游戏单独标记，提醒过一次后等你把理智用掉才会在下次回满时再提醒
- 个人开关：对机器人说"关闭理智提醒"可以只关掉你自己的提醒，不影响别人；也可以在 WebUI 管理页账号列表里点"关提醒/开提醒"单独控制每个账号
- AI 查询：直接问"我现在多少理智""终末地体力什么时候满"，机器人会实时查询两个游戏并告诉你预计回满时间
- WebUI 管理页的账号列表会显示最近一次检查到的各游戏理智缓存和提醒状态
- 通过 WebUI 网页绑定的账号没有会话记录，无法接收私聊提醒，但理智缓存仍会显示在管理页

## 常见问题

**绑定失败 / 签到失败？**

- 确认 token 复制完整，没有多余的引号、空格或换行
- token 会过期：重新登录森空岛官网后再按上面步骤取一次新 token
- 运行 AstrBot 的服务器/电脑需要能访问 `web-api.skland.com`，如果 AstrBot 日志里报网络错误，检查本机网络或代理
- WebUI 页面提示 "Failed to fetch" 通常是浏览器到 AstrBot 面板的连接问题，刷新页面或确认 AstrBot 正在运行

**群聊里能看到别人的 token 吗？**

不能。绑定只能在私聊或 WebUI 进行，签到结果中也不会包含 token。

## 本地改进

在原作者 Azincc v1.3.0 基础上的增强：

**v1.6.0**

- **终末地理智支持**：新增 `get_endfield_card_detail`（`/api/v1/game/endfield/card/detail`，数据含 `dungeon.curStamina/maxStamina/maxTs`），理智提醒和 AI 查询同时覆盖明日方舟与终末地；按游戏独立防重复标记。
- 理智计算重构为 `_derive_stamina`：方舟 360 秒/点、终末地 432 秒/点，从回满时刻实时推算。

**v1.5.2**

- **修复理智数值不准**：接口返回的 `ap.current` 是上次同步时的旧值，现改为按 `completeRecoveryTime` 回满时刻以 6 分钟/点实时推算当前理智。

**v1.5.1**

- **按账号开关理智提醒**：WebUI 管理页账号列表新增"关提醒/开提醒"按钮，可单独控制每个账号的理智回满提醒（配合已有的 AI 对话开关）。

**v1.5.0**

- **理智回满提醒（明日方舟）**：新增 `get_player_info` / `get_arknights_ap` 接口封装；后台定时任务按间隔（默认 15 分钟）检查所有绑定账号的理智，回满时私聊提醒（防重复标记，消耗后重置）。
- **新增 LLM 工具**：`skland_ap_query`（实时查询当前理智与预计回满时间）、`skland_ap_remind`（对话中开关自己的提醒）。
- **WebUI 管理页增强**：账号列表显示理智缓存与提醒状态，设置区新增理智提醒总开关与检查间隔。
- **终末地说明**：实测森空岛官方接口不返回终末地体力数据，本期仅支持明日方舟。

**v1.4.0**

- **AI 自然语言触发**：新增 LLM 函数工具 `skland_sign_in`（为当前会话用户签到）与 `skland_sign_status`（查询绑定游戏与最近签到日期），可直接对机器人说"帮我签到森空岛"等。token 不经过 AI，绑定仍走 `/skdlogin` 或 WebUI。
- **WebUI 管理页**：新增 `pages/manage/` 插件页（dashboard 插件页中打开），支持账号列表查看、绑定新账号（验证 token 并立即签到）、解绑、单个/全部手动签到、自动签到设置修改。接口不回传 token。
- **Bug 修复**：移除 `/skd` 群聊模式中恒为 False 的昵称滚动更新死代码（`users_data.get("umo")` 判断）。

## 致谢

- 原作者：[Azincc](https://github.com/Azincc) — [astrbot_plugin_skland](https://github.com/Azincc/astrbot_plugin_skland)

## 许可

MIT License（与上游保持一致）

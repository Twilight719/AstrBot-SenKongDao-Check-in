# AGENTS.md - astrbot_plugin_skland_remind

> AstrBot 插件（Python）：森空岛自动签到 + 明日方舟理智提醒。
> 本目录是 AstrBot 插件，从 Rust 项目 Skland-Auto-Sign-In 移植签名与登录逻辑而来；
> 本文件只描述当前 Python 插件，不再涉及 Rust 构建。

## 项目结构

```
astrbot_plugin_skland_remind/
├── main.py            # 插件入口：指令、LLM 工具、定时任务（自动签到/理智检查）
├── skland_api.py      # 森空岛 API 客户端：设备指纹、签名、登录、签到、玩家数据
├── web_api.py         # WebUI 后端接口（register_web_api 注册到 dashboard）
├── pages/manage/      # WebUI 管理页前端（经 dashboard 桥接发请求）
├── metadata.yaml      # 插件元数据（版本号在这里和 main.py 的 @register 里都要改）
├── _conf_schema.json  # AstrBot 插件配置 schema
└── requirements.txt   # 依赖（httpx、pycryptodome 等）
```

## 关键机制

- **凭证流程**：user token → `get_authorization()` → `get_credential()` → Credential(token, cred)；
  签名请求用 `_get_signed_headers(url, method, body, cred, did)`。
- **用户数据**：存 AstrBot KV（`get_kv_data("users", {})`），user_data 含
  `token`、`nickname`、`last_sign`、`umo`（私聊推送用）、`ap_cache`（理智缓存）、
  `ap_state.notified_full`（防重复提醒）、`ap_remind`（个人提醒开关）。
- **私聊通道**：`umo` 为空时私聊推送会被跳过；WebUI 绑定的账号没有 umo，
  靠 `refresh_umo_on_private_message`（私聊被动监听）在用户私聊机器人时自动补全。
- **定时任务**：apscheduler AsyncIOScheduler，job id：`skland_auto_sign`（cron）、
  `skland_ap_check`（interval）。改配置后需在 `web_api.py` 的 api_settings 里重排。
- **理智数据**：明日方舟用 `GET /api/v1/game/player/info?uid=` → `data.status.ap`；
  终末地用 `GET /api/v1/game/endfield/card/detail?roleId=&serverId=`（带 `sk-game-role` 头）
  → `detail.dungeon`（curStamina/maxStamina/maxTs）。
  两个接口的 current 都是旧快照，用 `_derive_stamina` 从回满时刻反推（方舟 360s/点，终末地 432s/点）。

## 约定

- Python 异步（httpx.AsyncClient），不要引入阻塞请求。
- WebUI 接口约定：成功 `{"code": 0, "data": ...}`，任何接口不得回传用户 token。
- 绑定/登录只允许私聊或 WebUI，群聊中提示用户撤回。
- 新增加密/签名逻辑前先理解现有实现，不要改动 DES/AES/RSA 相关代码。
- 发版：更新 `metadata.yaml` 与 `main.py` 的版本号，推 tag 触发 GitHub Actions 自动打 Release zip。

"""
森空岛签到插件 WebUI 后端接口

通过 context.register_web_api 注册到 AstrBot dashboard（与 dashboard 同源、同鉴权）。
返回约定：成功 {"code": 0, "data": ...}，失败 {"code": !=0, "message": ...}。
任何接口都不会回传用户 token。
"""

import re
import uuid
from datetime import datetime

from quart import request, jsonify

from astrbot.api import logger

PLUGIN_NAME = "astrbot_plugin_skland_remind"
API_PREFIX = f"/{PLUGIN_NAME}"
LOG_PREFIX = f"[{PLUGIN_NAME}][WebUI]"

_GAME_KEY_TO_NAME = {"arknights": "明日方舟", "endfield": "终末地"}


def register_web_apis(plugin):
    """在插件 initialize 时调用，注册全部 WebUI 路由。"""

    def ok(data=None):
        return jsonify({"code": 0, "data": data if data is not None else {}})

    def err(message, code=1):
        return jsonify({"code": code, "message": str(message)})

    def wrap(handler):
        async def wrapper(*args, **kwargs):
            try:
                return await handler(*args, **kwargs)
            except Exception as e:
                logger.error(f"{LOG_PREFIX} {handler.__name__} 失败: {e}", exc_info=True)
                # 始终返回 HTTP 200 + 业务错误码，让 dashboard 桥能把错误信息透传到页面
                return jsonify({"code": 500, "message": f"服务器内部错误: {e}"})

        wrapper.__name__ = f"skland_web_{handler.__name__}"
        return wrapper

    async def read_json() -> dict:
        data = await request.get_json()
        return data if isinstance(data, dict) else {}

    def serialize_results(results) -> list:
        return [
            {
                "game": r.game,
                "nickname": r.nickname,
                "success": bool(r.success or plugin._is_signed_today(r)),
                "awards": list(getattr(r, "awards", None) or []),
                "error": r.error or "",
            }
            for r in results
        ]

    # ==================== Handlers ====================

    async def api_accounts():
        users = await plugin.get_kv_data("users", {})
        accounts = []
        for user_id, user_data in users.items():
            last_sign = user_data.get("last_sign") or {}
            games = user_data.get("games")
            if not games:
                # 老数据没有 games 字段时，按 last_sign 推断
                games = [_GAME_KEY_TO_NAME.get(k, k) for k in last_sign.keys()]
            accounts.append(
                {
                    "user_id": user_id,
                    "nickname": user_data.get("nickname") or "",
                    "last_username": user_data.get("last_username") or "",
                    "games": games,
                    "last_sign": last_sign,
                    "bound_at": user_data.get("bound_at") or "",
                    "ap_cache": user_data.get("ap_cache") or None,
                    "ap_remind": user_data.get("ap_remind", True),
                }
            )
        return ok(
            {
                "accounts": accounts,
                "max_users": plugin._get_config().get("max_users", 10),
            }
        )

    async def api_bind():
        data = await read_json()
        token = str(data.get("token") or "").strip()
        user_id = str(data.get("user_id") or "").strip()

        if not token:
            return err("token 不能为空")
        if user_id and not re.fullmatch(r"[A-Za-z0-9_]{1,32}", user_id):
            return err("QQ号/标识只能包含字母、数字、下划线，最长 32 位")

        users = await plugin.get_kv_data("users", {})
        if not user_id:
            while True:
                user_id = "webui_" + uuid.uuid4().hex[:8]
                if user_id not in users:
                    break
        if user_id not in users:
            max_users = plugin._get_config().get("max_users", 10)
            if max_users > 0 and len(users) >= max_users:
                return err(f"绑定失败：已达到最大用户数限制（{max_users} 个）")

        # 验证 token 并立即签到一次
        results, nickname = await plugin.api.do_full_sign_in(token)
        if not results:
            return err("token 验证失败：未找到绑定的游戏角色，请检查 token 是否正确")

        user_data = users.get(user_id, {})
        user_data.update(
            {
                "token": token,
                "nickname": nickname,
                "last_username": user_data.get("last_username") or "",
                "bound_at": datetime.now().isoformat(),
                "platform_name": "webui",
                # WebUI 绑定的账号没有统一会话 ID，自动签到私发消息时会跳过
                "umo": user_data.get("umo", ""),
                "games": sorted({r.game for r in results}),
            }
        )
        plugin._update_last_sign(user_data, results)
        users[user_id] = user_data
        await plugin.put_kv_data("users", users)

        logger.info(f"{LOG_PREFIX} WebUI 绑定账号成功: {user_id} ({nickname})")
        message_text = plugin._format_sign_status(results, nickname)
        if not user_data.get("umo"):
            message_text += (
                "\n\n提示：WebUI 绑定的账号暂无 QQ 私聊通道，"
                "自动签到结果和理智回满提醒无法私聊推送。"
                "请在 QQ 里私聊机器人发送任意消息（如 /skd）即可自动开通。"
            )
        return ok(
            {
                "user_id": user_id,
                "nickname": nickname,
                "results": serialize_results(results),
                "message_text": message_text,
            }
        )

    async def api_unbind():
        data = await read_json()
        user_id = str(data.get("user_id") or "").strip()
        if not user_id:
            return err("user_id 不能为空")

        users = await plugin.get_kv_data("users", {})
        if user_id not in users:
            return err(f"用户 {user_id} 未绑定")
        del users[user_id]
        await plugin.put_kv_data("users", users)
        logger.info(f"{LOG_PREFIX} WebUI 解绑账号: {user_id}")
        return ok({"user_id": user_id})

    async def api_sign():
        data = await read_json()
        user_id = str(data.get("user_id") or "").strip()
        if not user_id:
            return err("user_id 不能为空")

        users = await plugin.get_kv_data("users", {})
        if user_id == "all":
            targets = list(users.keys())
        else:
            if user_id not in users:
                return err(f"用户 {user_id} 未绑定")
            targets = [user_id]

        results_out = []
        for uid in targets:
            user_data = users.get(uid)
            if not user_data or "token" not in user_data:
                continue
            try:
                results, nickname = await plugin._sign_user(user_data)
                users[uid] = user_data
                results_out.append(
                    {
                        "user_id": uid,
                        "nickname": nickname,
                        "ok": True,
                        "results": serialize_results(results),
                        "message_text": plugin._format_sign_status(results, nickname),
                    }
                )
            except Exception as e:
                logger.error(f"{LOG_PREFIX} 用户 {uid} 手动签到失败: {e}")
                results_out.append({"user_id": uid, "ok": False, "error": str(e)})

        await plugin.put_kv_data("users", users)
        return ok({"results": results_out})

    async def api_settings():
        if request.method == "GET":
            return ok(plugin._get_config())

        data = await read_json()
        updated = {}
        for key in (
            "auto_sign_enabled",
            "show_player_name",
            "auto_sign_hour",
            "auto_sign_delay",
            "max_users",
            "ap_remind_enabled",
            "ap_check_interval",
        ):
            if key not in data:
                continue
            value = data[key]
            try:
                if key in ("auto_sign_enabled", "show_player_name", "ap_remind_enabled"):
                    value = bool(value)
                else:
                    value = int(value)
            except (TypeError, ValueError):
                return err(f"配置项 {key} 的值无效")
            updated[key] = value

        if not updated:
            return err("没有可更新的配置项")
        if "auto_sign_hour" in updated and not 0 <= updated["auto_sign_hour"] <= 23:
            return err("auto_sign_hour 必须在 0-23 之间")
        if "auto_sign_delay" in updated and updated["auto_sign_delay"] < 0:
            return err("auto_sign_delay 不能为负数")
        if "max_users" in updated and updated["max_users"] < 0:
            return err("max_users 不能为负数")
        if "ap_check_interval" in updated and not 5 <= updated["ap_check_interval"] <= 120:
            return err("ap_check_interval 必须在 5-120 分钟之间")

        for key, value in updated.items():
            plugin.config[key] = value
        plugin.config.save_config()

        # 重排自动签到定时任务
        config = plugin._get_config()
        if config.get("auto_sign_enabled"):
            plugin._start_auto_sign_job(config.get("auto_sign_hour", 1))
            if not plugin.scheduler.running:
                plugin.scheduler.start()
        else:
            try:
                plugin.scheduler.remove_job("skland_auto_sign")
            except Exception:
                pass

        # 重排理智检查定时任务
        if config.get("ap_remind_enabled"):
            plugin._start_ap_check_job(config.get("ap_check_interval", 15))
            if not plugin.scheduler.running:
                plugin.scheduler.start()
        else:
            try:
                plugin.scheduler.remove_job("skland_ap_check")
            except Exception:
                pass

        logger.info(f"{LOG_PREFIX} WebUI 更新设置: {updated}")
        return ok(plugin._get_config())

    async def api_bridge_auth_token():
        auth_header = request.headers.get("Authorization", "").strip()
        if auth_header.startswith("Bearer "):
            token = auth_header.removeprefix("Bearer ").strip()
            if token:
                return jsonify({"token": token}), 200
        return jsonify({"message": "当前请求缺少 Bearer Token"}), 401

    async def api_ap_remind():
        data = await read_json()
        user_id = str(data.get("user_id") or "").strip()
        if not user_id:
            return err("user_id 不能为空")
        if "enable" not in data:
            return err("enable 不能为空")

        users = await plugin.get_kv_data("users", {})
        if user_id not in users:
            return err(f"用户 {user_id} 未绑定")
        users[user_id]["ap_remind"] = bool(data["enable"])
        await plugin.put_kv_data("users", users)
        logger.info(f"{LOG_PREFIX} 用户 {user_id} 理智提醒设置为 {bool(data['enable'])}")
        return ok({"user_id": user_id, "ap_remind": bool(data["enable"])})

    # ==================== 路由注册 ====================

    routes = [
        ("accounts", api_accounts, ["GET"], "获取已绑定账号列表（不含 token）"),
        ("bind", api_bind, ["POST"], "绑定新账号（验证 token 并立即签到一次）"),
        ("unbind", api_unbind, ["POST"], "解绑账号"),
        ("sign", api_sign, ["POST"], "手动触发签到（单个 user_id 或 all）"),
        ("settings", api_settings, ["GET", "POST"], "读取或保存自动签到设置"),
        ("ap_remind", api_ap_remind, ["POST"], "设置单个账号的理智回满提醒开关"),
        (
            "bridge/auth_token",
            api_bridge_auth_token,
            ["GET"],
            "获取当前会话 Bearer Token（用于插件页安全请求）",
        ),
    ]
    for route, handler, methods, desc in routes:
        plugin.context.register_web_api(
            f"{API_PREFIX}/{route}", wrap(handler), methods, desc
        )
    logger.info(f"{LOG_PREFIX} 已注册 {len(routes)} 个 WebUI 接口")

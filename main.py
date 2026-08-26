"""
AstrBot Plugin - 森空岛签到 (Skland Sign-In)

Commands:
- skd (group): Show sign-in status for all bound users in the group
- skd (private): Show user's own sign-in status
- skdlogin (private): Login with token and immediately sign in
- skdlogout (private): Logout and remove token
- skdusers (all): Show users and stats 

Config (AstrBot plugin config):
- auto_sign_enabled: 自动签到开关
- auto_sign_hour: 自动签到时间（小时，0-23）
- show_player_name: 显示玩家昵称（否则显示QQ昵称）
- auto_sign_delay: 签到延时
- max_users: 最大用户数量
"""

from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from astrbot.core.star.filter.permission import PermissionType
import astrbot.api.message_components as Comp
from astrbot.api import logger, AstrBotConfig
from astrbot.api.event import AstrMessageEvent, filter, MessageChain
from astrbot.api.star import Context, Star, register
from astrbot.core.star.config import put_config
import asyncio, random

from .skland_api import SklandAPI
from .web_api import register_web_apis

PLUGIN_NAME = "astrbot_plugin_skland"


@register(PLUGIN_NAME, "AstrBot", "森空岛自动签到插件", "1.5.3")
class SklandPlugin(Star):
    """森空岛签到插件"""

    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self.api = SklandAPI(max_retries=3)
        self.scheduler = AsyncIOScheduler()
        self._init_config()

    def _init_config(self):
        """注册后台配置项"""
        put_config(
            namespace=PLUGIN_NAME,
            name="自动签到开关",
            key="auto_sign_enabled",
            value=True,
            description="开启后，将在指定时间自动为所有已注册用户签到，并私发结果"
        )
        put_config(
            namespace=PLUGIN_NAME,
            name="自动签到时间（小时）",
            key="auto_sign_hour",
            value=1,
            description="自动签到执行的小时（0-23），默认凌晨1点"
        )
        put_config(
            namespace=PLUGIN_NAME,
            name="显示玩家名称",
            key="show_player_name",
            value=True,
            description="开启后，将在签到结果中显示森空岛昵称，否则显示QQ昵称"
        )
        put_config(
            namespace=PLUGIN_NAME,
            name="自动签到的延迟",
            key="auto_sign_delay",
            value=10,
            description="开启后，将在签到时进行向后随机延迟（随机范围 0 至 设定的秒数）"
        )
        put_config(
            namespace=PLUGIN_NAME,
            name="最大用户数",
            key="max_users",
            value=10,
            description="允许绑定的最大用户数量，0表示无限制"
        )
        put_config(
            namespace=PLUGIN_NAME,
            name="理智满提醒开关",
            key="ap_remind_enabled",
            value=True,
            description="开启后，将定期检查已绑定用户的明日方舟理智，回满时私聊提醒"
        )
        put_config(
            namespace=PLUGIN_NAME,
            name="理智检查间隔（分钟）",
            key="ap_check_interval",
            value=15,
            description="理智检查的时间间隔（分钟），建议 10-30，过短可能触发风控"
        )

    def _get_config(self) -> dict:
        """获取当前配置"""
        return {
            "auto_sign_enabled": self.config.get("auto_sign_enabled", True),
            "auto_sign_hour": self.config.get("auto_sign_hour", 1),
            "show_player_name": self.config.get("show_player_name", True),
            "auto_sign_delay": self.config.get("auto_sign_delay", 10),
            "max_users": self.config.get("max_users", 10),
            "ap_remind_enabled": self.config.get("ap_remind_enabled", True),
            "ap_check_interval": self.config.get("ap_check_interval", 15),
        }

    async def initialize(self):
        """插件初始化"""
        logger.info("森空岛签到插件已加载")
        register_web_apis(self)
        config = self._get_config()
        if config.get("auto_sign_enabled", False):
            hour = config.get("auto_sign_hour", 1)
            self._start_auto_sign_job(hour)
        if config.get("ap_remind_enabled", False):
            self._start_ap_check_job(config.get("ap_check_interval", 15))
        if not self.scheduler.running:
            self.scheduler.start()

    async def terminate(self):
        """插件卸载"""
        if self.scheduler.running:
            self.scheduler.shutdown()
        await self.api.close()
        logger.info("森空岛签到插件已卸载")

    # ==================== Auto Sign-In ====================

    def _start_auto_sign_job(self, hour: int = 1):
        """启动自动签到定时任务"""
        hour = max(0, min(23, hour))
        trigger = CronTrigger(hour=hour, minute=0)
        try:
            self.scheduler.remove_job("skland_auto_sign")
        except Exception:
            pass

        self.scheduler.add_job(
            self._auto_sign_all_users,
            trigger=trigger,
            id="skland_auto_sign",
            misfire_grace_time=3600,
        )
        logger.info(f"森空岛自动签到任务已启动，每天 {hour:02d}:00 执行")

    async def _auto_sign_all_users(self):
        """为所有已注册用户执行自动签到"""
        config = self._get_config()
        if not config.get("auto_sign_enabled", False):
            logger.info("自动签到已关闭，跳过执行")
            return

        logger.info("开始执行自动签到...")
        users = await self.get_kv_data("users", {})
        if not users:
            logger.info("没有已注册的用户，跳过自动签到")
            return
        
        # 自动签到的最大随机延时时间
        max_delay = config.get("auto_sign_delay", 10)

        for user_id, user_data in users.items():
            # 随机延时的核心代码
            if max_delay > 0:
                delay = random.uniform(0, max_delay)
                logger.info(f"处理下一个用户前等待 {delay:.2f} 秒")
                await asyncio.sleep(delay)
            
            if "token" not in user_data:
                continue

            try:
                results, nickname = await self._sign_user(user_data)

                # 构建消息
                message = f"🎮 森空岛自动签到结果\n\n{self._format_sign_status(results, nickname)}"
                await self._send_private_message(user_id, user_data, message)
                users[user_id] = user_data
                logger.info(f"用户 {user_id} ({nickname}) 自动签到完成")
            except Exception as e:
                logger.error(f"用户 {user_id} 自动签到失败: {e}")
                message = f"⚠️ 自动签到失败\n错误: {str(e)}\n请使用 /skdlogin 重新登录"
                await self._send_private_message(user_id, user_data, message)

        await self.put_kv_data("users", users)
        logger.info("自动签到执行完毕")

    # ==================== AP (理智) Reminder ====================

    def _start_ap_check_job(self, interval_minutes: int = 15):
        """启动理智检查定时任务"""
        interval_minutes = max(5, min(120, interval_minutes))
        try:
            self.scheduler.remove_job("skland_ap_check")
        except Exception:
            pass

        self.scheduler.add_job(
            self._check_ap_all_users,
            trigger=IntervalTrigger(minutes=interval_minutes),
            id="skland_ap_check",
            misfire_grace_time=300,
        )
        logger.info(f"森空岛理智检查任务已启动，每 {interval_minutes} 分钟执行")

    def _fmt_seconds(self, seconds: float) -> str:
        """把秒数格式化为 'X小时Y分钟'"""
        seconds = max(0, int(seconds))
        hours, rem = divmod(seconds, 3600)
        minutes = rem // 60
        if hours:
            return f"{hours}小时{minutes}分钟"
        return f"{minutes}分钟"

    def _format_ap_status(self, ap_info: dict) -> str:
        """格式化理智状态文本"""
        current = ap_info["current"]
        max_ap = ap_info["max"]
        lines = [f"理智：{current}/{max_ap}"]
        if current >= max_ap:
            lines.append("已回满！")
        else:
            recovery_ts = ap_info.get("complete_recovery_time") or 0
            remain = recovery_ts - datetime.now().timestamp()
            if remain > 0:
                full_at = datetime.fromtimestamp(recovery_ts).strftime("%H:%M")
                lines.append(f"约 {self._fmt_seconds(remain)} 后回满（{full_at}）")
        return "\n".join(lines)

    async def _check_ap_all_users(self):
        """检查所有已注册用户的理智，回满时私聊提醒"""
        config = self._get_config()
        if not config.get("ap_remind_enabled", False):
            return

        users = await self.get_kv_data("users", {})
        if not users:
            return

        changed = False
        for user_id, user_data in users.items():
            if "token" not in user_data:
                continue
            # 用户可在 AI 对话中单独关闭自己的提醒
            if user_data.get("ap_remind") is False:
                continue
            try:
                ap_info = await self.api.get_arknights_ap(user_data["token"])
            except Exception as e:
                logger.warning(f"用户 {user_id} 理智查询失败: {e}")
                continue

            user_data["ap_cache"] = {
                "current": ap_info["current"],
                "max": ap_info["max"],
                "complete_recovery_time": ap_info["complete_recovery_time"],
                "ts": int(datetime.now().timestamp()),
            }
            ap_state = user_data.setdefault("ap_state", {})
            changed = True

            if ap_info["max"] > 0 and ap_info["current"] >= ap_info["max"]:
                if not ap_state.get("notified_full"):
                    message = (
                        f"🎮 理智提醒\n\n【{ap_info['nickname']}】\n"
                        f"理智已回满 {ap_info['current']}/{ap_info['max']}，快去清理智吧~"
                    )
                    await self._send_private_message(user_id, user_data, message)
                    ap_state["notified_full"] = True
                    logger.info(f"用户 {user_id} 理智已满，已发送提醒")
            else:
                # 理智被消耗后重置，下次回满再提醒
                ap_state["notified_full"] = False

        if changed:
            await self.put_kv_data("users", users)

    async def _send_private_message(self, user_id: str, user_data: dict, message: str):
        """使用统一会话ID发送私聊消息"""
        try:
            umo = user_data.get("umo")
            if not umo:
                logger.warning(f"用户 {user_id} 没有统一会话ID，无法发送私聊消息")
                return

            message_chain = MessageChain().message(message)
            await self.context.send_message(umo, message_chain)
            logger.info(f"已发送私聊消息给用户 {user_id}")
        except Exception as e:
            logger.error(f"发送私聊消息失败: {e}")

    # ==================== Helpers ====================

    def _update_last_sign(self, user_data: dict, results):
        """根据签到结果就地更新用户的 last_sign 记录"""
        for r in results:
            if r.game == "明日方舟" and self._is_signed_today(r):
                user_data.setdefault("last_sign", {})["arknights"] = datetime.now().strftime("%Y-%m-%d")
            elif r.game == "终末地" and self._is_signed_today(r):
                user_data.setdefault("last_sign", {})["endfield"] = datetime.now().strftime("%Y-%m-%d")

    async def _sign_user(self, user_data: dict):
        """为单个用户执行签到并就地更新其 last_sign，返回 (results, nickname)"""
        results, nickname = await self.api.do_full_sign_in(user_data["token"])
        self._update_last_sign(user_data, results)
        return results, nickname

    def _is_signed_today(self, result) -> bool:
        if result.success:
            return True
        error = result.error.lower() if result.error else ""
        return any(k in error for k in ["已签到", "请勿重复", "重复签到", "already", "签到过", "今日已"])

    def _format_sign_status(self, results: list, nickname: str = "") -> str:
        if not results:
            return "没有绑定游戏"
        lines = []
        if nickname:
            lines.append(f"【{nickname}】")
        for r in results:
            if r.success or self._is_signed_today(r):
                award = ", ".join(r.awards) if getattr(r, "awards", None) else "无奖励"
                lines.append(f"{r.game} 已签到 ({award})")
            else:
                lines.append(f"{r.game} 签到失败: {r.error}")
        return "\n".join(lines)

    # ==================== Commands ====================

    @filter.command("skdhelp")
    async def skdhelp(self, event: AstrMessageEvent):
        """森空岛签到插件帮助"""
        yield event.plain_result(
            "森空岛签到插件帮助\n"
            "1. 私聊机器人发送/skdlogin <token> 登录并签到\n"
            "2. 私聊机器人发送/skdlogout 登出\n"
            "3. /skd 查看签到状态\n"
            "4. 直接对机器人说\"我现在多少理智\"查询理智，说\"理智满了叫我\"开启回满提醒"
        )
    
    # @filter.event_message_type(filter.EventMessageType.PRIVATE_MESSAGE)
    @filter.command("skdlogin")
    async def skdlogin(self, event: AstrMessageEvent, token: str = ""):
        # 验证是否在群内登录 如果是 则提示用户撤回消息且在私聊中使用
        group_id = getattr(event.message_obj, "group_id", None)
        user_name = event.get_sender_name()
        if group_id:
            yield event.plain_result(" 请在私聊中使用此命令登录\n为保护隐私，请将发送在群内的登录消息撤回")
            return
        
        config = self._get_config()
        
        user_id = event.get_sender_id()
        users = await self.get_kv_data("users", {})
        max_users = config.get("max_users", 10)
        
        if user_id not in users and max_users > 0 and len(users) >= max_users:
            yield event.plain_result(f"❌ 绑定失败：已达到最大用户数限制（{max_users}个）\n请联系管理员调整配置")
            return
        
        token = token.strip()
        if not token:
            yield event.plain_result(
                "请先获取token，方法如下:\n"
                "1. 登录 鹰角网络通行证 后，打开 (https://web-api.hypergryph.com/account/info/hg) 记下 content 字段的值（推荐）。\n"
                "   或者登录 森空岛网页版 (https://www.skland.com/) 后，\n"
                "   打开 (https://web-api.skland.com/account/info/hg) 记下 content 字段的值。\n"
                "   请复制类似这样的段落，content字段示例：N6QKb2C3d4A1b2C3d4，如果其中包含符号也一起复制\n"
                "2. 使用方法:\n"
                "   /skdlogin <content>")
            return
        yield event.plain_result("正在登录并签到，请稍候...")
        try:
            results, nickname = await self.api.do_full_sign_in(token)
            user_data = {
                "token": token,
                "nickname": nickname,
                "last_username": user_name,
                "last_sign": {},
                "bound_at": datetime.now().isoformat(),
                "platform_name": event.get_platform_name(),
                "umo": event.unified_msg_origin,  # 保存统一会话ID
            }
            for r in results:
                if r.game == "明日方舟" and self._is_signed_today(r):
                    user_data["last_sign"]["arknights"] = datetime.now().strftime("%Y-%m-%d")
                elif r.game == "终末地" and self._is_signed_today(r):
                    user_data["last_sign"]["endfield"] = datetime.now().strftime("%Y-%m-%d")
            await self.put_kv_data("users", {**(await self.get_kv_data("users", {})), user_id: user_data})
            yield event.plain_result(f"登录成功！\n{self._format_sign_status(results, nickname)}")
        except Exception as e:
            logger.error(f"skdlogin失败: {e}")
            yield event.plain_result(f"登录失败: {str(e)}")

    # @filter.event_message_type(filter.EventMessageType.PRIVATE_MESSAGE)
    @filter.command("skdlogout")
    async def skdlogout(self, event: AstrMessageEvent):
        # 验证是否在群内登出 如果是 则提示用户撤回消息且在私聊中使用
        group_id = getattr(event.message_obj, "group_id", None)
        if group_id:
            yield event.plain_result(" 请在私聊中使用此命令登出\n为保护隐私，请将发送在群内的登出消息撤回")
            return
        
        user_id = event.get_sender_id()
        users = await self.get_kv_data("users", {})
        if user_id in users:
            del users[user_id]
            await self.put_kv_data("users", users)
            yield event.plain_result("已退出登录并清除绑定信息")
        else:
            yield event.plain_result("您尚未绑定森空岛账号")

    @filter.command("skdusers")
    async def skdusers(self, event: AstrMessageEvent):
        """查询当前注册用户数量"""
        
        users = await self.get_kv_data("users", {})
        groups = await self.get_kv_data("groups", {})
        config = self._get_config()
        max_users = config.get("max_users", 10)
        
        # 计算群聊分布
        group_stats = []
        for group_id, user_ids in groups.items():
            if user_ids:
                group_name = group_id  # 这里可以尝试获取群名称，如果可能的话
                group_stats.append(f"  • 群 {group_name}: {len(user_ids)} 人")
        
        # 计算在线用户（最近7天有登录的用户）
        online_users = 0
        for user_data in users.values():
            if user_data.get("last_sign"):
                online_users += 1
        
        # 构建统计信息
        lines = [
            "📊 森空岛签到用户统计",
            "═══════════════════",
            f"📝 总注册用户: {len(users)} 人",
            # f"📈 今日活跃: {online_users} 人",
            f"📉 未签到用户: {len(users) - online_users} 人",
        ]
        
        # 检查管理员
        if event.is_admin():
            if max_users > 0:
                remaining = max(0, max_users - len(users))
                lines.append(f"🎯 最大限制: {max_users} 人")
                lines.append(f"🆓 剩余名额: {remaining} 人")
            
            # 限定私信查看
            if not getattr(event.message_obj, "group_id", None):
                # 添加群聊分布
                if group_stats:
                    lines.append("\n📌 群聊分布（仅代表群内同玩的数量）:")
                    lines.extend(group_stats)
                # 添加用户列表（如果用户数不多）
                if len(users) <= 20:
                    lines.append("\n👤 用户列表:")
                    for user_id, user_data in users.items():
                        nickname = user_data.get("nickname") or user_data.get("last_username", "未知")
                        last_sign = list(user_data.get("last_sign", {}).values())[-1] if user_data.get("last_sign") else "未签到"
                        lines.append(f"  • {nickname} (最后签到: {last_sign})")
                else:
                    lines.append(f"\n💡 用户数过多，不显示详细列表")
            else:
                lines.append(f"\n💡 如需查看详细用户列表请私信")
        yield event.plain_result("\n".join(lines))

    @filter.command("skd")
    async def skd(self, event: AstrMessageEvent):
        """群聊显示群成员签到状态，私聊显示自己"""
        user_id = event.get_sender_id()
        user_name = event.get_sender_name()
        group_id = getattr(event.message_obj, "group_id", None)
        is_group = bool(group_id)
        users_data = await self.get_kv_data("users", {})

        if is_group: # 群聊模式
            # 如果发送者已绑定，自动添加到该群
            if user_id in users_data:
                groups = await self.get_kv_data("groups", {})
                if group_id not in groups:
                    groups[group_id] = []
                if user_id not in groups[group_id]:
                    groups[group_id].append(user_id)
                    await self.put_kv_data("groups", groups)
            
            message_lines = [" 森空岛签到统计", "═══════════════", "方舟 | 终末 | 昵称", "-----------------"]
            group_users = (await self.get_kv_data("groups", {})).get(group_id, [])
            for uid in group_users:
                user_data = users_data.get(uid)
                if not user_data:
                    continue
                try:
                    results, nickname = await self.api.do_full_sign_in(user_data["token"])

                    # 如果配置不显示玩家名称，或者昵称获取为空，则使用QQ昵称显示
                    if nickname == None or nickname.strip() == "" or not self.config.get("show_player_name", True):
                        nickname = user_data.get("last_username").strip() or "(未知)"
                    
                    user_data["nickname"] = nickname
                    for r in results:
                        if r.game == "明日方舟" and self._is_signed_today(r):
                            user_data.setdefault("last_sign", {})["arknights"] = datetime.now().strftime("%Y-%m-%d")
                        elif r.game == "终末地" and self._is_signed_today(r):
                            user_data.setdefault("last_sign", {})["endfield"] = datetime.now().strftime("%Y-%m-%d")
                    
                    users_data[uid] = user_data
                    
                    ak_icon = "✅" if user_data.get("last_sign", {}).get("arknights") else "❌"
                    ef_icon = "✅" if user_data.get("last_sign", {}).get("endfield") else "❌"
                    message_lines.append(f" {ak_icon} | {ef_icon} | {nickname}")
                except:
                    message_lines.append(" ⚠️ | ⚠️ | (Error)")
            await self.put_kv_data("users", users_data)
            yield event.plain_result("\n".join(message_lines))
        else: # 私聊模式
            user_data = users_data.get(user_id)
            if not user_data:
                yield event.plain_result("你还未绑定账号，请使用 /skdlogin <token>")
                return
            try:
                results, nickname = await self.api.do_full_sign_in(user_data["token"])
                response = self._format_sign_status(results, nickname)
                yield event.plain_result(response)
            except Exception as e:
                yield event.plain_result(f"查询失败: {str(e)}")

    # ==================== LLM Tools ====================

    @filter.llm_tool(name="skland_sign_in")
    async def llm_skland_sign_in(self, event: AstrMessageEvent):
        """为当前聊天的用户执行森空岛（Skland）每日签到，覆盖明日方舟和终末地。

        当用户说"签到""打卡""帮我签到森空岛""明日方舟签到""终末地签到"等涉及森空岛/鹰角游戏签到的请求时调用此工具。
        用户必须事先绑定账号（通过私聊机器人发送 /skdlogin <token> 或在 WebUI 管理页绑定）；不要向用户索要 token，绑定只能由用户自己完成。
        """
        user_id = event.get_sender_id()
        users = await self.get_kv_data("users", {})
        user_data = users.get(user_id)
        if not user_data or "token" not in user_data:
            yield event.plain_result(
                "你还没有绑定森空岛账号，暂时无法签到。\n"
                "请先私聊我发送 /skdlogin <token> 完成绑定（token 获取方式见 /skdhelp），绑定后即可签到。"
            )
            return
        try:
            results, nickname = await self._sign_user(user_data)
            users[user_id] = user_data
            await self.put_kv_data("users", users)
            yield event.plain_result(f"🎮 森空岛签到结果\n\n{self._format_sign_status(results, nickname)}")
        except Exception as e:
            logger.error(f"LLM 工具签到失败: {e}")
            yield event.plain_result(f"签到失败: {str(e)}\n可能需要重新使用 /skdlogin 登录")

    @filter.llm_tool(name="skland_sign_status")
    async def llm_skland_sign_status(self, event: AstrMessageEvent):
        """查询当前聊天的用户森空岛（Skland）账号绑定情况与各游戏（明日方舟/终末地）的最近签到日期。

        当用户问"我签到过吗""今天签到了吗""我的森空岛绑定状态"等查询类问题时调用此工具。
        此工具只查询本地记录，不会触发真实签到；如需签到请改用 skland_sign_in。
        """
        user_id = event.get_sender_id()
        users = await self.get_kv_data("users", {})
        user_data = users.get(user_id)
        if not user_data:
            yield event.plain_result(
                "你还没有绑定森空岛账号。\n"
                "请先私聊我发送 /skdlogin <token> 完成绑定（token 获取方式见 /skdhelp）。"
            )
            return
        nickname = user_data.get("nickname") or user_data.get("last_username") or "未知"
        last_sign = user_data.get("last_sign") or {}
        today = datetime.now().strftime("%Y-%m-%d")
        lines = [f"森空岛账号：{nickname}"]
        for game_key, game_name in (("arknights", "明日方舟"), ("endfield", "终末地")):
            sign_date = last_sign.get(game_key)
            if sign_date:
                suffix = "（今天已签到）" if sign_date == today else ""
                lines.append(f"{game_name} 最近签到：{sign_date}{suffix}")
            else:
                lines.append(f"{game_name} 暂无签到记录")
        yield event.plain_result("\n".join(lines))

    @filter.llm_tool(name="skland_ap_query")
    async def llm_skland_ap_query(self, event: AstrMessageEvent):
        """查询当前聊天的用户明日方舟的当前理智（AP）以及预计回满时间。

        当用户问"我现在多少理智""理智满了吗""理智什么时候回满"等涉及明日方舟理智/体力的问题时调用此工具。
        用户必须事先绑定账号；此工具只支持明日方舟，终末地暂无官方体力数据接口。
        """
        user_id = event.get_sender_id()
        users = await self.get_kv_data("users", {})
        user_data = users.get(user_id)
        if not user_data or "token" not in user_data:
            yield event.plain_result(
                "你还没有绑定森空岛账号，暂时无法查询理智。\n"
                "请先私聊我发送 /skdlogin <token> 完成绑定（token 获取方式见 /skdhelp）。"
            )
            return
        try:
            ap_info = await self.api.get_arknights_ap(user_data["token"])
            yield event.plain_result(
                f"【{ap_info['nickname']}】\n{self._format_ap_status(ap_info)}"
            )
        except Exception as e:
            logger.error(f"LLM 工具理智查询失败: {e}")
            yield event.plain_result(f"理智查询失败: {str(e)}\n可能需要重新使用 /skdlogin 登录")

    @filter.llm_tool(name="skland_ap_remind")
    async def llm_skland_ap_remind(self, event: AstrMessageEvent, enable: bool = True):
        """开启或关闭当前聊天的用户的明日方舟理智回满私聊提醒。

        当用户说"理智满了叫我""理智满了提醒我""开启理智提醒"时以 enable=true 调用；
        当用户说"不用提醒我了""关闭理智提醒"时以 enable=false 调用。
        提醒依托插件的后台定时检查，全局开关和检查间隔由管理员在插件配置中设置。

        Args:
            enable (boolean): true 为开启提醒，false 为关闭提醒
        """
        user_id = event.get_sender_id()
        users = await self.get_kv_data("users", {})
        user_data = users.get(user_id)
        if not user_data or "token" not in user_data:
            yield event.plain_result(
                "你还没有绑定森空岛账号，暂时无法设置理智提醒。\n"
                "请先私聊我发送 /skdlogin <token> 完成绑定（token 获取方式见 /skdhelp）。"
            )
            return
        user_data["ap_remind"] = bool(enable)
        users[user_id] = user_data
        await self.put_kv_data("users", users)
        if enable:
            config = self._get_config()
            interval = config.get("ap_check_interval", 15)
            yield event.plain_result(
                f"已开启理智提醒✅\n理智回满时我会私聊提醒你（约每 {interval} 分钟检查一次）。"
            )
        else:
            yield event.plain_result("已关闭理智提醒，理智回满时将不再提醒你。")

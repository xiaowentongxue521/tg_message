import re
import logging
from datetime import datetime

from telethon import events

from .notifier import send_feishu_notification

logger = logging.getLogger(__name__)


def build_keyword_matcher(keywords: list[str], regex_patterns: list[str]):
    """构建关键词匹配函数。"""
    compiled_patterns = []
    for pattern in regex_patterns:
        try:
            compiled_patterns.append(re.compile(pattern, re.IGNORECASE))
        except re.error as e:
            logger.warning(f"无效的正则表达式 '{pattern}': {e}")

    def match(text: str) -> list[str]:
        """返回所有匹配的关键词/模式列表。"""
        if not text:
            return []

        matched = []
        text_lower = text.lower()

        for kw in keywords:
            if kw.lower() in text_lower:
                matched.append(kw)

        for pattern in compiled_patterns:
            m = pattern.search(text)
            if m:
                matched.append(f"正则:{pattern.pattern} -> {m.group()}")

        return matched

    return match


async def resolve_forward_targets(client, forward_rules: dict) -> dict:
    """解析转发目标，返回 {source_channel_lower: [target_entity, ...]}"""
    resolved = {}
    for source_channel, targets in forward_rules.items():
        source_key = source_channel.lower()
        resolved[source_key] = []
        for target in targets:
            try:
                entity = await client.get_entity(target)
                logger.info(f"转发目标已解析: {target} -> {entity.id}")
                resolved[source_key].append(entity)
            except Exception as e:
                logger.warning(f"无法解析转发目标 '{target}': {e}")
    return resolved


def register_handler(client, config: dict, channel_ids: list[int] | None = None, forward_targets: dict | None = None):
    """注册消息事件处理器。channel_ids 为 None 时监控所有频道/群组。"""
    monitor_config = config["monitor"]
    feishu_webhook = config["feishu"]["webhook_url"]
    proxy_url = config["feishu"].get("proxy", "")

    default_keywords = monitor_config.get("keywords", [])
    channel_keywords_config = monitor_config.get("channel_keywords", {})
    regex_patterns = monitor_config.get("regex_patterns", [])

    # 转发配置
    forward_enabled = monitor_config.get("forward", {}).get("enabled", False)
    # forward_targets 通过参数传入（在 main.py 中异步解析）

    # 默认匹配器（用于非特定频道）
    default_matcher = build_keyword_matcher(default_keywords, regex_patterns)

    # 预编译特定频道的匹配器 {channel_username_lower: matcher_func}
    channel_matchers = {}
    for ch_name, ch_keywords in channel_keywords_config.items():
        channel_matchers[ch_name.lower()] = build_keyword_matcher(ch_keywords, [])

    event_filter = events.NewMessage(chats=channel_ids) if channel_ids else events.NewMessage()

    @client.on(event_filter)
    async def on_new_message(event):
        text = event.message.text or event.message.message or ""
        if not text.strip():
            return

        # 获取聊天信息，决定使用哪个匹配器
        chat = await event.get_chat()
        chat_username = getattr(chat, "username", None)

        # 根据频道选择匹配器
        if chat_username and chat_username.lower() in channel_matchers:
            # 使用该频道的专属关键词匹配器
            matcher = channel_matchers[chat_username.lower()]
        else:
            # 使用默认匹配器
            matcher = default_matcher

        matched_keywords = matcher(text)
        if not matched_keywords:
            return

        # chat 和 chat_username 已在匹配逻辑中获取

        # 区分频道/群组和私聊
        if hasattr(chat, "title"):
            # 频道或群组
            chat_title = chat.title
        else:
            # 个人私聊，拼接姓名
            first = getattr(chat, "first_name", "") or ""
            last = getattr(chat, "last_name", "") or ""
            chat_title = f"{first} {last}".strip() or chat_username or f"用户{chat.id}"

        # 获取发送者信息（群组中显示是谁发的）
        sender = await event.get_sender()
        if sender and sender.id != chat.id:
            first = getattr(sender, "first_name", "") or ""
            last = getattr(sender, "last_name", "") or ""
            sender_name = f"{first} {last}".strip() or getattr(sender, "username", "") or f"用户{sender.id}"
            chat_title = f"{chat_title} > {sender_name}"

        # 构建消息时间
        msg_time = event.message.date
        if msg_time:
            time_str = msg_time.strftime("%Y-%m-%d %H:%M:%S")
        else:
            time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 构建消息链接
        msg_id = event.message.id
        if chat_username:
            msg_link = f"https://t.me/{chat_username}/{msg_id}"
        else:
            msg_link = ""

        logger.info(
            f"[命中] 频道: {chat_title} | 关键词: {matched_keywords} | 消息: {text[:80]}..."
        )

        # 转发消息（如果配置了转发规则）
        if forward_enabled and forward_targets and chat_username:
            source_key = chat_username.lower()
            if source_key in forward_targets:
                for target_entity in forward_targets[source_key]:
                    try:
                        # 转发原始消息
                        await client.forward_messages(target_entity, event.message)
                        logger.info(f"消息已转发到: {getattr(target_entity, 'username', target_entity.id)}")
                    except Exception as e:
                        logger.error(f"转发消息失败: {e}")

        # 发送飞书通知
        await send_feishu_notification(
            webhook_url=feishu_webhook,
            channel_name=chat_title,
            keywords=matched_keywords,
            message_text=text,
            message_time=time_str,
            message_link=msg_link,
            proxy_url=proxy_url,
        )

    if channel_ids:
        logger.info(f"已注册消息处理器，监控 {len(channel_ids)} 个频道")
    else:
        logger.info("已注册消息处理器，监控所有频道/群组")

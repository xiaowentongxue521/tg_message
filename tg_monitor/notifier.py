import logging
import httpx

logger = logging.getLogger(__name__)


async def send_feishu_notification(
    webhook_url: str,
    channel_name: str,
    keywords: list[str],
    message_text: str,
    message_time: str,
    message_link: str,
    proxy_url: str = "",
):
    """通过飞书 Webhook 发送通知消息。"""
    # 截断过长的消息
    if len(message_text) > 500:
        message_text = message_text[:500] + "..."

    keywords_str = ", ".join(keywords)

    # 构建飞书卡片消息
    elements = [
        {
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"**频道**: {channel_name}\n"
                f"**命中关键词**: {keywords_str}\n"
                f"**时间**: {message_time}",
            },
        },
        {"tag": "hr"},
        {
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": message_text,
            },
        },
    ]

    if message_link:
        elements.append(
            {
                "tag": "action",
                "actions": [
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "查看原消息"},
                        "type": "primary",
                        "url": message_link,
                    }
                ],
            }
        )

    payload = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": f"TG 监控提醒 - {channel_name}",
                },
                "template": "red",
            },
            "elements": elements,
        },
    }

    try:
        async with httpx.AsyncClient(timeout=10, proxy=proxy_url or None) as http_client:
            resp = await http_client.post(webhook_url, json=payload)
            resp.raise_for_status()
            result = resp.json()
            if result.get("code") == 0:
                logger.info(f"飞书通知发送成功")
            else:
                logger.warning(f"飞书通知响应异常: {result}")
    except Exception as e:
        logger.error(f"飞书通知发送失败: {e}")

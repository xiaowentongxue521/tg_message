import logging
from urllib.parse import urlparse

from telethon import TelegramClient

logger = logging.getLogger(__name__)


def _parse_proxy(proxy_url: str) -> dict | None:
    """解析代理URL，返回 Telethon 格式的 proxy 参数。"""
    if not proxy_url:
        return None

    parsed = urlparse(proxy_url)
    scheme = parsed.scheme.lower()

    if scheme == "socks5":
        return {
            "proxy_type": "socks5",
            "addr": parsed.hostname,
            "port": parsed.port,
            "username": parsed.username,
            "password": parsed.password,
        }
    elif scheme == "socks4":
        return {
            "proxy_type": "socks4",
            "addr": parsed.hostname,
            "port": parsed.port,
        }
    elif scheme in ("http", "https"):
        return {
            "proxy_type": "http",
            "addr": parsed.hostname,
            "port": parsed.port,
            "username": parsed.username,
            "password": parsed.password,
        }
    else:
        logger.warning(f"不支持的代理类型: {scheme}")
        return None


def create_client(config: dict) -> TelegramClient:
    """根据配置创建 Telethon 客户端。"""
    tg_config = config["telegram"]
    proxy = _parse_proxy(tg_config.get("proxy", ""))

    if proxy:
        logger.info(f"使用代理: {proxy['proxy_type']}://{proxy['addr']}:{proxy['port']}")
        client = TelegramClient(
            tg_config["session_name"],
            tg_config["api_id"],
            tg_config["api_hash"],
            proxy=proxy,
        )
    else:
        client = TelegramClient(
            tg_config["session_name"],
            tg_config["api_id"],
            tg_config["api_hash"],
        )
    return client


async def start_client(client: TelegramClient, config: dict):
    """启动客户端并完成登录。"""
    phone = config["telegram"]["phone"]
    await client.start(phone=phone)
    me = await client.get_me()
    logger.info(f"已登录: {me.first_name} (ID: {me.id})")


async def resolve_channels(client: TelegramClient, channels: list) -> list:
    """将频道用户名/ID解析为实体对象，返回有效频道列表。"""
    entities = []
    for ch in channels:
        try:
            entity = await client.get_entity(ch)
            logger.info(f"已找到频道: {getattr(entity, 'title', ch)}")
            entities.append(entity)
        except Exception as e:
            logger.warning(f"无法解析频道 '{ch}': {e}")
    return entities

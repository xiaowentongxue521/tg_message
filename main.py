import sys
import logging
import asyncio

import yaml

from tg_monitor.client import create_client, start_client, resolve_channels
from tg_monitor.handler import register_handler, resolve_forward_targets

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("tg_monitor")


def load_config(path: str = "config.yaml") -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


async def main():
    # 加载配置
    try:
        config = load_config()
    except FileNotFoundError:
        logger.error("找不到 config.yaml，请复制 config.example.yaml 为 config.yaml 并填写配置")
        sys.exit(1)

    # 创建并启动客户端
    client = create_client(config)
    await start_client(client, config)

    # 解析频道
    channels = config["monitor"].get("channels", [])
    monitor_all = not channels or channels == ["all"]

    if monitor_all:
        channel_ids = None
        logger.info("将监控所有已加入的频道/群组")
    else:
        entities = await resolve_channels(client, channels)
        if not entities:
            logger.error("没有找到任何有效的监控频道，请检查配置")
            await client.disconnect()
            sys.exit(1)
        channel_ids = [e.id for e in entities]

    # 解析转发目标
    forward_config = config["monitor"].get("forward", {})
    forward_enabled = forward_config.get("enabled", False)
    forward_targets = None
    if forward_enabled:
        forward_rules = forward_config.get("rules", {})
        forward_targets = await resolve_forward_targets(client, forward_rules)

    # 注册消息处理器
    register_handler(client, config, channel_ids, forward_targets)

    # 打印监控信息
    keywords = config["monitor"].get("keywords", [])
    channel_keywords = config["monitor"].get("channel_keywords", {})
    regex_patterns = config["monitor"].get("regex_patterns", [])
    logger.info("=" * 50)
    logger.info("Telegram 频道监控已启动")
    if monitor_all:
        logger.info("监控范围: 所有已加入的频道/群组")
    else:
        logger.info(f"监控频道数: {len(channel_ids)}")
    logger.info(f"默认关键词: {keywords}")
    if channel_keywords:
        logger.info("特定频道关键词:")
        for ch, kw_list in channel_keywords.items():
            logger.info(f"  - {ch}: {kw_list}")
    if regex_patterns:
        logger.info(f"正则表达式: {regex_patterns}")
    logger.info("按 Ctrl+C 停止监控")
    logger.info("=" * 50)

    # 保持运行
    await client.run_until_disconnected()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("监控已停止")

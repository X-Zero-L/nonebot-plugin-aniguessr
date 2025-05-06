from nonebot import get_driver, logger, require
from nonebot.plugin import PluginMetadata, inherit_supported_adapters

require("nonebot_plugin_waiter")
require("nonebot_plugin_uninfo")
require("nonebot_plugin_alconna")
require("nonebot_plugin_localstore")
require("nonebot_plugin_apscheduler")

import asyncio
import json
import os
import pathlib
import random

from arclet.alconna import Alconna, Args, Arparma, Option, Subcommand
from nonebot.adapters import Bot, Event
from nonebot.exception import FinishedException, IgnoredException
from nonebot.params import Depends
from nonebot_plugin_alconna import Match, Query, UniMessage, on_alconna
from nonebot_plugin_alconna.uniseg import Image, Text
from nonebot_plugin_apscheduler import scheduler
from nonebot_plugin_uninfo import Uninfo

from .config import Config, plugin_config
from .data_source import (
    create_character_database,
    load_character_data,
    load_character_data_from_file,
    update_character_data,
)
from .game_logic import AniGuessrGame
from .model import (
    AttributeStatus,
    CharacterDatabase,
    CharacterGuessResult,
    ComparisonStatus,
    GameSettings,
)

__plugin_meta__ = PluginMetadata(
    name="猜角色",
    description="一个猜动漫角色的游戏",
    usage="发送 /aniguessr 开始游戏",
    type="application",
    homepage="https://github.com/X-Zero-L/nonebot-plugin-aniguessr",
    config=Config,
    supported_adapters=inherit_supported_adapters("nonebot_plugin_alconna", "nonebot_plugin_uninfo"),
    extra={"author": "X-Zero-L <zeroeeau@gmail.com>"},
)

# 创建游戏实例字典，用用户ID作为键
games: dict[str, AniGuessrGame] = {}
user_locks: dict[str, asyncio.Lock] = {}
# 角色数据库
character_db: CharacterDatabase | None = None


def get_lock(user_id: str) -> asyncio.Lock:
    """获取用户锁"""
    if user_id not in user_locks:
        user_locks[user_id] = asyncio.Lock()
    return user_locks[user_id]


# 开始游戏命令
aniguessr_start = on_alconna(
    Alconna(
        "/aniguessr",
        Option("-h", help_text="显示帮助信息"),
    ),
    use_cmd_start=True,
    block=True,
    aliases={"猜角色", "猜猜角色", "角色猜猜"},
)

# 猜角色命令
aniguessr_guess = on_alconna(
    Alconna(
        "/guess",
        Args["character_name", str],
    ),
    use_cmd_start=True,
    block=True,
    aliases={"/猜", "/g"},
)

# 放弃本次游戏命令
aniguessr_give_up = on_alconna(
    Alconna("/giveup"),
    use_cmd_start=True,
    block=True,
    aliases={"/放弃", "/gg"},
)

# 强制更新数据命令（仅超级用户可用）
aniguessr_update = on_alconna(
    Alconna("/aniguessr_update"),
    use_cmd_start=True,
    block=True,
    aliases={"/更新角色数据"},
    # permission="superuser",
)

# 获取候选角色列表命令
aniguessr_candidates = on_alconna(
    Alconna("/candidates"),
    use_cmd_start=True,
    block=True,
    aliases={"/提示", "/候选"},
)


@aniguessr_start.handle()
async def handle_start(
    bot: Bot,
    event: Event,
    uninfo: Uninfo,
):
    # 获取用户ID
    user_id = uninfo.user.id

    # 获取用户锁，防止同一用户同时开始多个游戏
    lock = get_lock(user_id)
    if lock.locked():
        await aniguessr_start.finish(UniMessage("你已经在进行一场游戏了，请完成当前游戏或放弃后再开始新游戏"))

    async with lock:
        # 如果已经有游戏在进行中
        if user_id in games:
            await aniguessr_start.finish(UniMessage("你已经在进行一场游戏了，请完成当前游戏或放弃后再开始新游戏"))

        # 创建新游戏
        try:
            game_settings = GameSettings()  # 使用默认设置

            game = AniGuessrGame(character_db, settings=game_settings)
            games[user_id] = game

            # 生成随机提示
            hints = game.get_random_attrs()

            # 发送游戏开始消息
            start_msg = "游戏开始！请使用 /guess 角色名 来猜测。\n\n提示：这个角色的特征包括：\n"

            # 格式化提示，每个提示一行
            for hint in hints:
                start_msg += f"✅ {hint}\n"

            # 增加说明已确认属性
            start_msg += "\n这些是初始确认的特征，你可以通过猜测来获取更多线索。"

            start_msg += "\n\n游戏设置：\n"
            start_msg += f"• 最大尝试次数: {game.settings.max_attempts}\n"
            start_msg += f"• 游戏超时时间: {game.settings.timeout_seconds}秒\n"
            start_msg += "\n使用 /guess 角色名 来猜测，/candidates 查看候选角色，或 /giveup 放弃游戏"

            await aniguessr_start.finish(UniMessage(start_msg))
        except FinishedException:
            pass
        except Exception as e:
            logger.error(f"开始游戏出错: {e}")
            await aniguessr_start.finish(UniMessage(f"游戏启动失败: {e}"))


@aniguessr_guess.handle()
async def handle_guess(
    bot: Bot,
    event: Event,
    uninfo: Uninfo,
    character_name: Match[str],
):
    # 获取用户ID
    user_id = uninfo.user.id
    character_name = character_name.result
    # 检查是否有游戏在进行
    if user_id not in games:
        await aniguessr_guess.finish(UniMessage("你还没有开始游戏，请先使用 /aniguessr 开始游戏"))

    lock = get_lock(user_id)
    async with lock:
        game = games[user_id]

        # 检查游戏是否超时
        if game.is_timed_out():
            target_name = game.get_target_name()
            games.pop(user_id)
            await aniguessr_guess.finish(UniMessage(f"游戏已超时。正确答案是：{target_name}"))

        # 检查是否达到最大尝试次数
        if game.is_max_attempts_reached():
            target_name = game.get_target_name()
            games.pop(user_id)
            await aniguessr_guess.finish(UniMessage(f"已达到最大尝试次数 {game.attempts}。正确答案是：{target_name}"))

        # 进行猜测
        try:
            guess_result = await game.make_guess(character_name)

            # 根据猜测结果构建响应消息
            if guess_result.is_correct:
                # 游戏结束，猜对了
                games.pop(user_id)
                await aniguessr_guess.finish(
                    UniMessage(
                        f"恭喜你猜对了！正确角色是：{guess_result.target_name}\n你总共猜了 {guess_result.attempts} 次"
                    )
                )
            else:
                # 继续游戏
                msg = f"第 {guess_result.attempts} 次猜测：{character_name}\n\n"

                # 添加相似度比较信息
                msg += "比较结果：\n"
                for attr, detail in guess_result.comparisons.items():
                    indicator = ""
                    if detail.status == ComparisonStatus.EXACT:
                        indicator = "🟢"
                    elif detail.status == ComparisonStatus.CLOSE:
                        indicator = "🟡"
                    elif detail.status == ComparisonStatus.HIGHER:
                        indicator = "⬆️"
                    elif detail.status == ComparisonStatus.LOWER:
                        indicator = "⬇️"
                    elif detail.status == ComparisonStatus.DIFFERENT:
                        indicator = "❌"

                    msg += f"{indicator} {attr}: {detail.value}"
                    if detail.description:
                        msg += f" ({detail.description})"
                    msg += "\n"

                # 显示剩余尝试次数
                remaining_attempts = game.settings.max_attempts - game.attempts
                remaining_time = int(
                    game.settings.timeout_seconds - (asyncio.get_event_loop().time() - game.start_time)
                )

                msg += f"\n剩余尝试次数: {remaining_attempts}, 剩余时间: {remaining_time}秒"
                msg += "\n使用 /guess 角色名 继续猜测，/candidates 查看候选角色，或 /giveup 放弃本次游戏"

                await aniguessr_guess.finish(UniMessage(msg))
        except ValueError as e:
            # 角色不在数据库中
            await aniguessr_guess.finish(UniMessage(f"错误：{e!s}"))
        except FinishedException:
            pass
        except Exception as e:
            logger.error(f"猜测过程中出错: {e}")
            await aniguessr_guess.finish(UniMessage(f"出现错误: {e!s}"))


@aniguessr_give_up.handle()
async def handle_give_up(
    uninfo: Uninfo,
):
    # 获取用户ID
    user_id = uninfo.user.id

    # 检查是否有游戏在进行
    if user_id not in games:
        await aniguessr_give_up.finish(UniMessage("你还没有开始游戏，无需放弃"))

    # 获取正确答案并结束游戏
    game = games.pop(user_id)
    target_name = game.get_target_name()

    await aniguessr_give_up.finish(UniMessage(f"游戏结束！正确答案是：{target_name}"))


@aniguessr_update.handle()
async def handle_update():
    """处理强制更新数据的请求"""
    await aniguessr_update.send(UniMessage("正在更新角色数据，请稍等..."))

    success = await update_character_data()
    if success:
        await aniguessr_update.finish(UniMessage("角色数据更新成功！"))
    else:
        await aniguessr_update.finish(UniMessage("角色数据更新失败，请查看日志"))


# 定时任务：每周更新一次角色数据
@scheduler.scheduled_job("cron", day_of_week=0, hour=3, minute=0)
async def scheduled_update_data():
    """定时更新角色数据（每周一凌晨3点）"""
    logger.info("开始执行定时角色数据更新")
    try:
        success = await update_character_data()
        if success:
            logger.info("定时角色数据更新成功")
        else:
            logger.error("定时角色数据更新失败")
    except Exception as e:
        logger.error(f"定时更新角色数据时出错: {e}")


@aniguessr_candidates.handle()
async def handle_candidates(
    uninfo: Uninfo,
):
    """处理获取候选角色列表的请求"""
    # 获取用户ID
    user_id = uninfo.user.id

    # 检查是否有游戏在进行
    if user_id not in games:
        await aniguessr_candidates.finish(UniMessage("你还没有开始游戏，请先使用 /aniguessr 开始游戏"))

    game = games[user_id]

    # 获取已知的属性状态
    attr_status = game.get_attribute_status()

    msg = "当前已知信息：\n"

    if attr_status.confirmed:
        msg += "\n已确认目标角色具有的特征：\n"
        for attr in sorted(attr_status.confirmed):
            msg += f"✅ {attr}\n"

    if attr_status.excluded:
        msg += "\n已确认目标角色不具有的特征：\n"
        for attr in sorted(attr_status.excluded):
            msg += f"❌ {attr}\n"

    # 获取可能的候选角色
    candidates = game.get_candidate_characters()

    if candidates:
        # 如果候选列表过长，只显示前10个
        if len(candidates) > 10:
            msg += f"\n可能的候选角色 (共{len(candidates)}个，显示前10个)：\n"
            for char in candidates[:10]:
                msg += f"• {char}\n"
            msg += "...\n"
        else:
            msg += f"\n可能的候选角色 (共{len(candidates)}个)：\n"
            for char in candidates:
                msg += f"• {char}\n"
    else:
        if not attr_status.is_empty():
            msg += "\n暂无符合条件的候选角色，请继续猜测获取更多线索。\n"
        else:
            msg += "\n目前没有足够的线索，请通过猜测获取更多信息。\n"

    msg += "\n继续使用 /guess 角色名 进行猜测"

    await aniguessr_candidates.finish(UniMessage(msg))


driver = get_driver()


# 启动时尝试加载或下载数据
@driver.on_startup
async def init_character_data():
    """初始化角色数据"""
    logger.info("开始初始化角色数据")
    global character_db

    try:
        # 尝试创建角色数据库
        db = await create_character_database()
        if db:
            character_db = db
            logger.info(
                f"成功初始化角色数据库，包含 {len(db.characters)} 个角色和 {len(db.get_all_attributes())} 个属性"
            )

            # 输出一些统计信息
            most_attrs = 0
            most_attrs_char = ""
            for char_name, attrs in db.characters.items():
                if len(attrs) > most_attrs:
                    most_attrs = len(attrs)
                    most_attrs_char = char_name

            logger.info(f"属性最多的角色是 {most_attrs_char}，共有 {most_attrs} 个属性")
        else:
            logger.error("初始化角色数据库失败")
            # 尝试下载角色数据
            logger.info("尝试更新角色数据...")
            if await update_character_data():
                logger.info("数据更新成功，重新尝试初始化")
                db = await create_character_database()
                if db:
                    character_db = db
                    logger.info(f"重新初始化成功，角色数据库包含 {len(db.characters)} 个角色")
                else:
                    logger.error("重新初始化失败")
            else:
                logger.error("数据更新失败")
    except Exception as e:
        logger.error(f"初始化角色数据出错: {e}")

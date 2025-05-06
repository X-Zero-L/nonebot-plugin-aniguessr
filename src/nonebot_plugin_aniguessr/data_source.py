import json

import aiofiles
import httpx
from nonebot import logger
import nonebot_plugin_localstore as store

from .config import plugin_config
from .model import (
    Bgm2Moegirl,
    Char2Attr,
    CharacterDatabase,
    CharacterDataCollection,
    Id2Tags,
)

# 数据存储路径
DATA_DIR = store.get_plugin_data_dir()
# 确保数据目录存在
DATA_DIR.mkdir(parents=True, exist_ok=True)


async def download_character_data(force_update: bool = False) -> bool:
    """
    从远程下载角色数据
    Args:
        force_update: 是否强制更新，即使本地文件已存在
    Returns:
        bool: 下载是否成功
    """
    # 定义需要下载的文件列表
    files_to_download = [
        (
            "char2attr.json",
            "https://raw.githubusercontent.com/kennylimz/anime-character-guessr/main/data_server/data/char2attr.json",
        ),
        (
            "bgm2moegirl.json",
            "https://raw.githubusercontent.com/kennylimz/anime-character-guessr/main/data_server/data/bgm2moegirl.json",
        ),
        (
            "id_tags_mapping.json",
            "https://raw.githubusercontent.com/kennylimz/anime-character-guessr/main/data_server/data/id_tags_mapping.json",
        ),
        (
            "filtered_id_tags_mapping.json",
            "https://raw.githubusercontent.com/kennylimz/anime-character-guessr/main/data_server/data/filtered_id_tags_mapping.json",
        ),
    ]

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            for file_name, url in files_to_download:
                file_path = DATA_DIR / file_name

                # 如果文件已存在且不强制更新，则跳过
                if not force_update and file_path.exists():
                    logger.info(f"文件 {file_name} 已存在，跳过下载")
                    continue

                logger.info(f"正在下载 {file_name} 从 {url}")
                response = await client.get(url)

                if response.status_code == 200:
                    # 保存文件
                    async with aiofiles.open(file_path, "wb") as f:
                        await f.write(response.content)
                    logger.info(f"文件 {file_name} 下载成功")
                else:
                    logger.error(f"下载 {file_name} 失败，状态码: {response.status_code}")
                    return False

        return True

    except Exception as e:
        logger.error(f"下载角色数据失败: {e}")
        return False


async def load_character_data_from_file() -> CharacterDataCollection:
    """
    从本地文件加载角色数据
    Returns:
        CharacterDataCollection: 角色数据集合
    """
    # 检查数据文件是否存在，如果不存在则尝试下载
    required_files = ["char2attr.json", "bgm2moegirl.json", "id_tags_mapping.json", "filtered_id_tags_mapping.json"]
    all_files_exist = all((DATA_DIR / f).exists() for f in required_files)

    if not all_files_exist:
        logger.info("数据文件不完整，尝试下载")
        if not await download_character_data():
            logger.error("下载数据文件失败")
            return CharacterDataCollection.create_empty()

    try:
        # 加载char2attr.json
        char2attr_path = DATA_DIR / "char2attr.json"
        async with aiofiles.open(char2attr_path, encoding="utf-8") as f:
            char2attr_content = await f.read()
            char2attr = json.loads(char2attr_content)

        # 加载bgm2moegirl.json
        bgm2moegirl_path = DATA_DIR / "bgm2moegirl.json"
        async with aiofiles.open(bgm2moegirl_path, encoding="utf-8") as f:
            bgm2moegirl_content = await f.read()
            bgm2moegirl = json.loads(bgm2moegirl_content)

        # 加载id_tags_mapping.json
        id_tags_path = DATA_DIR / "id_tags_mapping.json"
        async with aiofiles.open(id_tags_path, encoding="utf-8") as f:
            id_tags_content = await f.read()
            id_tags = json.loads(id_tags_content)

        # 加载filtered_id_tags_mapping.json
        filtered_id_tags_path = DATA_DIR / "filtered_id_tags_mapping.json"
        async with aiofiles.open(filtered_id_tags_path, encoding="utf-8") as f:
            filtered_id_tags_content = await f.read()
            filtered_id_tags = json.loads(filtered_id_tags_content)

        # 创建并返回角色数据集合
        return CharacterDataCollection(
            char2attr=char2attr, bgm2moegirl=bgm2moegirl, id_tags=id_tags, filtered_id_tags=filtered_id_tags
        )

    except Exception as e:
        logger.error(f"加载角色数据文件失败: {e}")
        return CharacterDataCollection.create_empty()


async def filter_character_data(min_attrs: int = 5) -> Char2Attr:
    """
    过滤角色数据，只保留属性数量不少于min_attrs的角色
    Args:
        min_attrs: 最小属性数量
    Returns:
        Char2Attr: 过滤后的角色属性字典
    """
    data_collection = await load_character_data_from_file()

    filtered_char2attr = {}
    for char_name, attrs in data_collection.char2attr.items():
        if len(attrs) >= min_attrs:
            filtered_char2attr[char_name] = attrs

    return filtered_char2attr


async def create_character_database() -> CharacterDatabase | None:
    """
    创建并返回角色数据库对象
    Returns:
        Optional[CharacterDatabase]: 角色数据库对象，如果创建失败则返回None
    """
    data_collection = await load_character_data_from_file()

    if data_collection.is_empty():
        logger.error("加载角色数据失败，无法创建角色数据库")
        return None

    # 创建角色数据库（使用配置中的最小属性数量进行过滤）
    try:
        character_db = data_collection.create_database(plugin_config.aniguessr_min_attrs)
        logger.info(f"成功创建角色数据库，包含 {len(character_db.characters)} 个角色")
        return character_db
    except Exception as e:
        logger.error(f"创建角色数据库失败: {e}")
        return None


async def preprocess_character_data() -> bool:
    """
    预处理角色数据，生成额外的索引或优化结构
    Returns:
        bool: 预处理是否成功
    """
    try:
        data_collection = await load_character_data_from_file()

        if data_collection.is_empty():
            logger.error("角色数据为空，无法预处理")
            return False

        # 创建属性到角色的反向索引
        attr2chars = {}
        for char_name, attrs in data_collection.char2attr.items():
            for attr in attrs:
                if attr not in attr2chars:
                    attr2chars[attr] = []
                attr2chars[attr].append(char_name)

        # 保存预处理后的数据
        attr2chars_path = DATA_DIR / "attr2chars.json"

        async with aiofiles.open(attr2chars_path, "w", encoding="utf-8") as f:
            await f.write(json.dumps(attr2chars, ensure_ascii=False, indent=2))

        return True

    except Exception as e:
        logger.error(f"预处理角色数据失败: {e}")
        return False


async def update_character_data() -> bool:
    """
    更新角色数据
    Returns:
        bool: 更新是否成功
    """
    try:
        # 强制下载最新数据
        if not await download_character_data(force_update=True):
            return False

        # 预处理数据
        if not await preprocess_character_data():
            return False

        return True

    except Exception as e:
        logger.error(f"更新角色数据失败: {e}")
        return False


async def load_character_data() -> CharacterDataCollection:
    """
    加载并处理角色数据，用于游戏
    返回：CharacterDataCollection 对象，包含角色属性字典、BGM到萌娘百科映射、ID到标签映射等
    """
    try:
        # 加载数据
        data_collection = await load_character_data_from_file()

        # 如果数据为空，返回空集合
        if data_collection.is_empty():
            logger.error("角色数据加载失败，可能是文件不存在或格式错误")
            return CharacterDataCollection.create_empty()

        # 获取数据并根据需要进行过滤
        char2attr = data_collection.char2attr
        if plugin_config.aniguessr_min_attrs > 0:
            filtered_char2attr = await filter_character_data(plugin_config.aniguessr_min_attrs)
            if filtered_char2attr:
                logger.info(f"过滤后的角色数量：{len(filtered_char2attr)}，原数量：{len(char2attr)}")
                # 创建新的data_collection对象，使用过滤后的char2attr
                data_collection = CharacterDataCollection(
                    char2attr=filtered_char2attr,
                    bgm2moegirl=data_collection.bgm2moegirl,
                    id_tags=data_collection.id_tags,
                    filtered_id_tags=data_collection.filtered_id_tags,
                )

        return data_collection

    except Exception as e:
        logger.error(f"加载角色数据失败: {e}")
        return CharacterDataCollection.create_empty()

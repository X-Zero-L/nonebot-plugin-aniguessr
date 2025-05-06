from nonebot import get_driver, get_plugin_config
from pydantic import BaseModel


class Config(BaseModel):
    aniguessr_data_dir: str = ""  # 角色数据目录路径，默认使用插件内置的数据
    aniguessr_max_hints: int = 3  # 游戏开始时提供的提示数量
    aniguessr_max_attempts: int = 10  # 最大猜测次数，超过后游戏自动结束
    aniguessr_timeout: int = 999999  # 游戏超时时间（秒），超过后自动结束
    aniguessr_min_attrs: int = 5  # 角色最少需要有多少个属性才会被纳入游戏


# 配置加载
plugin_config: Config = get_plugin_config(Config)
global_config = get_driver().config

# 全局名称
NICKNAME: str = next(iter(global_config.nickname), "")

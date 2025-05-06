from dataclasses import dataclass
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

"""
# data/id_tags_mapping.json
# id2tags
example:
"123": ["白毛", "红瞳"],
"""
Id2Tags = dict[str, list[str]]

"""
filtered_id_tags_mapping.json
"""
FilteredId2Tags = dict[str, list[str]]

"""
# data/bgm2moegirl.json
# bgm2moegirl
example:
"50557":["阴阳师手游:鬼使白","妖怪屋:鬼使白","百闻牌:鬼使白","小白(甜心格格)","小白(白蛇：缘起)","小白(虚拟UP主)","小白(蜡笔小新)","白(烟草)"]
"""
Bgm2Moegirl = dict[str, list[str]]

"""
# data/char2attr.json
# char2attr
example:
"时崎狂三":["颜艺","大小姐","学生","高中生","转学生","失忆","恋猫","嗜杀","高速移动能力者","回复能力者","时光穿梭能力者","时间回溯能力者","时间停止能力者","吸取生命力能力者","影子能力者","预知未来能力者","巨乳","黑发","红瞳","金瞳","异色瞳","刘海","长刘海","遮眼发","遮单眼发","马尾","双马尾","下双马尾","特殊瞳孔","枪械","火枪","双枪","双持武器","反差萌","腹黑","狂气","凛娇","女王(性格)","S属性","温柔","亦正亦邪","愉悦犯","口癖","撩裙子","女王三段笑","特殊第一人称","第一人称Watakushi","吊带装","发饰","发箍","哥特萝莉装","婚纱","袜子","吊带袜","连裤袜","黑色连裤袜","靴子","长靴","眼罩","制服","侦探","自带BGM"
"""
Char2Attr = dict[str, list[str]]


"""
# attr2chars.json (根据char2attr生成的反向索引)
# 属性到角色的映射
example:
"双马尾": ["时崎狂三", "初音未来", ...]
"""
Attr2Chars = dict[str, list[str]]


class ComparisonStatus(str, Enum):
    """比较结果状态"""

    EXACT = "exact"  # 完全匹配
    CLOSE = "close"  # 接近匹配
    HIGHER = "higher"  # 目标值更高
    LOWER = "lower"  # 目标值更低
    DIFFERENT = "different"  # 完全不同


class AttributeComparison(BaseModel):
    """属性比较结果"""

    status: ComparisonStatus
    value: str
    description: str | None = None

    model_config = ConfigDict(
        frozen=True,
    )


class CharacterAttribute(BaseModel):
    """角色属性"""

    name: str
    attributes: list[str]

    model_config = ConfigDict(
        frozen=True,
    )

    def has_attribute(self, attr: str) -> bool:
        """检查角色是否有某个属性"""
        return attr in self.attributes


class CharacterDatabase(BaseModel):
    """角色数据库"""

    characters: dict[str, list[str]]
    attribute_to_characters: dict[str, list[str]] = Field(default_factory=dict)

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
    )

    def __init__(self, char_data: dict[str, list[str]], **kwargs):
        # 初始化角色数据
        super().__init__(characters=char_data, **kwargs)

        # 构建属性到角色的映射
        attr_to_chars = {}
        for char_name, attrs in char_data.items():
            for attr in attrs:
                if attr not in attr_to_chars:
                    attr_to_chars[attr] = []
                attr_to_chars[attr].append(char_name)

        self.attribute_to_characters = attr_to_chars

    def get_character(self, name: str) -> CharacterAttribute | None:
        """获取角色属性"""
        if name not in self.characters:
            return None
        return CharacterAttribute(name=name, attributes=self.characters[name])

    def get_characters_with_attribute(self, attr: str) -> list[str]:
        """获取具有特定属性的角色列表"""
        return self.attribute_to_characters.get(attr, [])

    def get_all_attributes(self) -> set[str]:
        """获取所有属性集合"""
        return set(self.attribute_to_characters.keys())

    def get_random_character(self) -> CharacterAttribute:
        """随机获取一个角色"""
        import random

        name = random.choice(list(self.characters.keys()))
        return self.get_character(name)


class CharacterDataCollection(BaseModel):
    """角色数据集合"""

    char2attr: Char2Attr
    bgm2moegirl: Bgm2Moegirl
    id_tags: Id2Tags
    filtered_id_tags: FilteredId2Tags = Field(default_factory=dict)

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
    )

    def is_empty(self) -> bool:
        """检查数据集合是否为空"""
        return not bool(self.char2attr)

    def create_database(self, min_attrs: int = 0) -> CharacterDatabase:
        """根据数据创建角色数据库"""
        if min_attrs > 0:
            # 过滤掉属性数量不足的角色
            filtered_data = {name: attrs for name, attrs in self.char2attr.items() if len(attrs) >= min_attrs}
            return CharacterDatabase(char_data=filtered_data)

        return CharacterDatabase(char_data=self.char2attr)

    def get_character_count(self) -> int:
        """获取角色数量"""
        return len(self.char2attr)

    @classmethod
    def create_empty(cls) -> "CharacterDataCollection":
        """创建空的数据集合"""
        return cls(char2attr={}, bgm2moegirl={}, id_tags={}, filtered_id_tags={})


@dataclass
class CharacterGuessResult:
    """角色猜测结果"""

    is_correct: bool
    comparisons: dict[str, AttributeComparison]
    target_name: str
    attempts: int


class GameSettings(BaseModel):
    """游戏设置"""

    max_attempts: int = Field(default=10, description="最大尝试次数")
    timeout_seconds: int = Field(default=300, description="游戏超时时间（秒）")
    hint_count: int = Field(default=3, description="初始提示数量")
    min_attrs: int = Field(default=5, description="角色最少需要的属性数量")


class AttributeStatus(BaseModel):
    """已知的属性状态"""

    confirmed: set[str] = Field(default_factory=set, description="已确认目标角色拥有的属性")
    excluded: set[str] = Field(default_factory=set, description="已确认目标角色没有的属性")

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
    )

    def is_empty(self) -> bool:
        """检查是否有任何已知属性"""
        return not self.confirmed and not self.excluded

    def add_confirmed(self, attr: str) -> None:
        """添加已确认属性"""
        self.confirmed.add(attr)

    def add_excluded(self, attr: str) -> None:
        """添加已排除属性"""
        self.excluded.add(attr)

    def add_confirmed_many(self, attrs: list[str] | set[str]) -> None:
        """添加多个已确认属性"""
        self.confirmed.update(attrs)

    def add_excluded_many(self, attrs: list[str] | set[str]) -> None:
        """添加多个已排除属性"""
        self.excluded.update(attrs)

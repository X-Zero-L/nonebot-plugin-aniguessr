import asyncio
import difflib
import random

from nonebot import logger

from .config import plugin_config
from .model import (
    AttributeComparison,
    AttributeStatus,
    CharacterDatabase,
    CharacterGuessResult,
    ComparisonStatus,
    GameSettings,
)


class AniGuessrGame:
    """猜角色游戏类"""

    def __init__(
        self,
        character_db: CharacterDatabase,
        settings: GameSettings | None = None,
    ):
        self.character_db = character_db
        self.char2attr = character_db.characters

        # 使用设置或默认值
        self.settings = settings or GameSettings(
            max_attempts=plugin_config.aniguessr_max_attempts,
            timeout_seconds=plugin_config.aniguessr_timeout,
            hint_count=plugin_config.aniguessr_max_hints,
            min_attrs=plugin_config.aniguessr_min_attrs,
        )

        # 从字典中随机选择一个角色作为目标
        self.target_character = self.character_db.get_random_character()
        self.target_name = self.target_character.name
        self.target_attrs = self.target_character.attributes

        # 保存猜测历史
        self.attempts = 0
        self.guessed_characters = set()

        # 维护已知的目标角色属性状态
        self.attr_status = AttributeStatus()

        # 属性分类（用于比较）
        self.numeric_attrs = {"身高", "体重", "年龄", "胸围"}

        # 用于预加载和筛选有效属性
        self.valid_attrs = self.character_db.get_all_attributes()

        # 创建时间戳，用于超时检查
        self.start_time = asyncio.get_event_loop().time()

        logger.info(f"游戏创建成功，目标角色: {self.target_name}")

    def get_target_name(self) -> str:
        """获取目标角色名称"""
        return self.target_name

    def get_random_attrs(self, count: int | None = None) -> list[str]:
        """获取随机属性作为提示"""
        # 如果未指定数量，使用设置中的值
        if count is None:
            count = self.settings.hint_count

        # 从目标角色的属性中随机选择几个作为提示
        if len(self.target_attrs) <= count:
            # 将所有属性添加到已确认属性
            self.attr_status.add_confirmed_many(self.target_attrs)
            return self.target_attrs

        # 随机选择属性，并将其添加到已确认属性中
        selected_attrs = random.sample(self.target_attrs, count)
        self.attr_status.add_confirmed_many(selected_attrs)
        return selected_attrs

    def is_timed_out(self) -> bool:
        """检查游戏是否超时"""
        current_time = asyncio.get_event_loop().time()
        return (current_time - self.start_time) > self.settings.timeout_seconds

    def is_max_attempts_reached(self) -> bool:
        """检查是否达到最大尝试次数"""
        return self.attempts >= self.settings.max_attempts

    def _compare_numeric_attribute(self, attr: str, target_value: str, guessed_value: str) -> ComparisonStatus:
        """
        比较数值型属性
        Args:
            attr: 属性名称
            target_value: 目标角色的属性值
            guessed_value: 猜测角色的属性值
        Returns:
            ComparisonStatus: 比较结果状态
        """
        import re

        def extract_number(value: str) -> float | None:
            matches = re.findall(r"\d+\.?\d*", value)
            if matches:
                return float(matches[0])
            return None

        target_num = extract_number(target_value)
        guessed_num = extract_number(guessed_value)

        if target_num is None or guessed_num is None:
            return ComparisonStatus.DIFFERENT

        if target_num == guessed_num:
            return ComparisonStatus.EXACT
        elif target_num > guessed_num:
            return ComparisonStatus.HIGHER
        else:
            return ComparisonStatus.LOWER

    def _find_closest_character(self, character_name: str) -> str:
        """查找最接近的角色名（模糊匹配）"""
        if character_name not in self.char2attr:
            closest_matches = difflib.get_close_matches(character_name, self.char2attr.keys(), n=1, cutoff=0.6)

            if not closest_matches:
                raise ValueError(f"没有找到角色 '{character_name}'，请尝试其他角色名")

            character_name = closest_matches[0]
            logger.info(f"模糊匹配: '{character_name}'")

        return character_name

    def _compare_attributes(self, guessed_character_name: str) -> dict[str, AttributeComparison]:
        """比较目标角色和猜测角色的属性"""
        comparisons: dict[str, AttributeComparison] = {}

        guessed_character = self.character_db.get_character(guessed_character_name)
        if not guessed_character:
            return comparisons

        guessed_attrs = set(guessed_character.attributes)
        target_attrs = set(self.target_attrs)

        # 比较所有猜测角色的属性
        for attr in guessed_attrs:
            if attr in target_attrs:
                # 属性匹配，添加到已确认属性
                self.attr_status.add_confirmed(attr)

                # 两个角色都有这个属性
                if attr in self.numeric_attrs:
                    # 数值型属性特殊处理
                    status = self._compare_numeric_attribute(attr, attr, attr)

                    description = "数值相近"
                    if status == ComparisonStatus.HIGHER:
                        description = "目标角色的值更高"
                    elif status == ComparisonStatus.LOWER:
                        description = "目标角色的值更低"

                    comparisons[attr] = AttributeComparison(status=status, value=attr, description=description)
                else:
                    # 非数值型属性
                    comparisons[attr] = AttributeComparison(status=ComparisonStatus.EXACT, value=attr)
            else:
                # 目标角色没有此属性，添加到排除属性
                self.attr_status.add_excluded(attr)
                comparisons[attr] = AttributeComparison(
                    status=ComparisonStatus.DIFFERENT,
                    value="目标角色不具有此特征",
                    description="该特征不存在于目标角色中",
                )

        # 检查目标角色特有的属性（已确认但猜测角色没有的）
        confirmed_but_not_guessed = self.attr_status.confirmed - guessed_attrs
        for attr in confirmed_but_not_guessed:
            comparisons[attr] = AttributeComparison(
                status=ComparisonStatus.DIFFERENT,
                value="目标角色具有此特征",
                description="该特征存在于目标角色中",
            )

        return comparisons

    def get_candidate_characters(self) -> list[str]:
        """
        根据已知的属性状态，获取可能的候选角色列表
        Returns:
            list[str]: 候选角色名称列表
        """
        if self.attr_status.is_empty():
            # 没有任何线索时，返回空列表
            return []

        candidates = set(self.char2attr.keys())

        # 剔除已经猜过的角色
        candidates -= self.guessed_characters

        # 筛选拥有所有已确认属性的角色
        if self.attr_status.confirmed:
            for attr in self.attr_status.confirmed:
                chars_with_attr = set(self.character_db.get_characters_with_attribute(attr))
                candidates &= chars_with_attr

        # 排除拥有任何已排除属性的角色
        if self.attr_status.excluded:
            for attr in self.attr_status.excluded:
                chars_with_attr = set(self.character_db.get_characters_with_attribute(attr))
                candidates -= chars_with_attr

        return sorted(candidates)

    def get_attribute_status(self) -> AttributeStatus:
        """
        获取已知的属性状态
        Returns:
            AttributeStatus: 属性状态对象
        """
        return self.attr_status

    async def make_guess(self, character_name: str) -> CharacterGuessResult:
        """
        进行一次猜测

        参数:
            character_name: 猜测的角色名

        返回:
            CharacterGuessResult: 猜测结果
        """
        self.attempts += 1

        # 查找最接近的角色名（模糊匹配）
        character_name = self._find_closest_character(character_name)

        # 记录已猜测的角色
        self.guessed_characters.add(character_name)

        # 检查是否猜对
        is_correct = character_name == self.target_name

        # 如果猜对了，不需要进行属性比较
        comparisons = {}
        if not is_correct and character_name in self.char2attr:
            comparisons = self._compare_attributes(character_name)

        logger.info(f"猜测结果: 角色={character_name}, 正确={is_correct}, 尝试次数={self.attempts}")

        return CharacterGuessResult(
            is_correct=is_correct, comparisons=comparisons, target_name=self.target_name, attempts=self.attempts
        )

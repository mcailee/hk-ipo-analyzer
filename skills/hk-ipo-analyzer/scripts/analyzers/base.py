"""分析器抽象基类。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models.ipo_data import IPOData, DimensionScore, SubScore


class BaseAnalyzer(ABC):
    """所有维度分析器的抽象基类。"""

    dimension_key: str = ""       # 对应 config.yaml 中的 key
    dimension_name: str = ""      # 中文显示名

    @abstractmethod
    def analyze(self, data: IPOData, config: dict) -> DimensionScore:
        """执行分析，返回维度评分。"""
        ...

    def score_by_range(self, value: Optional[float],
                       ranges: list[list]) -> float:
        """通用区间映射评分。
        ranges: [[下限, 上限, 分数], ...]
        最后一个区间为闭区间 [low, high]，其余为半开区间 [low, high)。
        """
        if value is None:
            return 50.0  # 数据缺失返回中性分
        for i, r in enumerate(ranges):
            low, high, score = r[0], r[1], r[2]
            if i == len(ranges) - 1:
                # 最后一个区间：闭区间，防止精确上限值穿透
                if low <= value <= high:
                    return float(score)
            else:
                if low <= value < high:
                    return float(score)
        return 50.0

    def handle_missing(self, weight: float) -> DimensionScore:
        """数据缺失时返回中性分。"""
        return DimensionScore(
            dimension=self.dimension_key,
            display_name=self.dimension_name,
            score=50.0,
            weight=weight,
            sub_scores=[],
            analysis=f"⚠️ {self.dimension_name}数据不足，采用中性评分（50分）。",
            data_sufficient=False,
        )

    @staticmethod
    def cap_score(score: float, min_val: float = 0, max_val: float = 100) -> float:
        """限制分数范围。"""
        return max(min_val, min(max_val, score))

    @staticmethod
    def avg_scores(sub_scores: list[SubScore]) -> float:
        """子指标简单平均。"""
        if not sub_scores:
            return 50.0
        return sum(s.score for s in sub_scores) / len(sub_scores)

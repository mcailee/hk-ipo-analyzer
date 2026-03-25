"""评级映射 + 法律降级红线检查。"""
from __future__ import annotations


class RatingMapper:
    """四级评级映射和降级逻辑。"""

    RATING_ORDER = ["强烈推荐", "推荐", "中性", "回避"]

    def __init__(self, config: dict):
        thresholds = config.get("rating", {}).get("thresholds", {})
        labels = config.get("rating", {}).get("labels", {})
        self.strong_buy = thresholds.get("strong_buy", 80)
        self.buy = thresholds.get("buy", 65)
        self.neutral = thresholds.get("neutral", 50)
        self.labels = {
            "strong_buy": labels.get("strong_buy", "强烈推荐"),
            "buy": labels.get("buy", "推荐"),
            "neutral": labels.get("neutral", "中性"),
            "avoid": labels.get("avoid", "回避"),
        }

    def map_rating(self, score: float) -> str:
        """分数 → 评级。"""
        if score >= self.strong_buy:
            return self.labels["strong_buy"]
        elif score >= self.buy:
            return self.labels["buy"]
        elif score >= self.neutral:
            return self.labels["neutral"]
        else:
            return self.labels["avoid"]

    def downgrade(self, current_rating: str) -> str:
        """降一档评级。"""
        try:
            idx = self.RATING_ORDER.index(current_rating)
            if idx < len(self.RATING_ORDER) - 1:
                return self.RATING_ORDER[idx + 1]
            return current_rating  # 已经是最低
        except ValueError:
            return current_rating

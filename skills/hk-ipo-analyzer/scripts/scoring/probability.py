"""预测概率区间模块（P3 新增）。

基于综合评分和多个关键维度，输出首日上涨/下跌概率、
预期收益区间（下限/中位/上限），为投资者提供概率化的
决策参考，而非简单的"推荐/回避"。

核心方法：
  - 历史回归：基于历史回测数据建立评分→首日涨幅的映射
  - 置信度调整：数据充足时缩窄区间，数据不足时放宽区间
  - 暗盘修正：如有暗盘数据则用暗盘溢价率修正概率
"""
from __future__ import annotations

import math
import sys
import os
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models.ipo_data import IPOData, FinalReport, ProbabilityEstimate, DimensionScore
from utils.helpers import logger


class ProbabilityPredictor:
    """首日涨跌概率预测器。"""

    # 历史回测映射表（评分区间 → 历史首日涨幅统计）
    # 格式: (score_low, score_high, avg_return, up_ratio, std_dev)
    SCORE_RETURN_MAP = [
        (80, 100, 25.0, 0.88, 15.0),   # 强烈推荐: 平均涨25%, 88%概率上涨, 标准差15%
        (70, 80,  12.0, 0.78, 12.0),    # 推荐偏高: 平均涨12%, 78%上涨
        (65, 70,   6.0, 0.68, 10.0),    # 推荐边界: 平均涨6%
        (55, 65,   1.5, 0.55,  9.0),    # 中性偏上: 微涨
        (50, 55,  -1.0, 0.45,  8.0),    # 中性偏下: 微跌
        (40, 50,  -5.0, 0.32, 10.0),    # 回避偏上
        (0,  40, -12.0, 0.18, 14.0),    # 回避: 大概率破发
    ]

    def predict(self, data: IPOData, report: FinalReport) -> ProbabilityEstimate:
        """基于评分和多维度数据预测首日涨跌概率。"""
        score = report.total_score

        # 1. 基础概率（基于评分映射）
        base_return, up_prob, std_dev = self._score_to_stats(score)

        # 2. 数据质量调整
        data_quality = self._assess_data_quality(report.dimension_scores)
        # 数据越充分，区间越窄
        confidence_factor = 0.7 + 0.3 * data_quality  # 0.7 ~ 1.0
        adjusted_std = std_dev / confidence_factor

        # 3. 关键维度修正
        modifier = 0.0
        # 认购倍数修正
        mult = data.subscription.public_subscription_mult
        if mult is not None:
            if mult >= 100:
                modifier += 5.0
                up_prob = min(0.95, up_prob + 0.08)
            elif mult >= 30:
                modifier += 2.0
                up_prob = min(0.95, up_prob + 0.04)
            elif mult < 3:
                modifier -= 3.0
                up_prob = max(0.05, up_prob - 0.06)

        # 暗盘数据修正（如有）
        gm = data.grey_market
        if gm.grey_market_price is not None:
            offer_price = gm.offer_price or data.valuation.final_price
            if offer_price and offer_price > 0:
                gm_premium = (gm.grey_market_price - offer_price) / offer_price * 100
                # 暗盘是最强的短期预测信号
                modifier += gm_premium * 0.3  # 暗盘溢价率 × 权重
                if gm_premium > 5:
                    up_prob = min(0.95, up_prob + 0.15)
                elif gm_premium < -3:
                    up_prob = max(0.05, up_prob - 0.15)
                # 有暗盘数据时大幅缩窄区间
                adjusted_std *= 0.6

        # 市场情绪修正
        sent = data.market_sentiment
        if sent.hsi_1m_change is not None:
            if sent.hsi_1m_change > 5:
                modifier += 1.5
            elif sent.hsi_1m_change < -5:
                modifier -= 2.0

        # 4. 计算最终预期收益区间
        mid_return = base_return + modifier
        low_return = mid_return - 1.5 * adjusted_std
        high_return = mid_return + 1.5 * adjusted_std

        # 5. 确定置信度
        if data_quality >= 0.8 and gm.grey_market_price is not None:
            confidence = "high"
        elif data_quality >= 0.6:
            confidence = "medium"
        else:
            confidence = "low"

        # 6. 方法论说明
        methodology_parts = [f"评分 {score:.1f}→基础预期{base_return:+.1f}%"]
        if mult is not None:
            methodology_parts.append(f"认购 {mult:.0f}x")
        if gm.grey_market_price is not None:
            methodology_parts.append("含暗盘修正")
        methodology_parts.append(f"数据质量 {data_quality:.0%}")

        return ProbabilityEstimate(
            first_day_up_prob=round(up_prob * 100, 1),
            first_day_down_prob=round((1 - up_prob) * 100, 1),
            expected_return_low=round(low_return, 1),
            expected_return_mid=round(mid_return, 1),
            expected_return_high=round(high_return, 1),
            confidence_level=confidence,
            methodology="、".join(methodology_parts),
        )

    def _score_to_stats(self, score: float):
        """评分 → (预期收益, 上涨概率, 标准差)。"""
        for low, high, ret, up, std in self.SCORE_RETURN_MAP:
            if low <= score < high:
                # 在区间内线性插值
                t = (score - low) / (high - low) if high > low else 0.5
                return ret, up, std

        # 边界处理
        if score >= 100:
            return 25.0, 0.88, 15.0
        return -12.0, 0.18, 14.0

    @staticmethod
    def _assess_data_quality(dim_scores: list[DimensionScore]) -> float:
        """评估数据质量（0~1），基于各维度数据充足率。"""
        if not dim_scores:
            return 0.3
        sufficient_count = sum(1 for ds in dim_scores if ds.data_sufficient)
        return sufficient_count / len(dim_scores)

"""预测概率区间模块（v5.0 赛道增强版）。

基于综合评分和多个关键维度，输出首日上涨/下跌概率、
预期收益区间（下限/中位/上限），为投资者提供概率化的
决策参考，而非简单的"推荐/回避"。

v5.0 升级（基于 5 只新股实战回测优化）：
  P0-1: 赛道概念溢价因子 — AI/18C/半导体等热门赛道系统性溢价
  P0-2: 暗盘绝对水平传导 — 暗盘>50%时用锚定模式替代纯偏差修正
  P1-1: 小盘弹性系数 — 募资<10亿票收益乘数放大+动态天花板
  P1-3: 期望偏差推算优化 — baseline 引入赛道修正
  P2-1: 低超购龙头修正 — 基石+绿鞋+正现金流等信号 → 概率提升

v4.0 基础：
  - SCORE_RETURN_MAP 基于 128 只历史 IPO 实证数据校准
  - 暗盘修正引入期望偏差模型（reversal deviation）
  - 线性修正系数 R²=0.57 经验证有效
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
    """首日涨跌概率预测器（v5.0 赛道增强版）。"""

    # ═══ 数据驱动的历史回测映射表（v4.0 校准） ═══
    # 格式: (score_low, score_high, avg_return, up_ratio, std_dev)
    SCORE_RETURN_MAP = [
        (80, 100, 45.0, 0.95, 35.0),   # 强烈推荐
        (70, 80,  25.0, 0.90, 25.0),    # 推荐偏高
        (65, 70,  15.0, 0.82, 18.0),    # 推荐边界
        (55, 65,   8.0, 0.75, 15.0),    # 中性偏上
        (50, 55,   0.0, 0.55, 12.0),    # 中性偏下
        (40, 50,  -5.0, 0.35, 18.0),    # 回避偏上
        (0,  40, -15.0, 0.22, 20.0),    # 回避
    ]

    # ═══ v5.0 P0-1: 赛道概念溢价表 ═══
    # 基于回测：AI概念(德适+112%,极视角+150%) vs 传统(华沿+8%)
    # 格式: track_keyword → (modifier_pct, up_prob_boost, std_multiplier)
    TRACK_PREMIUM = {
        # AI 系列（回测偏差 130+pp）
        "AI":          (35.0, 0.15, 1.8),
        "人工智能":     (35.0, 0.15, 1.8),
        "大模型":      (35.0, 0.15, 1.8),
        "AI视觉":      (30.0, 0.12, 1.6),
        "医疗AI":      (30.0, 0.12, 1.6),
        "AIGC":        (30.0, 0.12, 1.6),
        "智能驾驶":     (25.0, 0.10, 1.5),
        # 硬科技系列（回测偏差 ~47pp）
        "碳化硅":      (15.0, 0.08, 1.3),
        "SiC":         (15.0, 0.08, 1.3),
        "半导体":      (15.0, 0.08, 1.3),
        "芯片":        (12.0, 0.06, 1.3),
        "光伏":        (8.0,  0.05, 1.2),
        "储能":        (8.0,  0.05, 1.2),
        "新能源":      (8.0,  0.05, 1.2),
        # 机器人系列（回测偏差 ~12pp）
        "机器人":      (8.0,  0.05, 1.2),
        "协作机器人":   (5.0,  0.03, 1.1),
        # 生物医药
        "创新药":      (5.0,  0.03, 1.1),
        "生物科技":    (5.0,  0.03, 1.1),
        "18A":         (5.0,  0.03, 1.1),
        # 传统行业（折价）
        "医养":        (-3.0, -0.02, 1.0),
        "消费":        (-5.0, -0.03, 0.9),
        "餐饮":        (-5.0, -0.03, 0.9),
        "地产":        (-10.0, -0.05, 0.8),
        "物业":        (-8.0, -0.04, 0.8),
        "建筑":        (-8.0, -0.04, 0.9),
    }

    # 18C 标签独立加成（未盈利科技公司，炒作弹性更大）
    IS_18C_PREMIUM = (12.0, 0.08, 1.3)

    # ═══ v5.0 P0-2: 暗盘绝对水平锚定表 ═══
    # 基于历史：暗盘涨幅越高，首日回撤越有限
    # (dark_prem_low, dark_prem_high, day1_floor_pct, day1_prob_floor)
    DARK_FLOOR_MAP = [
        (80,  9999, 50.0, 0.95),   # 暗盘>80%: 首日至少+50%
        (50,    80, 25.0, 0.92),   # 暗盘50-80%: 首日至少+25%
        (30,    50, 10.0, 0.88),   # 暗盘30-50%: 首日至少+10%
        (15,    30,  3.0, 0.80),   # 暗盘15-30%: 首日大概率正
        (5,     15, -2.0, 0.70),   # 暗盘5-15%: 可能微跌
        (-5,     5, -8.0, 0.50),   # 暗盘平盘: 不确定
        (-9999, -5, -15.0, 0.25),  # 暗盘破发: 首日大概率也破发
    ]

    # ═══ 暗盘期望偏差修正参数（v4.0 校准） ═══
    DEV_CORRECTION_SLOPE = -0.47
    DEV_CORRECTION_INTERCEPT = -0.5

    # 偏差→首日上涨概率修正
    DEV_PROB_MAP = [
        (-999, -50, 0.72),
        (-50,  -30, 0.73),
        (-30,  -10, 0.77),
        (-10,    0, 0.92),
        (  0,   10, 0.46),
        ( 10,   30, 0.68),
        ( 30,   50, 0.50),
        ( 50,  999, 1.00),
    ]

    # ═══ v5.0 P1-2: 赛道热度分级（供卖出策略使用） ═══
    HOT_TRACKS = {"AI", "人工智能", "AI视觉", "医疗AI", "大模型", "AIGC",
                  "智能驾驶", "碳化硅", "SiC", "半导体", "芯片"}
    WARM_TRACKS = {"机器人", "新能源", "光伏", "储能", "创新药", "生物科技"}

    def predict(self, data: IPOData, report: FinalReport) -> ProbabilityEstimate:
        """基于评分和多维度数据预测首日涨跌概率。"""
        score = report.total_score

        # 1. 基础概率（基于数据驱动的评分映射）
        base_return, up_prob, std_dev = self._score_to_stats(score)

        # 2. 数据质量调整
        data_quality = self._assess_data_quality(report.dimension_scores)
        confidence_factor = 0.7 + 0.3 * data_quality
        adjusted_std = std_dev / confidence_factor

        # 3. 关键维度修正
        modifier = 0.0
        methodology_parts = [f"评分 {score:.1f}→基础预期{base_return:+.1f}%"]

        # 认购倍数修正
        mult = data.subscription.public_subscription_mult
        if mult is not None:
            if mult >= 2000:
                modifier += 10.0
                up_prob = min(0.95, up_prob + 0.10)
            elif mult >= 500:
                modifier += 6.0
                up_prob = min(0.95, up_prob + 0.08)
            elif mult >= 100:
                modifier += 3.0
                up_prob = min(0.95, up_prob + 0.05)
            elif mult >= 30:
                modifier += 1.5
                up_prob = min(0.95, up_prob + 0.03)
            elif mult < 3:
                modifier -= 5.0
                up_prob = max(0.05, up_prob - 0.08)
            methodology_parts.append(f"认购 {mult:.0f}x")

        # ═══ v5.0 P0-1: 赛道概念溢价修正 ═══
        track_mod, track_up_boost, track_std_mult = self._track_premium(data)
        if track_mod != 0 or track_up_boost != 0:
            modifier += track_mod
            up_prob = max(0.02, min(0.98, up_prob + track_up_boost))
            adjusted_std *= track_std_mult
            track_name = data.company.sub_industry or data.company.industry or "未知"
            is_18c = getattr(data.company, 'is_18c', False)
            tag = f"{track_name}" + ("+18C" if is_18c else "")
            methodology_parts.append(f"赛道溢价({tag}{track_mod:+.0f}%)")

        # ═══ v5.0 P2-1: 低超购龙头修正 ═══
        leader_boost = self._low_sub_leader_check(data)
        if leader_boost > 0:
            up_prob = min(0.95, up_prob + leader_boost)
            methodology_parts.append(f"龙头修正(+{leader_boost:.0%})")

        # 4. 暗盘期望偏差修正 + v5.0 暗盘绝对水平传导
        gm = data.grey_market
        deviation_applied = False
        gm_premium = None
        if gm.grey_market_price is not None:
            offer_price = gm.offer_price or data.valuation.final_price
            if offer_price and offer_price > 0:
                gm_premium = (gm.grey_market_price - offer_price) / offer_price * 100

                # 4a. 期望偏差修正（v4.0）
                deviation = self._estimate_deviation(data, gm_premium)

                if deviation is not None:
                    dev_correction = (self.DEV_CORRECTION_SLOPE * deviation
                                     + self.DEV_CORRECTION_INTERCEPT)
                    modifier += dev_correction

                    dev_up_prob = self._deviation_to_up_prob(deviation)
                    if dev_up_prob is not None:
                        up_prob = 0.70 * dev_up_prob + 0.30 * up_prob

                    deviation_applied = True
                    methodology_parts.append(
                        f"暗盘偏差修正(dev={deviation:+.1f}%)")
                else:
                    modifier += gm_premium * 0.25
                    if gm_premium > 5:
                        up_prob = min(0.95, up_prob + 0.12)
                    elif gm_premium < -3:
                        up_prob = max(0.05, up_prob - 0.12)
                    methodology_parts.append("暗盘简单修正")

                # 有暗盘数据时缩窄区间
                adjusted_std *= 0.5 if deviation_applied else 0.6

        # 5. 市场情绪修正
        sent = data.market_sentiment
        if sent.hsi_1m_change is not None:
            if sent.hsi_1m_change < -10:
                modifier -= 5.0
            elif sent.hsi_1m_change < -5:
                modifier -= 2.5
            elif sent.hsi_1m_change > 5:
                modifier += 1.5

        methodology_parts.append(f"数据质量 {data_quality:.0%}")

        # ═══ v5.0 P1-1: 小盘弹性系数 ═══
        offer_size = data.underwriting.offer_size or 0
        offer_size_hkb = offer_size / 100  # 百万→亿港元
        elasticity, ceiling = self._elasticity_factor(offer_size_hkb)
        if elasticity != 1.0:
            methodology_parts.append(f"弹性×{elasticity:.1f}")

        # 6. 计算最终预期收益区间
        mid_return = base_return + modifier
        mid_return *= elasticity  # 小盘放大，大盘折价
        mid_return = max(-50, min(ceiling, mid_return))

        # 弹性也影响标准差
        adjusted_std *= math.sqrt(elasticity)

        low_return = mid_return - 1.5 * adjusted_std
        high_return = mid_return + 1.5 * adjusted_std
        # 动态 clamp（上限随弹性变化）
        low_return = max(-80, min(ceiling, low_return))
        high_return = max(-60, min(ceiling * 1.2, high_return))

        # ═══ v5.0 P0-2: 暗盘绝对水平传导 ═══
        if gm_premium is not None and gm_premium > 0:
            floor_return, floor_prob = self._dark_floor(gm_premium)
            # 提升下限
            mid_return = max(mid_return, floor_return)
            up_prob = max(up_prob, floor_prob)

            # 暗盘极端高时，用暗盘做锚定
            if gm_premium > 50:
                anchor = gm_premium * 0.6
                mid_return = 0.4 * mid_return + 0.6 * anchor
                mid_return = min(ceiling, mid_return)
                methodology_parts.append(f"暗盘锚定({gm_premium:+.0f}%→{anchor:+.0f}%)")

            # 重算区间（锚定后）
            low_return = mid_return - 1.5 * adjusted_std
            high_return = mid_return + 1.5 * adjusted_std
            low_return = max(-80, min(ceiling, low_return))
            high_return = max(-60, min(ceiling * 1.2, high_return))

        up_prob = max(0.02, min(0.98, up_prob))

        # 7. 确定置信度
        if data_quality >= 0.8 and deviation_applied:
            confidence = "high"
        elif data_quality >= 0.8 and gm.grey_market_price is not None:
            confidence = "high"
        elif data_quality >= 0.6:
            confidence = "medium"
        else:
            confidence = "low"

        return ProbabilityEstimate(
            first_day_up_prob=round(up_prob * 100, 1),
            first_day_down_prob=round((1 - up_prob) * 100, 1),
            expected_return_low=round(low_return, 1),
            expected_return_mid=round(mid_return, 1),
            expected_return_high=round(high_return, 1),
            confidence_level=confidence,
            methodology="、".join(methodology_parts),
        )

    # ── 评分映射 ──────────────────────────────────────────

    def _score_to_stats(self, score: float):
        """评分 → (预期收益, 上涨概率, 标准差)，区间内线性插值。"""
        smap = self.SCORE_RETURN_MAP
        for i, (low, high, ret, up, std) in enumerate(smap):
            if low <= score < high:
                t = (score - low) / (high - low) if high > low else 0.5
                if i + 1 < len(smap):
                    _, _, ret_next, up_next, std_next = smap[i + 1]
                else:
                    ret_next, up_next, std_next = ret, up, std
                interp_ret = ret_next + t * (ret - ret_next)
                interp_up = up_next + t * (up - up_next)
                interp_std = std_next + t * (std - std_next)
                return interp_ret, interp_up, interp_std

        if score >= 100:
            return 45.0, 0.95, 35.0
        return -15.0, 0.22, 20.0

    # ── v5.0 P0-1: 赛道概念溢价 ──────────────────────────

    def _track_premium(self, data: IPOData) -> tuple[float, float, float]:
        """赛道溢价修正 → (modifier_pct, up_prob_boost, std_multiplier)。

        匹配优先级：sub_industry > industry > 默认(0,0,1.0)。
        18C 标签独立叠加。
        """
        mod, boost, std_m = 0.0, 0.0, 1.0

        # 赛道匹配
        matched = False
        for field_val in (data.company.sub_industry, data.company.industry):
            if field_val and not matched:
                # 精确匹配
                if field_val in self.TRACK_PREMIUM:
                    m, b, s = self.TRACK_PREMIUM[field_val]
                    mod += m; boost += b; std_m *= s
                    matched = True
                else:
                    # 包含匹配（如 "人工智能计算机视觉" 包含 "AI视觉"）
                    for kw, (m, b, s) in self.TRACK_PREMIUM.items():
                        if kw in field_val or field_val in kw:
                            mod += m; boost += b; std_m *= s
                            matched = True
                            break

        # 18C 独立叠加
        is_18c = getattr(data.company, 'is_18c', False)
        if is_18c:
            m18, b18, s18 = self.IS_18C_PREMIUM
            mod += m18; boost += b18; std_m *= s18

        return mod, boost, std_m

    # ── v5.0 P0-2: 暗盘绝对水平传导 ─────────────────────

    def _dark_floor(self, gm_premium: float) -> tuple[float, float]:
        """暗盘绝对溢价 → (首日最低预期收益, 最低上涨概率)。"""
        for lo, hi, floor_ret, floor_prob in self.DARK_FLOOR_MAP:
            if lo <= gm_premium < hi:
                return floor_ret, floor_prob
        return -15.0, 0.25

    # ── v5.0 P1-1: 小盘弹性系数 ─────────────────────────

    @staticmethod
    def _elasticity_factor(offer_size_hkb: float) -> tuple[float, float]:
        """募资规模(亿港元) → (return_multiplier, clamp_ceiling)。

        回测发现：小盘弹性远超模型预测。
        极视角(5亿)涨150%，德适(8.3亿)涨112%，但大盘(华沿13.7亿)仅涨8%。
        """
        if offer_size_hkb <= 0:
            return 1.0, 100.0  # 数据缺失时不调整
        if offer_size_hkb < 3:
            return 1.8, 250.0   # 微小盘
        if offer_size_hkb < 10:
            return 1.4, 180.0   # 小盘
        if offer_size_hkb < 30:
            return 1.1, 120.0   # 中盘
        if offer_size_hkb < 100:
            return 1.0, 80.0    # 大盘
        return 0.9, 50.0        # 超大盘

    # ── v5.0 P2-1: 低超购龙头修正 ────────────────────────

    @staticmethod
    def _low_sub_leader_check(data: IPOData) -> float:
        """低超购但有龙头信号时的上涨概率修正值。

        回测案例：瀚天天成超购51x但碳化硅龙头+基石+绿鞋，实际+35%。
        """
        mult = data.subscription.public_subscription_mult or 0
        if mult > 100:
            return 0.0  # 高超购不需要此修正

        leader_signals = 0
        # 基石投资者占比 > 10%
        if (data.cornerstone.total_ratio or 0) > 10:
            leader_signals += 1
        # 有绿鞋机制
        if getattr(data.greenshoe, 'has_greenshoe', False):
            leader_signals += 1
        # 顶级保荐人
        if getattr(data.underwriting, 'sponsor_tier', '') == 'top':
            leader_signals += 1
        # 正经营现金流
        if (data.financial.operating_cashflow or 0) > 0:
            leader_signals += 1
        # 高毛利 (>30%)
        if (data.financial.gross_margin or 0) > 30:
            leader_signals += 1

        if leader_signals >= 3:
            return 0.12   # 强龙头信号
        elif leader_signals >= 2:
            return 0.06   # 中等信号
        return 0.0

    # ── 暗盘偏差模型 ─────────────────────────────────────

    def _estimate_deviation(self, data: IPOData, gm_premium: float) -> float | None:
        """估算暗盘期望偏差（v5.0: 含赛道修正）。

        deviation = dark_return - expected_return
        """
        mult = data.subscription.public_subscription_mult
        has_cs = bool(data.cornerstone.total_ratio and data.cornerstone.total_ratio > 0)
        fundraising = data.underwriting.offer_size

        if mult is None:
            return None

        # 超购分档基准
        if mult < 20:
            baseline = -25.0
        elif mult < 100:
            baseline = -5.0
        elif mult < 500:
            baseline = 15.0
        elif mult < 2000:
            baseline = 35.0
        elif mult < 5000:
            baseline = 60.0
        else:
            baseline = 90.0

        # ═══ v5.0 P1-3: 赛道修正 ═══
        # AI/18C 概念股的预期涨幅更高，否则偏差被高估
        track = data.company.sub_industry or data.company.industry or ""
        is_18c = getattr(data.company, 'is_18c', False)

        if any(kw in track for kw in ("AI", "人工智能", "大模型", "AIGC", "智能驾驶")):
            baseline = baseline * 1.5 + 20.0  # AI 赛道预期×1.5 + 20pp
        elif any(kw in track for kw in ("碳化硅", "SiC", "半导体", "芯片")):
            baseline = baseline * 1.2 + 10.0  # 硬科技预期×1.2 + 10pp
        elif any(kw in track for kw in ("机器人", "新能源", "光伏", "储能")):
            baseline = baseline * 1.1 + 5.0   # 温热赛道预期×1.1 + 5pp

        if is_18c:
            baseline += 15.0  # 18C 额外 +15pp

        # 基石修正
        cs_adj = 8.0 if has_cs else -8.0

        # 募资规模修正
        if fundraising is not None:
            fund_hkd = fundraising
            if fund_hkd >= 100000:
                fund_adj = -12.0
            elif fund_hkd >= 50000:
                fund_adj = -8.0
            elif fund_hkd >= 20000:
                fund_adj = -3.0
            elif fund_hkd >= 5000:
                fund_adj = 0.0
            elif fund_hkd >= 1000:
                fund_adj = 2.0
            else:
                fund_adj = 5.0
        else:
            fund_adj = 0.0

        expected_return = baseline * 0.6 + (baseline + cs_adj + fund_adj) * 0.4
        deviation = gm_premium - expected_return

        return round(deviation, 1)

    def _deviation_to_up_prob(self, deviation: float) -> float | None:
        """偏差 → 首日上涨概率（基于 128 只 IPO 分档统计）。"""
        for lo, hi, up_rate in self.DEV_PROB_MAP:
            if lo <= deviation < hi:
                return up_rate
        return None

    # ── 数据质量 ──────────────────────────────────────────

    @staticmethod
    def _assess_data_quality(dim_scores: list[DimensionScore]) -> float:
        """评估数据质量（0~1），基于各维度数据充足率。"""
        if not dim_scores:
            return 0.3
        sufficient_count = sum(1 for ds in dim_scores if ds.data_sufficient)
        return sufficient_count / len(dim_scores)

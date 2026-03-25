"""中签率计算器（P3 新增）。

基于公开认购倍数、发行规模、每手股数和发行价等参数，
估算中签率、建议认购手数和资金效率。

核心公式：
  - 基础中签率 = 1 / 认购倍数
  - 一手中签率 ≈ min(1, 公开发售股数 / (每手股数 × 认购人数))
  - 资金效率 = (预期收益 × 中签概率) / (冻结资金 × 冻结天数 / 365)

支持两种模式:
  - 预估模式: 基于历史相似IPO的认购倍数预测
  - 确定模式: 认购数据公布后的精确计算
"""
from __future__ import annotations

import math
import sys
import os
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models.ipo_data import IPOData, AllotmentEstimate
from utils.helpers import logger


class AllotmentCalculator:
    """中签率计算器。"""

    # 港股 IPO 经验参数
    DEFAULT_FREEZE_DAYS = 5             # 平均冻结资金天数
    DEFAULT_LOT_SIZE = 500              # 默认每手股数
    BROKERAGE_FEE_RATE = 0.001         # 券商佣金率
    LEVY_RATE = 0.00257                 # 印花税+交易征费等
    FINANCING_COST_ANNUAL = 0.05        # 融资利率（年化 5%）

    def calculate(self, data: IPOData, config: dict | None = None,
                  target_hands: int | None = None,
                  use_financing: bool = False) -> AllotmentEstimate:
        """计算中签率和资金效率。

        Args:
            data: IPO 数据
            config: 配置（可选）
            target_hands: 目标认购手数（不提供则自动推荐）
            use_financing: 是否使用孖展（融资打新）
        """
        sub = data.subscription
        val = data.valuation
        uw = data.underwriting

        # 基础参数
        offer_price = val.final_price or val.offer_price_high or val.offer_price_low
        lot_size = self.DEFAULT_LOT_SIZE
        if val.total_shares and val.total_shares > 0:
            # 尝试从发行股数推算每手（港股常见500/1000/2000）
            for ls in [100, 200, 500, 1000, 2000, 4000, 5000, 10000]:
                if val.total_shares % ls == 0:
                    lot_size = ls
                    break

        if offer_price is None or offer_price <= 0:
            return AllotmentEstimate(
                methodology="数据不足：缺少发行价信息"
            )

        # 每手所需资金
        capital_per_hand = offer_price * lot_size
        # 加上手续费（约 1.0027%）
        total_per_hand = capital_per_hand * (1 + self.BROKERAGE_FEE_RATE + 0.0027)

        # 认购倍数
        mult = sub.public_subscription_mult

        if mult is not None and mult > 0:
            mode = "确定模式"
            # ── 确定模式：已有认购数据 ──
            basic_allot_rate = 100.0 / mult  # 基础中签率 (%)

            # 一手中签率（港股分配机制：优先保证一手）
            # 经验公式：一手中签率 ≈ min(100%, 基础中签率 × 认购倍数调整系数)
            if mult <= 5:
                one_hand_rate = min(100, basic_allot_rate * 1.5)
            elif mult <= 15:
                one_hand_rate = min(100, basic_allot_rate * 2.0)
            elif mult <= 50:
                one_hand_rate = min(95, basic_allot_rate * 2.5)
            elif mult <= 100:
                one_hand_rate = min(80, basic_allot_rate * 3.0)
            else:
                # 超高倍数时，一手中签率约 10%-40%
                one_hand_rate = max(5, min(50, 1000 / mult))

        else:
            mode = "预估模式"
            # ── 预估模式：基于市值/行业/发行规模估算 ──
            est_mult = self._estimate_subscription_mult(data)
            if est_mult <= 0:
                return AllotmentEstimate(
                    methodology="预估模式：无法估算认购倍数"
                )
            mult = est_mult
            basic_allot_rate = 100.0 / mult
            one_hand_rate = max(5, min(80, 1000 / mult)) if mult > 10 else min(100, basic_allot_rate * 2.0)

        # 建议认购手数（最优化资金效率）
        if target_hands is None:
            target_hands = self._optimal_hands(mult, one_hand_rate)

        # 资金需求
        total_capital = total_per_hand * target_hands
        if use_financing:
            # 孖展打新，通常 90% 融资
            own_capital = total_capital * 0.1
            finance_cost = total_capital * 0.9 * self.FINANCING_COST_ANNUAL * self.DEFAULT_FREEZE_DAYS / 365
            effective_capital = own_capital + finance_cost
        else:
            effective_capital = total_capital

        # 预期收益（基于认购倍数的经验预期首日涨幅）
        expected_first_day_return = self._expected_return_from_mult(mult)
        expected_profit_per_hand = capital_per_hand * expected_first_day_return / 100

        # 中签后预期持仓手数 — 基于中签率
        est_winning_hands = max(1, round(target_hands * basic_allot_rate / 100))

        # 资金效率（年化）
        actual_profit = expected_profit_per_hand * est_winning_hands
        capital_efficiency = (actual_profit / effective_capital) * (365 / self.DEFAULT_FREEZE_DAYS) * 100 if effective_capital > 0 else 0

        return AllotmentEstimate(
            estimated_allocation_rate=round(basic_allot_rate, 2),
            estimated_one_hand_win_rate=round(one_hand_rate, 1),
            optimal_hands=target_hands,
            expected_profit_per_hand=round(expected_profit_per_hand, 0),
            capital_required=round(effective_capital, 0),
            capital_efficiency=round(capital_efficiency, 1),
            methodology=f"{mode}：认购倍数 {mult:.0f}x → 基础中签率 {basic_allot_rate:.2f}%，建议认购 {target_hands} 手",
        )

    def _estimate_subscription_mult(self, data: IPOData) -> float:
        """基于市值、行业等特征预估认购倍数。"""
        market_cap = data.valuation.market_cap or 0
        offer_size = data.underwriting.offer_size or 0
        industry = data.company.industry or ""

        # 基础估算（基于发行规模）
        if offer_size > 0:
            if offer_size < 200:
                base_mult = 20   # 微型IPO通常认购热
            elif offer_size < 1000:
                base_mult = 12
            elif offer_size < 5000:
                base_mult = 6
            else:
                base_mult = 3    # 大型IPO认购倍数低
        elif market_cap > 0:
            if market_cap < 1000:
                base_mult = 15
            elif market_cap < 5000:
                base_mult = 8
            else:
                base_mult = 4
        else:
            base_mult = 8  # 默认

        # 行业调整
        hot_keywords = ["AI", "人工智能", "芯片", "半导体", "新能源", "医药", "biotech"]
        for kw in hot_keywords:
            if kw.lower() in industry.lower():
                base_mult *= 1.5
                break

        return base_mult

    @staticmethod
    def _optimal_hands(mult: float, one_hand_rate: float) -> int:
        """推荐最优认购手数。"""
        if mult <= 5:
            return 1
        elif mult <= 20:
            return 3
        elif mult <= 50:
            return 5
        elif mult <= 100:
            return 10
        elif mult <= 300:
            return 20
        else:
            return 30  # 超高倍数 → 多申保证一手

    @staticmethod
    def _expected_return_from_mult(mult: float) -> float:
        """基于认购倍数的经验预期首日涨幅 (%)。"""
        if mult >= 300:
            return 30
        elif mult >= 100:
            return 20
        elif mult >= 50:
            return 12
        elif mult >= 20:
            return 8
        elif mult >= 10:
            return 5
        elif mult >= 5:
            return 2
        else:
            return -2  # 低认购 → 可能破发

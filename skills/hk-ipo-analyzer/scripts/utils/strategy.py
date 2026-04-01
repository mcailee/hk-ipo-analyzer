"""打新策略引擎（P4 新增）。

根据投资者资金量级、账户数量、融资意愿等，结合 IPO 认购热度数据，
输出最优打新策略推荐（甲组/乙组分配、多账户矩阵、融资成本精算）。

核心概念：
  - 甲组 (Group A): ≤500万港元，优先保证一人一手分配
  - 乙组 (Group B): >500万港元，按申购金额比例分配
  - 甲乙双打: 同一投资者同时在甲/乙两个分配池认购
  - 多账户矩阵: 利用多个甲组账户提升一手中签概率
  - 孖展 (融资): 杠杆放大认购额，需计算利息成本

策略类型：
  - A_only: 纯甲组（单/多账户）
  - B_only: 纯乙组
  - AB_dual: 甲乙双打
  - multi_A: 多账户甲组矩阵
  - multi_A_plus_B: 多账户甲组 + 乙组
"""
from __future__ import annotations

import math
import sys
import os
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models.ipo_data import (
    IPOData,
    AccountAllocation,
    GroupSimulation,
    StrategyRecommendation,
)
from utils.helpers import logger


class StrategyEngine:
    """打新策略引擎。"""

    # ── 默认参数（可被 config 覆盖）────────────────────────
    GROUP_A_MAX = 5_000_000          # 甲组申购上限 (HKD)
    DEFAULT_FREEZE_DAYS = 5
    BROKERAGE_FEE_RATE = 0.001
    LEVY_RATE = 0.00257
    DEFAULT_PUBLIC_RATIO = 0.10      # 默认公开发售占比

    # 回拨阈值: [(倍数, 公开发售占比)]
    CLAWBACK_TIERS = [(15, 0.30), (50, 0.40), (100, 0.50)]

    # 融资利率分档: [(倍数, 年化利率)]
    FINANCING_TIERS = [
        (0, 0.00), (1, 0.038), (5, 0.042), (10, 0.048), (20, 0.055)
    ]

    def __init__(self, config: dict | None = None):
        self.config = config or {}
        strat_cfg = self.config.get("strategy", {})

        # 加载配置覆盖
        ga = strat_cfg.get("group_a", {})
        self.GROUP_A_MAX = ga.get("max_amount", self.GROUP_A_MAX)

        cb = strat_cfg.get("clawback", {})
        raw_tiers = cb.get("tiers")
        if raw_tiers:
            self.CLAWBACK_TIERS = [(t[0], t[1]) for t in raw_tiers]
        self.DEFAULT_PUBLIC_RATIO = cb.get("default_public_ratio", self.DEFAULT_PUBLIC_RATIO)

        raw_fin = strat_cfg.get("financing_tiers")
        if raw_fin:
            self.FINANCING_TIERS = [(t[0], t[1]) for t in raw_fin]

        allot_cfg = self.config.get("allotment", {})
        self.FREEZE_DAYS = allot_cfg.get("freeze_days", self.DEFAULT_FREEZE_DAYS)
        self.BROKERAGE_FEE_RATE = allot_cfg.get("brokerage_fee_rate", self.BROKERAGE_FEE_RATE)

    # ══════════════════════════════════════════════════════════
    #  主入口
    # ══════════════════════════════════════════════════════════

    def recommend(
        self,
        data: IPOData,
        total_capital: float = 0,
        num_accounts: int = 1,
        financing_mult: float = 0,
    ) -> StrategyRecommendation:
        """生成完整打新策略推荐。

        Args:
            data: IPO 数据（需含 subscription/valuation 信息）
            total_capital: 投资者可用总资金 (HKD)，0=自动按默认估算
            num_accounts: 可用证券账户数量
            financing_mult: 融资倍数（0=现金, 10=10倍孖展）
        """
        rec = StrategyRecommendation()

        # 基础参数
        val = data.valuation
        sub = data.subscription
        offer_price = val.final_price or val.offer_price_high or val.offer_price_low
        if not offer_price or offer_price <= 0:
            rec.methodology = "数据不足：缺少发行价信息"
            return rec

        lot_size = self._infer_lot_size(offer_price, val.total_shares)
        capital_per_hand = offer_price * lot_size
        mult = sub.public_subscription_mult or 0

        # 发行规模（百万HKD → HKD）
        offer_size_hkd = (data.underwriting.offer_size or 0) * 1_000_000

        # 确定投资者量级
        tier_info = self._classify_investor(total_capital)
        rec.investor_tier = tier_info["id"]
        rec.investor_tier_label = tier_info["label"]
        rec.total_capital = total_capital
        rec.num_accounts = num_accounts

        # 如果未指定融资倍数，按量级默认值
        if financing_mult <= 0:
            financing_mult = tier_info.get("default_financing", 0)

        # ── 甲组/乙组分配模拟 ──
        rec.group_a_sim = self._simulate_group_a(
            mult, offer_size_hkd, capital_per_hand, lot_size
        )
        rec.group_b_sim = self._simulate_group_b(
            mult, offer_size_hkd, capital_per_hand
        )

        # ── 枚举所有可行策略并选最优 ──
        strategies = self._enumerate_strategies(
            total_capital=total_capital,
            num_accounts=num_accounts,
            financing_mult=financing_mult,
            capital_per_hand=capital_per_hand,
            lot_size=lot_size,
            mult=mult,
            offer_size_hkd=offer_size_hkd,
            group_a_sim=rec.group_a_sim,
            group_b_sim=rec.group_b_sim,
        )

        if not strategies:
            rec.methodology = "资金不足：无法认购至少一手"
            return rec

        # 选择预期净收益最高的策略
        best = max(strategies, key=lambda s: s["total_net_profit"])

        # 填充推荐结果
        rec.recommended_strategy = best["strategy_type"]
        rec.strategy_label = best["strategy_label"]
        rec.strategy_rationale = best["rationale"]
        rec.accounts = best["accounts"]
        rec.total_subscription_amount = best["total_sub_amount"]
        rec.total_own_capital = best["total_own_capital"]
        rec.total_financing_cost = best["total_fin_cost"]
        rec.total_expected_profit = best["total_gross_profit"]
        rec.total_expected_net_profit = best["total_net_profit"]
        rec.overall_roi = (
            best["total_net_profit"] / best["total_own_capital"] * 100
            if best["total_own_capital"] > 0 else 0
        )
        rec.capital_efficiency_annualized = (
            rec.overall_roi * 365 / self.FREEZE_DAYS
            if self.FREEZE_DAYS > 0 else 0
        )

        # 风控数据
        rec.breakeven_return = self._calc_breakeven(best)
        rec.max_loss_scenario = self._calc_max_loss(best, capital_per_hand)

        rec.methodology = (
            f"策略引擎 v1.0 | 资金 HK${total_capital:,.0f} | "
            f"{num_accounts} 账户 | "
            f"{'现金' if financing_mult <= 0 else f'{financing_mult:.0f}倍孖展'} | "
            f"认购倍数 {mult:.0f}x"
        )

        return rec

    # ══════════════════════════════════════════════════════════
    #  甲组模拟
    # ══════════════════════════════════════════════════════════

    def _simulate_group_a(
        self,
        mult: float,
        offer_size_hkd: float,
        capital_per_hand: float,
        lot_size: int,
    ) -> GroupSimulation:
        """模拟甲组分配。"""
        sim = GroupSimulation(group="A")
        if mult <= 0:
            sim.methodology = "无认购倍数数据，无法模拟"
            return sim

        # 计算回拨后甲组分配池
        public_ratio = self._clawback_ratio(mult)
        public_shares = (offer_size_hkd / capital_per_hand * lot_size) * public_ratio if offer_size_hkd > 0 else 0
        # 甲组通常拿公开发售的 50%（甲乙各半，具体依回拨后比例）
        group_a_shares = public_shares * 0.5
        sim.total_pool_shares = group_a_shares

        # 甲组申请人数预估（经验值：认购倍数 × 基础人数系数）
        if offer_size_hkd > 0:
            # 基础预估：认购总额 / 平均每人认购额(~10万HKD)
            avg_sub_per_person = 100_000
            sim.total_applicants_est = mult * (offer_size_hkd * public_ratio * 0.5) / avg_sub_per_person
            sim.total_applicants_est = max(sim.total_applicants_est, 1000)
        else:
            sim.total_applicants_est = mult * 5000

        # 甲组中签率
        if group_a_shares > 0 and sim.total_applicants_est > 0:
            hands_available = group_a_shares / lot_size
            # 一手中签率：可分配手数 / 申请人数
            sim.one_hand_rate = min(100, hands_available / sim.total_applicants_est * 100)
            # 总中签率
            sim.allocation_rate = 100.0 / mult if mult > 0 else 100
        else:
            sim.one_hand_rate = 0
            sim.allocation_rate = 0

        sim.methodology = f"甲组 | 回拨后公开发售占比 {public_ratio*100:.0f}% | 一手中签率 {sim.one_hand_rate:.1f}%"
        return sim

    # ══════════════════════════════════════════════════════════
    #  乙组模拟
    # ══════════════════════════════════════════════════════════

    def _simulate_group_b(
        self,
        mult: float,
        offer_size_hkd: float,
        capital_per_hand: float,
    ) -> GroupSimulation:
        """模拟乙组分配（按比例分配）。"""
        sim = GroupSimulation(group="B")
        if mult <= 0:
            sim.methodology = "无认购倍数数据，无法模拟"
            return sim

        public_ratio = self._clawback_ratio(mult)
        public_amount = offer_size_hkd * public_ratio if offer_size_hkd > 0 else 0
        group_b_amount = public_amount * 0.5  # 乙组拿公开发售的另一半
        sim.total_pool_shares = group_b_amount

        # 乙组中签率 ≈ 乙组可分配金额 / 乙组总认购金额
        # 乙组总认购金额是未知的，但可以基于整体认购倍数粗略估算
        # 经验：乙组认购金额约占总公开认购的 30-50%（大型IPO更高）
        group_b_sub_ratio = 0.40  # 假设乙组占总公开认购的40%
        total_public_sub = offer_size_hkd * public_ratio * mult
        group_b_total_sub = total_public_sub * group_b_sub_ratio

        if group_b_total_sub > 0 and group_b_amount > 0:
            sim.allocation_rate = group_b_amount / group_b_total_sub * 100
        else:
            # 无法精确估算时按整体倍数粗估
            sim.allocation_rate = 100.0 / mult if mult > 0 else 100

        sim.allocation_rate = min(100, sim.allocation_rate)
        sim.methodology = (
            f"乙组 | 按比例分配 | 预估中签率 {sim.allocation_rate:.2f}% "
            f"(基于乙组占比 {group_b_sub_ratio*100:.0f}% 假设)"
        )
        return sim

    # ══════════════════════════════════════════════════════════
    #  策略枚举
    # ══════════════════════════════════════════════════════════

    def _enumerate_strategies(
        self,
        total_capital: float,
        num_accounts: int,
        financing_mult: float,
        capital_per_hand: float,
        lot_size: int,
        mult: float,
        offer_size_hkd: float,
        group_a_sim: GroupSimulation,
        group_b_sim: GroupSimulation,
    ) -> list[dict]:
        """枚举所有可行策略方案。"""
        strategies = []
        expected_return_pct = self._expected_return_from_mult(mult) / 100.0
        fee_rate = self.BROKERAGE_FEE_RATE + self.LEVY_RATE

        # 甲组上限手数
        max_a_hands = int(self.GROUP_A_MAX / (capital_per_hand * (1 + fee_rate)))
        max_a_hands = max(max_a_hands, 1)

        # 融资放大后的购买力
        leverage = 1 + financing_mult if financing_mult > 0 else 1
        effective_capital = total_capital * leverage
        fin_rate = self._get_financing_rate(financing_mult)

        # ── 策略1: 纯甲组（单账户摸一手）──
        if capital_per_hand * (1 + fee_rate) <= effective_capital:
            acct = self._build_account(
                account_id=1, group="A", hands=1,
                capital_per_hand=capital_per_hand,
                financing_mult=financing_mult, fin_rate=fin_rate,
                alloc_rate=group_a_sim.one_hand_rate or 0,
                expected_return_pct=expected_return_pct,
                fee_rate=fee_rate,
            )
            strategies.append({
                "strategy_type": "A_only",
                "strategy_label": "甲组摸一手",
                "rationale": "最低资金投入，博一手中签",
                "accounts": [acct],
                **self._summarize_accounts([acct]),
            })

        # ── 策略2: 甲组甲尾（最优手数）──
        optimal_a = self._calc_optimal_a_hands(mult, group_a_sim)
        a_tail_hands = min(optimal_a, max_a_hands)
        a_tail_cost = a_tail_hands * capital_per_hand * (1 + fee_rate)
        if a_tail_cost <= effective_capital and a_tail_hands > 1:
            acct = self._build_account(
                account_id=1, group="A", hands=a_tail_hands,
                capital_per_hand=capital_per_hand,
                financing_mult=financing_mult, fin_rate=fin_rate,
                alloc_rate=group_a_sim.allocation_rate or 0,
                expected_return_pct=expected_return_pct,
                fee_rate=fee_rate,
            )
            strategies.append({
                "strategy_type": "A_only",
                "strategy_label": f"甲组甲尾({a_tail_hands}手)",
                "rationale": f"甲组最优手数 {a_tail_hands} 手，平衡中签率与资金效率",
                "accounts": [acct],
                **self._summarize_accounts([acct]),
            })

        # ── 策略3: 甲组甲头（打满甲组上限）──
        a_top_cost = max_a_hands * capital_per_hand * (1 + fee_rate)
        if a_top_cost <= effective_capital and max_a_hands > a_tail_hands:
            acct = self._build_account(
                account_id=1, group="A", hands=max_a_hands,
                capital_per_hand=capital_per_hand,
                financing_mult=financing_mult, fin_rate=fin_rate,
                alloc_rate=group_a_sim.allocation_rate or 0,
                expected_return_pct=expected_return_pct,
                fee_rate=fee_rate,
            )
            strategies.append({
                "strategy_type": "A_only",
                "strategy_label": f"甲组甲头({max_a_hands}手)",
                "rationale": "甲组满额认购，最大化甲组分配概率",
                "accounts": [acct],
                **self._summarize_accounts([acct]),
            })

        # ── 策略4: 多账户甲组矩阵 ──
        if num_accounts >= 2:
            accounts = []
            remaining = effective_capital
            for i in range(min(num_accounts, 5)):  # 最多5个甲组账户
                hands = min(max_a_hands, int(remaining / (capital_per_hand * (1 + fee_rate))))
                if hands <= 0:
                    break
                acct = self._build_account(
                    account_id=i + 1, group="A", hands=hands,
                    capital_per_hand=capital_per_hand,
                    financing_mult=financing_mult, fin_rate=fin_rate,
                    alloc_rate=group_a_sim.one_hand_rate or 0,
                    expected_return_pct=expected_return_pct,
                    fee_rate=fee_rate,
                )
                accounts.append(acct)
                remaining -= acct.own_capital
                if remaining <= 0:
                    break

            if len(accounts) >= 2:
                strategies.append({
                    "strategy_type": "multi_A",
                    "strategy_label": f"多账户甲组矩阵({len(accounts)}户)",
                    "rationale": f"{len(accounts)} 个甲组账户独立参与分配，多次中签一手的概率更高",
                    "accounts": accounts,
                    **self._summarize_accounts(accounts),
                })

        # ── 策略5: 纯乙组 ──
        group_b_min = self.GROUP_A_MAX + 1
        if effective_capital >= group_b_min:
            b_hands = int(effective_capital / (capital_per_hand * (1 + fee_rate)))
            acct = self._build_account(
                account_id=1, group="B", hands=b_hands,
                capital_per_hand=capital_per_hand,
                financing_mult=financing_mult, fin_rate=fin_rate,
                alloc_rate=group_b_sim.allocation_rate or 0,
                expected_return_pct=expected_return_pct,
                fee_rate=fee_rate,
            )
            strategies.append({
                "strategy_type": "B_only",
                "strategy_label": f"纯乙组({b_hands}手)",
                "rationale": "大额资金走乙组按比例分配，确保获配",
                "accounts": [acct],
                **self._summarize_accounts([acct]),
            })

        # ── 策略6: 甲乙双打（1甲+1乙）──
        if effective_capital >= group_b_min + capital_per_hand * (1 + fee_rate):
            # 分配：甲组用最优手数，剩余全部进乙组
            a_cap_for_dual = min(
                max_a_hands * capital_per_hand * (1 + fee_rate),
                effective_capital * 0.3  # 甲组最多用30%资金
            )
            a_hands_dual = max(1, int(a_cap_for_dual / (capital_per_hand * (1 + fee_rate))))
            a_hands_dual = min(a_hands_dual, max_a_hands)

            b_remaining = effective_capital - a_hands_dual * capital_per_hand * (1 + fee_rate)
            b_hands_dual = int(b_remaining / (capital_per_hand * (1 + fee_rate)))

            if b_hands_dual > 0:
                a_acct = self._build_account(
                    account_id=1, group="A", hands=a_hands_dual,
                    capital_per_hand=capital_per_hand,
                    financing_mult=financing_mult, fin_rate=fin_rate,
                    alloc_rate=group_a_sim.one_hand_rate or 0,
                    expected_return_pct=expected_return_pct,
                    fee_rate=fee_rate,
                )
                b_acct = self._build_account(
                    account_id=2, group="B", hands=b_hands_dual,
                    capital_per_hand=capital_per_hand,
                    financing_mult=financing_mult, fin_rate=fin_rate,
                    alloc_rate=group_b_sim.allocation_rate or 0,
                    expected_return_pct=expected_return_pct,
                    fee_rate=fee_rate,
                )
                strategies.append({
                    "strategy_type": "AB_dual",
                    "strategy_label": f"甲乙双打(甲{a_hands_dual}手+乙{b_hands_dual}手)",
                    "rationale": "甲乙两个分配池独立参与，双重中签机会",
                    "accounts": [a_acct, b_acct],
                    **self._summarize_accounts([a_acct, b_acct]),
                })

        # ── 策略7: 多甲+乙 终极组合 ──
        if num_accounts >= 3 and effective_capital >= group_b_min + capital_per_hand * 2 * (1 + fee_rate):
            accounts = []
            remaining = effective_capital

            # 留一部分给乙组（约50%）
            b_budget = remaining * 0.5
            a_budget = remaining - b_budget

            # 甲组账户
            for i in range(min(num_accounts - 1, 4)):
                per_a_budget = a_budget / min(num_accounts - 1, 4)
                hands = min(max_a_hands, int(per_a_budget / (capital_per_hand * (1 + fee_rate))))
                if hands <= 0:
                    break
                acct = self._build_account(
                    account_id=i + 1, group="A", hands=hands,
                    capital_per_hand=capital_per_hand,
                    financing_mult=financing_mult, fin_rate=fin_rate,
                    alloc_rate=group_a_sim.one_hand_rate or 0,
                    expected_return_pct=expected_return_pct,
                    fee_rate=fee_rate,
                )
                accounts.append(acct)

            # 乙组账户
            b_hands = int(b_budget / (capital_per_hand * (1 + fee_rate)))
            if b_hands > 0:
                b_acct = self._build_account(
                    account_id=len(accounts) + 1, group="B", hands=b_hands,
                    capital_per_hand=capital_per_hand,
                    financing_mult=financing_mult, fin_rate=fin_rate,
                    alloc_rate=group_b_sim.allocation_rate or 0,
                    expected_return_pct=expected_return_pct,
                    fee_rate=fee_rate,
                )
                accounts.append(b_acct)

            if len(accounts) >= 3:
                a_count = sum(1 for a in accounts if a.group == "A")
                strategies.append({
                    "strategy_type": "multi_A_plus_B",
                    "strategy_label": f"多甲+乙({a_count}甲+1乙)",
                    "rationale": f"{a_count} 个甲组矩阵 + 乙组按比例分配，攻守兼备",
                    "accounts": accounts,
                    **self._summarize_accounts(accounts),
                })

        return strategies

    # ══════════════════════════════════════════════════════════
    #  辅助方法
    # ══════════════════════════════════════════════════════════

    def _build_account(
        self,
        account_id: int,
        group: str,
        hands: int,
        capital_per_hand: float,
        financing_mult: float,
        fin_rate: float,
        alloc_rate: float,
        expected_return_pct: float,
        fee_rate: float,
    ) -> AccountAllocation:
        """构建单账户分配方案。"""
        sub_amount = hands * capital_per_hand * (1 + fee_rate)
        leverage = 1 + financing_mult if financing_mult > 0 else 1

        if financing_mult > 0:
            own_capital = sub_amount / leverage
            fin_amount = sub_amount - own_capital
            fin_cost = fin_amount * fin_rate * self.FREEZE_DAYS / 365
        else:
            own_capital = sub_amount
            fin_amount = 0
            fin_cost = 0

        # 预期中签手数
        winning_hands = hands * alloc_rate / 100.0
        # 预期收益（首日卖出）
        gross_profit = winning_hands * capital_per_hand * expected_return_pct
        net_profit = gross_profit - fin_cost
        roi = net_profit / own_capital * 100 if own_capital > 0 else 0

        return AccountAllocation(
            account_id=account_id,
            group=group,
            subscription_hands=hands,
            subscription_amount=round(sub_amount, 0),
            own_capital=round(own_capital, 0),
            financing_amount=round(fin_amount, 0),
            financing_mult=financing_mult,
            financing_cost=round(fin_cost, 0),
            total_cost=round(own_capital + fin_cost, 0),
            expected_winning_hands=round(winning_hands, 2),
            expected_profit=round(gross_profit, 0),
            expected_net_profit=round(net_profit, 0),
            roi=round(roi, 2),
        )

    def _summarize_accounts(self, accounts: list[AccountAllocation]) -> dict:
        """汇总多账户数据。"""
        return {
            "total_sub_amount": sum(a.subscription_amount for a in accounts),
            "total_own_capital": sum(a.own_capital for a in accounts),
            "total_fin_cost": sum(a.financing_cost for a in accounts),
            "total_gross_profit": sum(a.expected_profit for a in accounts),
            "total_net_profit": sum(a.expected_net_profit for a in accounts),
        }

    def _clawback_ratio(self, mult: float) -> float:
        """根据认购倍数计算回拨后公开发售占比。"""
        ratio = self.DEFAULT_PUBLIC_RATIO
        for threshold, pct in self.CLAWBACK_TIERS:
            if mult >= threshold:
                ratio = pct
        return ratio

    def _get_financing_rate(self, mult: float) -> float:
        """根据融资倍数获取对应利率。"""
        rate = 0.0
        for threshold, r in self.FINANCING_TIERS:
            if mult >= threshold:
                rate = r
        return rate

    def _calc_optimal_a_hands(self, mult: float, sim: GroupSimulation) -> int:
        """根据认购倍数计算甲组最优手数。

        逻辑：
        - 低倍数(≤5): 1手即可（大概率中签）
        - 中倍数(5-50): 3-10手，提高中签概率
        - 高倍数(50-300): 10-30手（甲尾策略）
        - 超高倍数(300+): 甲头打满
        """
        if mult <= 5:
            return 1
        elif mult <= 15:
            return 3
        elif mult <= 30:
            return 5
        elif mult <= 50:
            return 10
        elif mult <= 100:
            return 20
        elif mult <= 300:
            return 50
        else:
            return 999  # 甲头，后续由 max_a_hands 限制

    def _classify_investor(self, capital: float) -> dict:
        """根据资金量级分类投资者。"""
        strat_cfg = self.config.get("strategy", {})
        tiers_cfg = strat_cfg.get("investor_tiers", [])
        tier_strats = strat_cfg.get("tier_strategies", {})

        if tiers_cfg:
            for low, high, label, tier_id in tiers_cfg:
                if low <= capital < high:
                    ts = tier_strats.get(tier_id, {})
                    return {
                        "id": tier_id,
                        "label": label,
                        "default_financing": ts.get("financing_mult", 0),
                    }

        # 无配置时的默认分类
        if capital < 500_000:
            return {"id": "retail_small", "label": "小散", "default_financing": 0}
        elif capital < 5_000_000:
            return {"id": "retail_mid", "label": "中户", "default_financing": 10}
        elif capital < 20_000_000:
            return {"id": "whale", "label": "大户", "default_financing": 10}
        else:
            return {"id": "ultra_whale", "label": "超大户", "default_financing": 10}

    def _calc_breakeven(self, strategy: dict) -> float:
        """计算盈亏平衡所需涨幅 (%)。"""
        total_fin = strategy["total_fin_cost"]
        total_sub = strategy["total_sub_amount"]
        if total_sub <= 0:
            return 0
        return total_fin / total_sub * 100

    def _calc_max_loss(self, strategy: dict, capital_per_hand: float) -> float:
        """计算最大亏损情景（假设首日跌20%）。"""
        total_hands = sum(a.subscription_hands for a in strategy["accounts"])
        alloc_rates = [a.expected_winning_hands / a.subscription_hands
                       if a.subscription_hands > 0 else 0
                       for a in strategy["accounts"]]
        avg_alloc = sum(alloc_rates) / len(alloc_rates) if alloc_rates else 0
        winning_hands = total_hands * avg_alloc
        max_loss_on_stock = winning_hands * capital_per_hand * 0.20  # 跌20%
        total_fin_cost = strategy["total_fin_cost"]
        return round(max_loss_on_stock + total_fin_cost, 0)

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
            return -2

    def _infer_lot_size(self, offer_price: float | None,
                        total_shares: int | None) -> int:
        """基于发行价推算每手股数。"""
        COMMON_LOTS = [100, 200, 400, 500, 1000, 2000, 4000, 5000, 10000]
        TARGET_MIN, TARGET_MAX = 2000, 5000

        if offer_price and offer_price > 0:
            best = 500
            best_cost = offer_price * best
            for ls in COMMON_LOTS:
                cost = offer_price * ls
                if TARGET_MIN <= cost <= TARGET_MAX:
                    best = ls
                    best_cost = cost
            if best_cost < TARGET_MIN or best_cost > TARGET_MAX:
                best = min(COMMON_LOTS, key=lambda ls: abs(offer_price * ls - 3500))
            if total_shares and total_shares > 0 and total_shares % best != 0:
                for ls in sorted(COMMON_LOTS, key=lambda x: abs(offer_price * x - 3500)):
                    if total_shares % ls == 0:
                        best = ls
                        break
            return best
        return 500

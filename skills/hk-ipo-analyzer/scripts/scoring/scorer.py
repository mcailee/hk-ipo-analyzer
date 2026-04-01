"""综合评分引擎 — 支持分阶段加权评分 + 卖出时机建议 + 概率预测 + 中签率计算。

v3.0 优化:
  - 集成概率预测区间（P3）
  - 集成中签率计算器（P3）
  - 支持条件性维度加权（P2/P3 新增维度无数据时 weight=0）
"""
from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models.ipo_data import IPOData, DimensionScore, FinalReport, SubScore, SellTimingAdvice
from utils.helpers import get_config, detect_industry, logger


class Scorer:
    """加权评分引擎。"""

    def __init__(self, config: dict | None = None):
        self.config = config or get_config()

    def score_phase1(self, data: IPOData,
                     dimension_scores: list[DimensionScore]) -> FinalReport:
        """Phase1 评分：基本面维度（含条件性维度），权重等比放大至 100%。"""
        report = self._compute(data, dimension_scores, phase=1)

        # P3: Phase1 也生成概率预测（仅基于基本面）
        try:
            from scoring.probability import ProbabilityPredictor
            predictor = ProbabilityPredictor()
            report.probability = predictor.predict(data, report)
        except Exception as e:
            logger.warning(f"概率预测失败: {e}")

        return report

    def score_phase2(self, data: IPOData,
                     dimension_scores: list[DimensionScore],
                     phase1_report: FinalReport | None = None) -> FinalReport:
        """Phase2 评分：全维度 + 卖出时机建议 + 概率预测 + 中签率。"""
        report = self._compute(data, dimension_scores, phase=2)
        if phase1_report:
            report.phase1_score = phase1_report.total_score
            report.phase1_rating = phase1_report.rating

        # Phase2 才生成卖出时机建议
        report.sell_timing = self._generate_sell_timing(data, report)

        # P3: 概率预测区间
        try:
            from scoring.probability import ProbabilityPredictor
            predictor = ProbabilityPredictor()
            report.probability = predictor.predict(data, report)
        except Exception as e:
            logger.warning(f"概率预测失败: {e}")

        # P3: 中签率计算
        try:
            from utils.allotment import AllotmentCalculator
            calculator = AllotmentCalculator()
            report.allotment = calculator.calculate(data, self.config)
        except Exception as e:
            logger.warning(f"中签率计算失败: {e}")

        return report

    def _compute(self, data: IPOData,
                 dimension_scores: list[DimensionScore],
                 phase: int) -> FinalReport:
        """加权计算综合评分。"""
        dim_cfg = self.config["dimensions"]

        # 计算可用维度的总权重（用于等比放大）
        total_weight = sum(ds.weight for ds in dimension_scores)
        if total_weight <= 0:
            total_weight = 1.0

        # 加权求和
        weighted_sum = 0.0
        for ds in dimension_scores:
            normalized_weight = ds.weight / total_weight
            weighted_sum += ds.score * normalized_weight

        total_score = max(0, min(100, weighted_sum))

        # 评级映射
        from scoring.rating import RatingMapper
        mapper = RatingMapper(self.config)
        rating = mapper.map_rating(total_score)

        # 检查降级
        original_rating = None
        downgrade_reasons = []
        all_red_flags = []
        for ds in dimension_scores:
            all_red_flags.extend(ds.red_flags)

        if all_red_flags:
            original_rating = rating
            rating = mapper.downgrade(rating)
            downgrade_reasons = all_red_flags
            logger.warning(f"⚠️ 触发降级: {rating} (原: {original_rating}), 原因: {all_red_flags}")

        # 行业专属指标
        industry_type = detect_industry(data.company.industry, self.config)
        industry_subs = []
        for ds in dimension_scores:
            if ds.dimension in ("financial", "industry"):
                for ss in ds.sub_scores:
                    if ss.name in ("Rule of 40", "MAU", "ARPU", "LTV/CAC",
                                   "经常性收入占比", "大客户集中度",
                                   "管线数量", "核心产品阶段", "适应症市场",
                                   "同店增长", "门店扩张", "库存周转"):
                        industry_subs.append(ss)

        # 生成摘要
        summary = self._build_summary(data, total_score, rating,
                                       dimension_scores, phase)

        return FinalReport(
            stock_code=data.company.stock_code or "unknown",
            company_name=data.company.name or "未知公司",
            phase=phase,
            total_score=round(total_score, 1),
            rating=rating,
            original_rating=original_rating,
            downgrade_reasons=downgrade_reasons,
            dimension_scores=dimension_scores,
            industry=industry_type,
            industry_specific_scores=industry_subs,
            summary=summary,
        )

    def _generate_sell_timing(self, data: IPOData, report: FinalReport) -> SellTimingAdvice:
        """基于市值、认购倍数和综合评分生成卖出时机建议。

        v5.0 升级：引入赛道热度因子
        回测发现：
          - 热门赛道(AI/半导体) + 极端超购 → 首日全天上涨概率高
          - 传统赛道 + 极端超购 → 暗盘/首日即卖（后续衰减快）
          - 微小盘(<3亿): 暗盘卖最优
          - 大盘(30-100亿): 持有到 day3 最优
        """
        timing_cfg = self.config.get("sell_timing", {})
        strategies = timing_cfg.get("strategies", {})

        market_cap = data.valuation.market_cap or 0
        offer_size = data.underwriting.offer_size or 0
        sub_mult = data.subscription.public_subscription_mult or 0
        total_score = report.total_score

        offer_size_hkb = offer_size / 100  # 百万→亿港元

        # v5.0: 赛道热度分级
        track = data.company.sub_industry or data.company.industry or ""
        HOT_TRACKS = {"AI", "人工智能", "AI视觉", "医疗AI", "大模型", "AIGC",
                      "智能驾驶", "碳化硅", "SiC", "半导体", "芯片"}
        WARM_TRACKS = {"机器人", "新能源", "光伏", "储能", "创新药", "生物科技"}

        is_hot = any(kw in track for kw in HOT_TRACKS)
        is_warm = any(kw in track for kw in WARM_TRACKS)

        # 决策树（基于回测验证的最优退出时点）
        if offer_size_hkb > 0 and offer_size_hkb < 3:
            strat_key = "quick_flip"
            rationale = (f"微小盘(募资{offer_size_hkb:.1f}亿)，回测显示暗盘即卖期望最高。"
                        f"超购{sub_mult:.0f}x" + ("，炒作风险大" if sub_mult > 2000 else ""))
            confidence = "high" if sub_mult >= 100 else "medium"
        elif offer_size_hkb < 10:
            if sub_mult >= 500:
                if is_hot:
                    # v5.0: 热门赛道小盘+高超购 → 可持有到首日收盘
                    strat_key = "short_hold"
                    rationale = f"小盘(募资{offer_size_hkb:.1f}亿) + 高认购({sub_mult:.0f}x) + 热门赛道({track})，散户FOMO驱动首日全天上涨，建议尾盘卖出"
                    confidence = "medium"
                else:
                    strat_key = "quick_flip"
                    rationale = f"小盘(募资{offer_size_hkb:.1f}亿) + 高认购({sub_mult:.0f}x)，首日即卖锁定利润"
                    confidence = "high"
            else:
                strat_key = "quick_flip"
                rationale = f"小盘(募资{offer_size_hkb:.1f}亿)，流动性有限，建议首日获利了结"
                confidence = "medium"
        elif offer_size_hkb < 30:
            if sub_mult >= 500 and total_score >= 65:
                strat_key = "short_hold"
                rationale = f"中盘(募资{offer_size_hkb:.1f}亿) + 高认购+高评分，可持有到 Day3"
                confidence = "high"
            elif total_score >= 70:
                strat_key = "short_hold"
                rationale = f"中盘(募资{offer_size_hkb:.1f}亿)，评分{total_score:.0f}分较好，适当短持"
                confidence = "medium"
            else:
                strat_key = "quick_flip"
                rationale = f"中盘(募资{offer_size_hkb:.1f}亿)，评分一般，建议首日卖出"
                confidence = "medium"
        elif offer_size_hkb < 100:
            if total_score >= 75:
                strat_key = "medium_hold"
                rationale = f"大盘(募资{offer_size_hkb:.1f}亿) + 高评分({total_score:.0f})，回测显示持有到 Day3-5 最优"
                confidence = "high" if total_score >= 80 else "medium"
            else:
                strat_key = "short_hold"
                rationale = f"大盘(募资{offer_size_hkb:.1f}亿)，建议短线观察 Day1-3 后决定"
                confidence = "medium"
        else:
            if total_score >= 70:
                strat_key = "medium_hold"
                rationale = f"超大盘(募资{offer_size_hkb:.1f}亿)，机构定价充分，可中线持有 Day3-5"
                confidence = "medium"
            else:
                strat_key = "short_hold"
                rationale = f"超大盘(募资{offer_size_hkb:.1f}亿)，收益空间有限，Day1-3 择机卖出"
                confidence = "low"

        # 超购特殊修正（v5.0: 引入赛道热度豁免）
        if sub_mult < 20 and strat_key != "quick_flip":
            strat_key = "quick_flip"
            rationale = f"认购不足20倍({sub_mult:.0f}x)，回测期望为负，建议尽快卖出"
            confidence = "medium"
        elif sub_mult >= 5000:
            if is_hot:
                # v5.0 核心改动：热门赛道+极端超购 → 不降级为 quick_flip
                strat_key = "short_hold"
                rationale = (f"极端超购({sub_mult:.0f}x) + 热门赛道({track})，"
                            f"散户FOMO可能推动首日全天上涨，建议尾盘附近卖出")
                confidence = "medium"
            elif is_warm:
                strat_key = "quick_flip"
                rationale = f"极端超购({sub_mult:.0f}x) + 温热赛道({track})，首日开盘即卖"
                confidence = "high"
            else:
                strat_key = "quick_flip"
                rationale = f"极端超购({sub_mult:.0f}x)，暗盘/首日炒作见顶概率高，速战速决"
                confidence = "high"

        strat = strategies.get(strat_key, {})

        return SellTimingAdvice(
            strategy=strat_key,
            suggested_days=strat.get("max_hold_days", 3),
            rationale=rationale,
            stop_loss_pct=strat.get("stop_loss_pct", -5),
            take_profit_pct=strat.get("take_profit_pct", 15),
            confidence=confidence,
        )

    def _build_summary(self, data, score, rating, dim_scores, phase):
        """生成分析摘要。"""
        name = data.company.name or data.company.stock_code or "该公司"
        parts = [f"【Phase {phase} 分析报告】{name}"]
        parts.append(f"综合评分: {score:.1f}/100 → 投资建议: {rating}")
        parts.append("")

        # 亮点和风险
        highlights = []
        risks = []
        for ds in dim_scores:
            if ds.score >= 75:
                highlights.append(f"✅ {ds.display_name}({ds.score:.0f}分)")
            elif ds.score < 40:
                risks.append(f"⚠️ {ds.display_name}({ds.score:.0f}分)")

        if highlights:
            parts.append("亮点: " + ", ".join(highlights))
        if risks:
            parts.append("风险: " + ", ".join(risks))

        return "\n".join(parts)

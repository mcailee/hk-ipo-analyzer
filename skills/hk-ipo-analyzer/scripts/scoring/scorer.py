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
        """基于市值、认购倍数和综合评分生成卖出时机建议。"""
        timing_cfg = self.config.get("sell_timing", {})
        small_cap = timing_cfg.get("small_cap_threshold", 5000)
        large_cap = timing_cfg.get("large_cap_threshold", 30000)
        strategies = timing_cfg.get("strategies", {})

        market_cap = data.valuation.market_cap or 0
        sub_mult = data.subscription.public_subscription_mult or 0
        total_score = report.total_score

        # 决策逻辑
        if market_cap < small_cap and sub_mult >= 30:
            strat_key = "quick_flip"
            rationale = f"小市值(HK${market_cap:.0f}M) + 高认购({sub_mult:.0f}x)，适合速战速决"
            confidence = "high"
        elif market_cap < small_cap:
            strat_key = "quick_flip"
            rationale = f"小市值(HK${market_cap:.0f}M)，流动性有限，建议尽快获利了结"
            confidence = "medium"
        elif market_cap > large_cap and total_score >= 75:
            strat_key = "medium_hold"
            rationale = f"大市值(HK${market_cap:.0f}M) + 高评分({total_score:.0f})，基本面支撑中线持有"
            confidence = "high" if total_score >= 80 else "medium"
        elif market_cap > large_cap:
            strat_key = "short_hold"
            rationale = f"大市值(HK${market_cap:.0f}M)，建议短线观察后决定"
            confidence = "medium"
        elif sub_mult >= 100:
            strat_key = "quick_flip"
            rationale = f"超高认购({sub_mult:.0f}x)，首日溢价可期但后续动能衰减快"
            confidence = "high"
        elif total_score >= 70:
            strat_key = "short_hold"
            rationale = f"综合评分较高({total_score:.0f})，可适当短线持有"
            confidence = "medium"
        else:
            strat_key = "quick_flip"
            rationale = f"综合评分一般({total_score:.0f})，建议首日获利即走"
            confidence = "low"

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

"""市场情绪分析器（9%，Phase1/Phase2 均可用）。

子指标：
  1. 恒指近1月涨跌幅
  2. 近30日IPO破发率
  3. 南向资金净流入
  4. 恒指波动率
"""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from analyzers.base import BaseAnalyzer
from models.ipo_data import IPOData, DimensionScore, SubScore


class MarketSentimentAnalyzer(BaseAnalyzer):
    dimension_key = "market_sentiment"
    dimension_name = "市场情绪"

    def analyze(self, data: IPOData, config: dict) -> DimensionScore:
        weight = config["dimensions"]["market_sentiment"]["weight"]
        sent = data.market_sentiment
        scoring = config.get("sentiment_scoring", {})
        subs = []

        # 1. 恒指近1月涨跌幅
        if sent.hsi_1m_change is not None:
            s = self.score_by_range(sent.hsi_1m_change,
                                    scoring.get("hsi_1m_change", []))
            direction = "上涨" if sent.hsi_1m_change >= 0 else "下跌"
            subs.append(SubScore("恒指近1月表现", s,
                                 f"恒指近1月{direction} {abs(sent.hsi_1m_change):.1f}%",
                                 sent.hsi_1m_change))

        # 2. 近30日IPO破发率
        if sent.ipo_break_rate_30d is not None:
            s = self.score_by_range(sent.ipo_break_rate_30d,
                                    scoring.get("ipo_break_rate_30d", []))
            subs.append(SubScore("近期IPO破发率", s,
                                 f"近30日新股破发率 {sent.ipo_break_rate_30d:.0f}%",
                                 sent.ipo_break_rate_30d))

        # 3. 南向资金净流入
        if sent.southbound_net_flow is not None:
            s = self.score_by_range(sent.southbound_net_flow,
                                    scoring.get("southbound_net_flow", []))
            direction = "净流入" if sent.southbound_net_flow >= 0 else "净流出"
            subs.append(SubScore("南向资金", s,
                                 f"南向资金{direction} {abs(sent.southbound_net_flow):.1f}亿港元",
                                 sent.southbound_net_flow))

        # 4. 恒指波动率
        if sent.hsi_volatility is not None:
            s = self.score_by_range(sent.hsi_volatility,
                                    scoring.get("hsi_volatility", []))
            subs.append(SubScore("市场波动率", s,
                                 f"恒指波动率 {sent.hsi_volatility:.1f}%",
                                 sent.hsi_volatility))

        if not subs:
            return self.handle_missing(weight)

        score = self.avg_scores(subs)
        analysis = self._build_analysis(sent, score)

        return DimensionScore(
            dimension=self.dimension_key,
            display_name=self.dimension_name,
            score=self.cap_score(score),
            weight=weight,
            sub_scores=subs,
            analysis=analysis,
            data_sufficient=len(subs) >= 2,
        )

    def _build_analysis(self, sent, score):
        parts = []
        if sent.hsi_1m_change is not None:
            if sent.hsi_1m_change > 5:
                parts.append("大盘走势强劲，IPO氛围有利。")
            elif sent.hsi_1m_change > 0:
                parts.append("大盘温和上涨，IPO环境尚可。")
            elif sent.hsi_1m_change > -3:
                parts.append("大盘小幅回调，IPO环境偏弱。")
            else:
                parts.append("大盘明显下跌，IPO破发风险加大。")

        if sent.ipo_break_rate_30d is not None:
            if sent.ipo_break_rate_30d > 50:
                parts.append(f"近期破发率高达{sent.ipo_break_rate_30d:.0f}%，市场信心严重不足。")
            elif sent.ipo_break_rate_30d > 30:
                parts.append(f"近期破发率{sent.ipo_break_rate_30d:.0f}%，需谨慎。")

        if score >= 75:
            parts.append("整体市场情绪积极，打新胜率有系统性加成。")
        elif score >= 55:
            parts.append("市场情绪中性，需关注个股基本面。")
        else:
            parts.append("市场情绪低迷，建议降低打新仓位或观望。")

        return " ".join(parts)

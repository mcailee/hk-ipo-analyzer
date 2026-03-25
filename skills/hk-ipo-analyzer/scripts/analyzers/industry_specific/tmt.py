"""TMT 行业专属分析器。"""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from analyzers.industry_specific.base import IndustrySpecificAnalyzer
from models.ipo_data import IPOData, SubScore
from utils.helpers import safe_float


class TMTAnalyzer(IndustrySpecificAnalyzer):
    industry_name = "TMT"

    def analyze(self, data: IPOData) -> list[SubScore]:
        d = data.industry_specific.data if data.industry_specific else {}
        subs = []

        # Rule of 40 (营收增速% + 利润率% >= 40 为健康)
        rev_growth = data.financial.revenue_cagr
        margin = data.financial.net_margin
        if rev_growth is not None and margin is not None:
            rule40 = rev_growth + margin
            if rule40 >= 40:
                s = 90
            elif rule40 >= 25:
                s = 70
            elif rule40 >= 10:
                s = 50
            else:
                s = 25
            subs.append(SubScore("Rule of 40", s,
                                 f"增速({rev_growth:.0f}%) + 利润率({margin:.0f}%) = {rule40:.0f}",
                                 rule40))

        # MAU/DAU
        mau = safe_float(d.get("mau"))
        if mau is not None:
            if mau >= 10000:  # 千万级
                s = 90
            elif mau >= 1000:
                s = 75
            elif mau >= 100:
                s = 55
            else:
                s = 35
            subs.append(SubScore("月活用户(MAU)", s,
                                 f"MAU {mau:.0f} 万", mau))

        # ARPU
        arpu = safe_float(d.get("arpu"))
        if arpu is not None:
            if arpu >= 500:
                s = 85
            elif arpu >= 100:
                s = 70
            elif arpu >= 30:
                s = 50
            else:
                s = 35
            subs.append(SubScore("ARPU", s, f"ARPU ¥{arpu:.0f}", arpu))

        # LTV/CAC
        ltv_cac = safe_float(d.get("ltv_cac"))
        if ltv_cac is not None:
            if ltv_cac >= 5:
                s = 90
            elif ltv_cac >= 3:
                s = 75
            elif ltv_cac >= 1:
                s = 45
            else:
                s = 15
            subs.append(SubScore("LTV/CAC", s,
                                 f"LTV/CAC = {ltv_cac:.1f}x (>3为佳)", ltv_cac))

        # 经常性收入占比
        recurring = safe_float(d.get("recurring_revenue_pct"))
        if recurring is not None:
            if recurring >= 70:
                s = 90
            elif recurring >= 50:
                s = 70
            elif recurring >= 30:
                s = 50
            else:
                s = 30
            subs.append(SubScore("经常性收入占比", s,
                                 f"经常性收入占比 {recurring:.0f}%", recurring))

        # 大客户集中度
        top_client = safe_float(d.get("top_client_pct"))
        if top_client is not None:
            if top_client < 20:
                s = 85
            elif top_client < 30:
                s = 70
            elif top_client < 50:
                s = 45
            else:
                s = 20
            subs.append(SubScore("大客户集中度", s,
                                 f"前五大客户占比 {top_client:.0f}% (<30%佳)", top_client))

        return subs

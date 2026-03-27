"""消费品行业专属分析器。"""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from analyzers.industry_specific.base import IndustrySpecificAnalyzer
from models.ipo_data import IPOData, SubScore
from utils.helpers import safe_float, safe_int


class ConsumerAnalyzer(IndustrySpecificAnalyzer):
    industry_name = "消费品"

    def analyze(self, data: IPOData) -> list[SubScore]:
        d = data.industry_specific.data if data.industry_specific else {}
        subs = []

        # 同店增长
        sssg = safe_float(d.get("same_store_sales_growth"))
        if sssg is not None:
            if sssg >= 10:
                s = 90
            elif sssg >= 5:
                s = 75
            elif sssg >= 0:
                s = 55
            else:
                s = 25
            subs.append(SubScore("同店增长", s, f"同店增长 {sssg:.1f}% (>5%佳)", sssg))

        # 门店数量增速
        store_growth = safe_float(d.get("store_growth_rate"))
        if store_growth is not None:
            if store_growth >= 30:
                s = 85
            elif store_growth >= 15:
                s = 70
            elif store_growth >= 5:
                s = 55
            else:
                s = 35
            subs.append(SubScore("门店扩张", s,
                                 f"门店增速 {store_growth:.0f}%", store_growth))

        # 库存周转天数
        inv_days = safe_float(d.get("inventory_turnover_days"))
        if inv_days is not None:
            if inv_days <= 30:
                s = 85
            elif inv_days <= 60:
                s = 70
            elif inv_days <= 90:
                s = 55
            elif inv_days <= 150:
                s = 35
            else:
                s = 15
            subs.append(SubScore("库存周转", s,
                                 f"库存周转 {inv_days:.0f} 天", inv_days))

        # 毛利率水平（优先用行业专属数据，避免与 financial.py 通用毛利率重复）
        gm = safe_float(d.get("gross_margin")) or data.financial.gross_margin
        if gm is not None and d.get("gross_margin") is not None:
            # 仅当行业数据中有专属毛利率时才评分（否则由 financial.py 通用评分覆盖）
            if gm >= 60:
                s = 90
            elif gm >= 45:
                s = 75
            elif gm >= 30:
                s = 55
            else:
                s = 35
            subs.append(SubScore("毛利率水平", s, f"消费品毛利率 {gm:.1f}%", gm))

        # 渠道分布
        online_pct = safe_float(d.get("online_revenue_pct"))
        if online_pct is not None:
            # 线上线下平衡最佳
            if 30 <= online_pct <= 60:
                s = 80
            elif online_pct > 60:
                s = 65
            else:
                s = 55
            subs.append(SubScore("渠道分布", s,
                                 f"线上收入占比 {online_pct:.0f}%", online_pct))

        return subs

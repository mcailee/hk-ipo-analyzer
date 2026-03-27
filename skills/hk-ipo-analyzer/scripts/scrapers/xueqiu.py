"""雪球数据爬虫 — 获取财务数据和行业信息。"""

from __future__ import annotations

import re
from typing import Optional

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scrapers.base import BaseScraper
from models.ipo_data import IPOData, FinancialInfo, ValuationInfo
from utils.helpers import safe_float, logger


class XueqiuScraper(BaseScraper):
    """从雪球获取港股补充数据。"""

    BASE_URL = "https://xueqiu.com"
    API_URL = "https://stock.xueqiu.com"

    def __init__(self, config=None):
        super().__init__(config)
        # 先访问主页获取 cookie/token
        self._init_session()

    def _init_session(self):
        """初始化会话（获取必要的 cookie）。"""
        try:
            resp = self.session.get(self.BASE_URL, timeout=self.timeout)
            logger.info("[雪球] 会话初始化完成")
        except Exception as e:
            logger.warning(f"[雪球] 会话初始化失败: {e}")

    def scrape(self, stock_code: str, existing_data: Optional[IPOData] = None) -> IPOData:
        """获取指定港股代码的补充数据。"""
        data = existing_data or IPOData()
        hk_code = self._normalize_code(stock_code)
        logger.info(f"[雪球] 开始获取 {hk_code} ...")

        self._scrape_quote(hk_code, data)
        self._scrape_financial(hk_code, data)
        self._scrape_industry_peers(hk_code, data)

        logger.info(f"[雪球] {hk_code} 获取完成")
        return data

    def _normalize_code(self, code: str) -> str:
        """标准化为雪球港股格式（如 09999）。"""
        code = code.strip().lstrip("0")
        return code.zfill(5)

    def _scrape_quote(self, code: str, data: IPOData):
        """获取股票行情和基本信息。"""
        try:
            url = f"{self.API_URL}/v5/stock/quote.json"
            params = {"symbol": f"HK{code}", "extend": "detail"}
            result = self._get_json(url, params=params)
            if not result or "data" not in result:
                return

            quote = result["data"].get("quote", {})
            if quote:
                if not data.company.name:
                    data.company.name = quote.get("name")
                data.company.stock_code = code

                # PE / 市值等
                data.valuation.pe_ratio = safe_float(quote.get("pe_ttm"))
                # 雪球 market_capital 单位是原始港元，转为百万港元（与下游阈值一致）
                raw_cap = safe_float(quote.get("market_capital"))
                data.valuation.market_cap = raw_cap / 1_000_000 if raw_cap else None

                # 行业
                data.company.industry = quote.get("industry") or quote.get("sub_type")

        except Exception as e:
            logger.warning(f"[雪球] 获取行情异常: {e}")

    def _scrape_financial(self, code: str, data: IPOData):
        """获取财务数据。"""
        try:
            url = f"{self.API_URL}/v5/stock/finance/cn/indicator.json"
            params = {
                "symbol": f"HK{code}",
                "type": "Q4",
                "is_detail": "true",
                "count": 3,
            }
            result = self._get_json(url, params=params)
            if not result or "data" not in result:
                return

            items = result["data"].get("list", [])
            if not items:
                return

            # 最新一期
            latest = items[0]

            # 净利率：优先使用雪球接口的 net_selling_rate（销售净利率），
            # 降级方案：从净利润/营收手动计算
            net_margin = safe_float(latest.get("net_selling_rate"))
            if net_margin is None:
                net_profit = safe_float(latest.get("net_profit_atsopc"))
                revenue = safe_float(latest.get("total_revenue"))
                if net_profit is not None and revenue and revenue > 0:
                    net_margin = net_profit / revenue * 100
            data.financial.net_margin = net_margin

            data.financial.roe = safe_float(latest.get("avg_roe"))
            data.financial.gross_margin = safe_float(latest.get("gross_selling_rate"))
            data.financial.debt_ratio = safe_float(latest.get("asset_liab_ratio"))

            # 营收增速：优先 3 年数据计算真正 2 年 CAGR，
            # 降级方案：仅 2 年数据时按 YoY 计算
            rev_latest = safe_float(latest.get("total_revenue"))
            if rev_latest:
                data.financial.revenue_latest = rev_latest

            if len(items) >= 2:
                rev_prev = safe_float(items[1].get("total_revenue"))
                if rev_prev:
                    data.financial.revenue_prev = rev_prev

            if len(items) >= 3:
                rev_prev2 = safe_float(items[2].get("total_revenue"))
                if rev_prev2:
                    data.financial.revenue_prev2 = rev_prev2

            # 计算增速
            if (data.financial.revenue_latest and data.financial.revenue_prev2
                    and data.financial.revenue_prev2 > 0):
                # 3 年数据：真正的 2 年 CAGR
                data.financial.revenue_cagr = (
                    (data.financial.revenue_latest / data.financial.revenue_prev2) ** 0.5 - 1
                ) * 100
            elif (data.financial.revenue_latest and data.financial.revenue_prev
                  and data.financial.revenue_prev > 0):
                # 仅 2 年数据：YoY（字段名保持 revenue_cagr 兼容下游）
                data.financial.revenue_cagr = (
                    data.financial.revenue_latest / data.financial.revenue_prev - 1
                ) * 100

        except Exception as e:
            logger.warning(f"[雪球] 获取财务数据异常: {e}")

    def _scrape_industry_peers(self, code: str, data: IPOData):
        """获取同行估值数据。"""
        try:
            url = f"{self.API_URL}/v5/stock/screener/quote/list.json"
            industry = data.company.industry
            if not industry:
                return

            params = {
                "page": 1,
                "size": 10,
                "order": "desc",
                "order_by": "market_capital",
                "market": "HK",
                "industry": industry,
            }
            result = self._get_json(url, params=params)
            if not result or "data" not in result:
                return

            stocks = result["data"].get("list", [])
            pe_list = []
            ps_list = []
            for s in stocks:
                if s.get("symbol") == f"HK{code}":
                    continue
                pe = safe_float(s.get("pe_ttm"))
                if pe and 0 < pe < 200:
                    pe_list.append(pe)
                ps = safe_float(s.get("ps"))
                if ps and 0 < ps < 200:
                    ps_list.append(ps)

            if pe_list:
                data.valuation.peer_avg_pe = sum(pe_list) / len(pe_list)
                logger.info(f"[雪球] 同行平均 PE: {data.valuation.peer_avg_pe:.1f} ({len(pe_list)} 家)")
            if ps_list:
                data.valuation.peer_avg_ps = sum(ps_list) / len(ps_list)
                logger.info(f"[雪球] 同行平均 PS: {data.valuation.peer_avg_ps:.1f} ({len(ps_list)} 家)")

        except Exception as e:
            logger.warning(f"[雪球] 获取同行数据异常: {e}")

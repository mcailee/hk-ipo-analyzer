"""港交所披露易爬虫 — 获取 IPO 基本信息。

⚠️ WIP/STUB: 当前仅实现了基础搜索框架，数据解析不完整。
实际数据依赖雪球 API + 招股书 PDF 解析。HKEX 接口参数仍需
根据实际 API 文档校准。_parse_price_range 和 _parse_greenshoe
为预留方法，尚未接入主流程。
"""

from __future__ import annotations

import re
from typing import Optional

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scrapers.base import BaseScraper
from models.ipo_data import (
    IPOData, CompanyInfo, ValuationInfo, UnderwritingInfo,
    GreenshoeInfo, CornerstoneInfo, CornerstoneInvestor,
    ShareholderInfo, LegalInfo,
)
from utils.helpers import safe_float, safe_int, logger


class HKEXScraper(BaseScraper):
    """从港交所披露易 (HKEX) 获取 IPO 相关信息。"""

    BASE_URL = "https://www.hkexnews.hk"
    SEARCH_URL = f"{BASE_URL}/app/SEHKPostIPOApp"  # 上市后公告搜索
    IPO_SEARCH_URL = f"{BASE_URL}/app/IPOApp"       # IPO 招股相关

    def scrape(self, stock_code: str) -> IPOData:
        """爬取指定股票代码的 IPO 信息。"""
        data = IPOData()
        logger.info(f"[HKEX] 开始爬取 {stock_code} ...")

        # 获取基本信息页
        self._scrape_ipo_info(stock_code, data)
        # 获取招股文件列表
        self._scrape_prospectus_list(stock_code, data)

        logger.info(f"[HKEX] {stock_code} 爬取完成")
        return data

    def _scrape_ipo_info(self, stock_code: str, data: IPOData):
        """从港交所获取 IPO 基本信息。"""
        try:
            # 尝试搜索公司 IPO 信息
            search_url = f"{self.BASE_URL}/listedco/listconews/advancedsearchEHTC.htm"
            params = {"StockCode": stock_code, "DocType": "IPO"}
            soup = self._get_soup(search_url, params=params)
            if soup is None:
                logger.warning(f"[HKEX] 无法获取 {stock_code} 的 IPO 信息页")
                return

            # 解析公司名
            title_tag = soup.find("td", string=re.compile(r"Company Name|公司名称", re.I))
            if title_tag:
                name_td = title_tag.find_next_sibling("td")
                if name_td:
                    data.company.name = name_td.get_text(strip=True)

            # 解析上市日期
            date_tag = soup.find("td", string=re.compile(r"Listing Date|上市日期", re.I))
            if date_tag:
                date_td = date_tag.find_next_sibling("td")
                if date_td:
                    data.underwriting.listing_date = date_td.get_text(strip=True)

        except Exception as e:
            logger.warning(f"[HKEX] 解析 IPO 信息异常: {e}")

    def _scrape_prospectus_list(self, stock_code: str, data: IPOData):
        """获取招股文件列表（招股章程等）。"""
        try:
            url = f"{self.BASE_URL}/listedco/listconews/advancedsearchEHTC.htm"
            params = {
                "StockCode": stock_code,
                "DocType": "Prospectus",
            }
            soup = self._get_soup(url, params=params)
            if soup is None:
                return

            # 提取文件链接
            links = soup.find_all("a", href=re.compile(r"\.pdf$", re.I))
            if links:
                logger.info(f"[HKEX] 找到 {len(links)} 个招股相关文件")

        except Exception as e:
            logger.warning(f"[HKEX] 获取招股文件列表异常: {e}")

    def _parse_price_range(self, text: str, data: IPOData):
        """解析招股价区间。"""
        # 匹配 "HK$X.XX to HK$X.XX" 或 "X.XX港元至X.XX港元"
        patterns = [
            r'HK\$\s*(\d+\.?\d*)\s*(?:to|至|-)\s*HK\$\s*(\d+\.?\d*)',
            r'(\d+\.?\d*)\s*港元\s*(?:至|-)\s*(\d+\.?\d*)\s*港元',
        ]
        for pat in patterns:
            m = re.search(pat, text, re.I)
            if m:
                data.valuation.offer_price_low = safe_float(m.group(1))
                data.valuation.offer_price_high = safe_float(m.group(2))
                return

    def _parse_greenshoe(self, text: str, data: IPOData):
        """解析绿鞋机制信息。"""
        if re.search(r"超额配售|over[- ]?allotment|greenshoe|绿鞋", text, re.I):
            data.greenshoe.has_greenshoe = True
            # 尝试提取比例
            m = re.search(r'(\d+\.?\d*)\s*%', text)
            if m:
                data.greenshoe.overallotment_ratio = safe_float(m.group(1))
        else:
            data.greenshoe.has_greenshoe = False

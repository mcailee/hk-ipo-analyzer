"""爬虫基类，封装通用请求逻辑。"""

from __future__ import annotations

import random
import time
from abc import ABC, abstractmethod
from typing import Optional

import requests
from bs4 import BeautifulSoup

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from utils.helpers import get_config, logger


class BaseScraper(ABC):
    """爬虫抽象基类。"""

    def __init__(self, config: Optional[dict] = None):
        self.config = config or get_config()
        scraper_cfg = self.config.get("scraper", {})
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": scraper_cfg.get("user_agent", "Mozilla/5.0"),
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        })
        self.timeout = scraper_cfg.get("timeout", 30)
        self.min_delay = scraper_cfg.get("min_delay", 1.0)
        self.max_delay = scraper_cfg.get("max_delay", 2.0)

    def _delay(self):
        """随机延迟防反爬。"""
        time.sleep(random.uniform(self.min_delay, self.max_delay))

    def _get(self, url: str, params: Optional[dict] = None, **kwargs) -> Optional[requests.Response]:
        """通用 GET 请求。"""
        try:
            self._delay()
            resp = self.session.get(url, params=params, timeout=self.timeout, **kwargs)
            resp.raise_for_status()
            return resp
        except requests.RequestException as e:
            logger.warning(f"请求失败 [{url}]: {e}")
            return None

    def _get_soup(self, url: str, params: Optional[dict] = None, encoding: str = "utf-8") -> Optional[BeautifulSoup]:
        """GET 请求并返回 BeautifulSoup 对象。"""
        resp = self._get(url, params=params)
        if resp is None:
            return None
        resp.encoding = encoding
        return BeautifulSoup(resp.text, "html.parser")

    def _get_json(self, url: str, params: Optional[dict] = None) -> Optional[dict]:
        """GET 请求并返回 JSON。"""
        resp = self._get(url, params=params)
        if resp is None:
            return None
        try:
            return resp.json()
        except ValueError:
            logger.warning(f"JSON 解析失败: {url}")
            return None

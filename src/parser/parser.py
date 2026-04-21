import os
import re
import time
import tomllib
import logging
import queue
from datetime import datetime
from typing import Any, Dict

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains

from src.parser.enums import Currency
from src.parser.database import DatabaseManager
from src.parser.db_worker import DBWorker
from src.parser.config import settings
from src.parser.models import Item


class CSFloatParser:
    """
    Selenium-based parser for CSFloat market data.

    Responsibilities:
    - Login and navigation
    - Item search & filtering
    - Parsing sales table
    - Sending data to DB worker queue
    """

    def __init__(self) -> None:
        profile_path = os.path.abspath("chrome_profile")
        self._is_first_run_profile = (not os.path.isdir(profile_path)) or (
            os.path.isdir(profile_path) and not os.listdir(profile_path)
        )

        self._load_config()
        self._setup_logger()

        self.currency = Currency(self.config.get("currency", "USD").upper())

        self.chrome_options = webdriver.ChromeOptions()
        self.chrome_options.add_experimental_option(
            "excludeSwitches", ["enable-automation", "enable-logging"]
        )
        self.chrome_options.add_argument(f"--user-data-dir={profile_path}")

        self.browser = webdriver.Chrome(options=self.chrome_options)

        self.queue: queue.Queue = queue.Queue(maxsize=1000)

        self.db = DatabaseManager(
            connection_string=settings.DATABASE_URL,
            echo=settings.DB_ECHO,
        )
        self.db.create_tables()

        self.worker = DBWorker(self.db, self.queue, batch_size=50)
        self.worker.start()

    def __enter__(self) -> "CSFloatParser":
        self.browser.maximize_window()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.logger.info("Waiting for queue to be processed...")

        self.queue.join()

        self.logger.info("Stopping DB worker...")
        self.worker.stop()
        self.worker.join()

        self.browser.quit()

    def _load_config(self) -> None:
        with open("config.toml", "rb") as file:
            self.config = tomllib.load(file)

    def _setup_logger(self):
        log_dir = self.config.get("logging", {}).get("dir", "logs")
        log_level = self.config.get("logging", {}).get("level", "INFO").upper()

        os.makedirs(log_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        log_file = os.path.join(log_dir, f"CSFloat_sales_parser_{timestamp}.log")

        logging.getLogger("selenium").setLevel(logging.WARNING)
        logging.getLogger("selenium.webdriver").setLevel(logging.WARNING)
        logging.getLogger("selenium.webdriver.common.selenium_manager").setLevel(
            logging.WARNING
        )
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        logging.getLogger("WDM").setLevel(logging.WARNING)

        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, log_level))

        if root_logger.hasHandlers():
            root_logger.handlers.clear()

        formatter = logging.Formatter(
            "%(asctime)s [%(name)s] %(levelname)s %(message)s", "%Y-%m-%d %H:%M:%S"
        )

        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)

        root_logger.addHandler(file_handler)
        root_logger.addHandler(console_handler)

        self.logger = logging.getLogger("parser")

        self.logger.info(f"Logger initialized. Log file: {log_file}")

    def login(self) -> None:
        self.browser.get("https://csfloat.com/")

        if self._is_first_run_profile:
            self.logger.warning(
                "Chrome profile is missing/empty (first run). "
                "Please authorize manually in the opened browser window. "
                "Waiting up to 600 seconds for the UI to become available..."
            )
            time.sleep(600)

        current_currency_elem = WebDriverWait(self.browser, 10).until(
            EC.visibility_of_element_located((By.ID, "mat-select-value-0"))
        )

        current_currency = current_currency_elem.text

        if current_currency != self.currency.value:
            self.change_currency()

    def change_currency(self) -> None:
        currency_elem = self.browser.find_element(By.ID, "mat-select-value-0")
        currency_elem.click()

        WebDriverWait(self.browser, timeout=10).until(
            EC.presence_of_element_located((By.ID, "mat-option-1"))
        )

        self.browser.find_element(
            By.XPATH,
            f"//mat-option[starts-with(normalize-space(), '{self.currency.value}')]",
        ).click()

        self.browser.refresh()

    def start(self) -> None:
        self._open_market()

        for item in self.config["items"]:
            try:
                self._process_item(item)
            except Exception as e:
                self.logger.error(
                    f"Error processing {item['name']}: {e}",
                    exc_info=True,
                )

    def _open_market(self) -> None:
        market_elem = WebDriverWait(self.browser, 10).until(
            EC.visibility_of_element_located(
                (By.XPATH, "//span[@class='mdc-button__label' and text()='Market']")
            )
        )
        market_elem.click()

    def _process_item(self, item: Dict[str, Any]) -> None:
        try:
            hash_name = item["name"]
            skin_name = self._normalize_name(hash_name)

            self.logger.info(f"Processing item: {skin_name} [{hash_name}]")

            self._search_item(skin_name)
            self._apply_filters(hash_name)

            if self._is_no_items():
                self.logger.error(f"No items found: {hash_name}")
                return

            self._open_first_item()
            self._open_latest_sales()

            if self._is_no_sales():
                self.logger.warning(f"No sales for: {hash_name}")
                return

            self._parse_sales(hash_name)

        finally:
            self._reset_to_search()

    def _normalize_name(self, hash_name: str) -> str:
        name = re.sub(r"^(StatTrak™|Souvenir)\s+", "", hash_name)
        name = re.sub(r"\s*\([^)]+\)$", "", name)
        return name

    def _search_item(self, skin_name: str) -> None:
        search_elem = WebDriverWait(self.browser, 10).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, "div.round-square"))
        )
        search_elem.click()

        search_bar = WebDriverWait(self.browser, 10).until(
            EC.visibility_of_element_located((By.ID, "spotlight-overlay-input"))
        )

        search_bar.send_keys(skin_name)

        results = WebDriverWait(self.browser, 10).until(
            EC.visibility_of_all_elements_located(
                (By.CSS_SELECTOR, ".mat-ripple.result-row.item-result.ng-star-inserted")
            )
        )

        if not results:
            raise ValueError(f"No search results for: {skin_name}")

        results[0].click()
        search_bar.send_keys(Keys.ENTER)

    def _apply_filters(self, hash_name: str) -> None:
        self._apply_wear_filter(hash_name)
        time.sleep(0.5)
        self._apply_type_filter(hash_name)
        time.sleep(5)

    def _apply_wear_filter(self, hash_name):
        wear_map = {
            "(Factory New)": "FN",
            "(Minimal Wear)": "MW",
            "(Field-Tested)": "FT",
            "(Well-Worn)": "WW",
            "(Battle-Scarred)": "BS",
        }

        wear_parent = WebDriverWait(self.browser, 10).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, ".wear .btn-select"))
        )

        for key, value in wear_map.items():
            if hash_name.endswith(key):
                elem = wear_parent.find_element(
                    By.XPATH,
                    f".//div[contains(@class, 'bubble') and normalize-space()='{value}']",
                )
                elem.click()
                return

    def _apply_type_filter(self, hash_name):
        if hash_name.startswith("StatTrak"):
            self.browser.find_element(By.ID, "mat-mdc-checkbox-0-input").click()
        elif hash_name.startswith("Souvenir"):
            self.browser.find_element(By.ID, "mat-mdc-checkbox-1-input").click()
        else:
            self.browser.find_element(By.ID, "mat-mdc-checkbox-3-input").click()

    def _is_no_items(self):
        return bool(
            self.browser.find_elements(By.XPATH, "//span[text()='Found No Items']")
        )

    def _is_no_sales(self):
        return bool(
            self.browser.find_elements(
                By.XPATH, "//item-latest-sales//span[text()='Found No Sales']"
            )
        )

    def _open_first_item(self):
        items = WebDriverWait(self.browser, 10).until(
            EC.presence_of_all_elements_located((By.TAG_NAME, "item-card"))
        )
        self.logger.info(f"Found {len(items)} items")
        items[0].click()

    def _open_latest_sales(self):
        latest_sales_elem = WebDriverWait(self.browser, 10).until(
            EC.element_to_be_clickable(
                (By.XPATH, "//mat-button-toggle//span[text()='Latest Sales']")
            )
        )
        latest_sales_elem.click()

    def _parse_sales(self, hash_name: str) -> None:
        rows = WebDriverWait(self.browser, 10).until(
            EC.presence_of_all_elements_located(
                (By.CSS_SELECTOR, "item-latest-sales table tbody tr")
            )
        )

        self.logger.info(f"Found {len(rows)} sales")

        for row in rows:
            sale_data = self._parse_single_sale(row)

            if self._is_duplicate(hash_name, sale_data):
                self.logger.info(f"Duplicate detected, stop parsing {hash_name}")
                break

            try:
                self.queue.put((hash_name, sale_data), timeout=10)
            except queue.Full:
                self.logger.warning("Queue is full, skipping sale")

    def _parse_single_sale(self, row) -> Dict[str, Any]:
        return {
            "price": self._parse_price(row),
            "base_data": self._parse_reference_tooltip(row),
            "datetime": self._parse_datetime(row),
            "float": self._parse_float(row),
            "seed": self._parse_seed(row),
            "stickers": self._parse_stickers_block(row),
            "badge": self._parse_badge_block(row),
        }

    def _reset_to_search(self) -> None:
        self.browser.get("https://csfloat.com/search")

    def _get_last_tooltip(self, timeout: int = 5):
        tooltips = WebDriverWait(self.browser, timeout).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".cdk-overlay-pane"))
        )
        return tooltips[-1]

    def _parse_price(self, sale_elem):
        try:
            price_elem = sale_elem.find_element(
                By.CSS_SELECTOR, "td[data-column-name='Price'] div.price"
            )
            price_text = price_elem.text.replace(",", "")
            price = re.sub(r"[^\d.]", "", price_text)
            return float(price)
        except Exception as e:
            self.logger.error(f"Error parsing price: {e}", exc_info=True)
            return None

    def _parse_reference_tooltip(self, sale_elem):
        try:
            icon_elem = sale_elem.find_element(By.CSS_SELECTOR, ".reference")
            ActionChains(self.browser).move_to_element(icon_elem).perform()

            tooltip = self._get_last_tooltip()

            rows = tooltip.find_elements(By.CSS_SELECTOR, ".row")
            data = {}

            for row in rows:
                label = row.find_element(By.CSS_SELECTOR, ".label").text.strip()
                value = row.find_element(By.CSS_SELECTOR, ".price").text.strip()
                data[label] = value

            result = {}

            if "Base Price:" in data:
                val = data["Base Price:"].replace(",", "")
                result["base_price"] = float(
                    "".join(c for c in val if c.isdigit() or c == ".")
                )

            if "Global Listings:" in data:
                val = data["Global Listings:"].replace(",", "").lstrip(">")
                result["global_listings"] = int(val)

            return result

        except Exception as e:
            self.logger.error(f"Error parsing tooltip: {e}", exc_info=True)
            return {}

    def _parse_datetime(self, sale_elem):
        try:
            sold_elem = sale_elem.find_element(
                By.CSS_SELECTOR, "td[data-column-name='Sold'] span"
            )

            ActionChains(self.browser).move_to_element(sold_elem).perform()

            tooltip = WebDriverWait(self.browser, 5).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, ".mat-mdc-tooltip"))
            )

            return datetime.strptime(tooltip.text, "%b %d, %Y, %I:%M:%S %p")

        except Exception as e:
            self.logger.error(f"Error parsing datetime: {e}", exc_info=True)
            return None

    def _parse_float(self, sale_elem):
        try:
            elem = sale_elem.find_element(
                By.CSS_SELECTOR, "td[data-column-name='Float Value'] span"
            )
            return float(elem.text.strip().split()[0])
        except Exception as e:
            self.logger.error(f"Error parsing float: {e}", exc_info=True)
            return None

    def _parse_seed(self, sale_elem):
        try:
            elem = sale_elem.find_element(
                By.CSS_SELECTOR, "td[data-column-name='Paint Seed'] span"
            )
            return int(elem.text.strip().split()[0])
        except Exception as e:
            self.logger.error(f"Error parsing paint_seed: {e}", exc_info=True)
            return None

    def _parse_stickers_block(self, sale_elem):
        try:
            container = sale_elem.find_element(
                By.CSS_SELECTOR, "td[data-column-name='Stickers'] app-sticker-view"
            )

            result = []

            for sticker in container.find_elements(By.CSS_SELECTOR, ".sticker"):
                ActionChains(self.browser).move_to_element(sticker).perform()
                tooltip = self._get_last_tooltip()

                parsed = self.parse_stickers(tooltip.text)
                result.append(parsed)

            return result

        except Exception as e:
            self.logger.error(f"Error parsing stickers_block: {e}", exc_info=True)
            return []

    def _parse_badge_block(self, sale_elem):
        try:
            badge_blocks = sale_elem.find_elements(
                By.CSS_SELECTOR, "td[data-column-name=''] app-item-badge"
            )

            if not badge_blocks:
                return None

            badge_block = badge_blocks[0]

            badge_data = {"type": None, "percent": None}

            tier_elems = badge_block.find_elements(By.CSS_SELECTOR, "img")
            if tier_elems:
                ActionChains(self.browser).move_to_element(tier_elems[0]).perform()
                tooltip = self._get_last_tooltip()
                badge_data["type"] = tooltip.text.strip()

            percent_elems = badge_block.find_elements(By.CSS_SELECTOR, ".badge")
            if percent_elems:
                ActionChains(self.browser).move_to_element(percent_elems[0]).perform()
                tooltip = self._get_last_tooltip()
                badge_data["percent"] = tooltip.text.strip()

            return self.parse_badge(badge_data["percent"], badge_data["type"])

        except Exception as e:
            self.logger.error(f"Error parsing badge_block: {e}", exc_info=True)
            return None

    def _is_duplicate(self, hash_name: str, sale_data: dict) -> bool:
        with self.db.get_session() as session:
            item = session.query(Item).filter_by(name=hash_name).first()

            if not item:
                return False

            return self.db.sale_exists(
                session,
                item.id,
                sale_data["datetime"],
                sale_data["price"],
                sale_data["seed"],
            )

    @staticmethod
    def parse_stickers(full_text):
        result = {
            "name": None,
            "wear": None,
            "slot": None,
            "x": None,
            "y": None,
            "rotation": None,
            "reference_price": None,
            "global_listings": None,
        }

        lines = [line.strip() for line in full_text.split("\n") if line.strip()]

        if not lines:
            return result

        result["name"] = lines[0]

        for line in lines[1:]:
            if "Wear" in line:
                match = re.search(r"([\d\.]+)%", line)
                if match:
                    result["wear"] = float(match.group(1))

            elif "Slot" in line:
                match = re.search(r"Slot\s+(\d+)", line)
                if match:
                    result["slot"] = int(match.group(1))

            elif "X:" in line:
                x_match = re.search(r"X:\s*([-\d\.]+)", line)
                y_match = re.search(r"Y:\s*([-\d\.]+)", line)
                r_match = re.search(r"R:\s*([-\d\.]+)", line)

                if x_match:
                    result["x"] = float(x_match.group(1))
                if y_match:
                    result["y"] = float(y_match.group(1))
                if r_match:
                    result["rotation"] = float(r_match.group(1))

            elif "Reference Price" in line:
                match = re.search(r"[\$¥€]\s?([\d,\.]+)", line)
                if match:
                    result["reference_price"] = float(match.group(1).replace(",", ""))

            elif "Global Listings" in line:
                match = re.search(r"(\d+)", line)
                if match:
                    result["global_listings"] = int(match.group(1))

        return result

    @staticmethod
    def parse_badge(percent_text: str, badge_type: str | None):
        if not percent_text:
            return None

        percent_text = percent_text.strip()

        result = {"pattern_type": badge_type, "data": {}}

        if "Fade:" in percent_text:

            fade_match = re.search(r"Fade:\s*([\d.]+)%", percent_text)
            rank_match = re.search(r"Rank\s*#(\d+)", percent_text)

            if fade_match:
                result["data"]["fade_percent"] = float(fade_match.group(1))

            if rank_match:
                result["data"]["rank"] = int(rank_match.group(1))

            return result

        elif "Blue:" in percent_text:

            parts = percent_text.split("\n")

            if len(parts) >= 2:
                zones = parts[0].strip()
                blue_line = parts[1].strip()

                result["data"]["zones"] = zones

                blue_match = re.search(r"Blue:\s*([\d.]+)%\s*/\s*([\d.]+)%", blue_line)
                if blue_match:
                    result["data"]["blue_top"] = float(blue_match.group(1))
                    result["data"]["blue_magazine"] = float(blue_match.group(2))

            return result

        result["data"]["raw"] = percent_text

        return result

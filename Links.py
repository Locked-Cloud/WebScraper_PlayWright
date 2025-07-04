import time
import random
import csv
import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, WebDriverException
import requests
from urllib.parse import urljoin, urlparse
import re
from datetime import datetime
import logging
import sys
from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext, Playwright
import asyncio
from typing import Optional, Tuple, List, Dict, Set, Union, Any
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement

# --- Configuration ---
CATEGORIES = [
    "https://chefaa.com/eg-ar/now/category/sexual-welness"
]

CHECKPOINT_FILE = "multi_category_scraping_checkpoint.json"
MAX_WORKERS = 3  # Number of parallel browsers
BATCH_SIZE = 3   # Pages per batch (reduced for stability)
REQUEST_DELAY = (2, 4)  # Random delay range
SMART_RETRY_DELAY = (10, 20)
MAX_RETRIES = 3  # Maximum retries per page

# Browser automation options
AUTOMATION_METHODS = ['playwright', 'undetected-chromedriver']

# Setup logging with UTF-8 encoding
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scraper.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class BrowserAutomation:
    """Base class for browser automation"""
    def __init__(self):
        self.driver: Optional[Union[WebDriver, Page]] = None
        
    def create_driver(self) -> bool:
        raise NotImplementedError
        
    def quit(self) -> None:
        raise NotImplementedError
        
    def get_page(self, url: str) -> bool:
        raise NotImplementedError
        
    def find_elements(self, selector: str) -> List[Union[WebElement, Any]]:
        raise NotImplementedError
        
    def get_attribute(self, element: Union[WebElement, Any], attribute: str) -> str:
        raise NotImplementedError

    def scroll_to_bottom(self) -> None:
        raise NotImplementedError

class PlaywrightAutomation(BrowserAutomation):
    """Playwright implementation"""
    def __init__(self):
        super().__init__()
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        
    def create_driver(self) -> bool:
        try:
            self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.launch(
                headless=True,
                args=[
                    '--disable-gpu',
                    '--disable-dev-shm-usage',
                    '--disable-setuid-sandbox',
                    '--no-sandbox',
                ]
            )
            self.context = self.browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36'
            )
            self.page = self.context.new_page()
            self.driver = self.page
            return True
        except Exception as e:
            logger.error(f"Failed to create Playwright driver: {e}")
            return False
            
    def quit(self) -> None:
        try:
            if self.page:
                self.page.close()
            if self.context:
                self.context.close()
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
        except Exception as e:
            logger.warning(f"Playwright cleanup warning: {e}")
            
    def get_page(self, url: str) -> bool:
        try:
            if self.page:
                self.page.goto(url, wait_until='networkidle')
                return True
            return False
        except Exception as e:
            logger.error(f"Playwright navigation error: {e}")
            return False
            
    def find_elements(self, selector: str) -> List[Any]:
        try:
            if self.page:
                return self.page.query_selector_all(selector)
            return []
        except Exception:
            return []
            
    def get_attribute(self, element: Any, attribute: str) -> str:
        try:
            if attribute == 'textContent':
                return element.text_content() or ""
            return element.get_attribute(attribute) or ""
        except Exception:
            return ""

    def scroll_to_bottom(self) -> None:
        if self.page:
            self.page.evaluate("window.scrollTo(0, document.body.scrollHeight);")

class UndetectedChromeAutomation(BrowserAutomation):
    """Undetected ChromeDriver implementation"""
    def __init__(self):
        super().__init__()
        self.driver: Optional[WebDriver] = None
        
    def create_driver(self) -> bool:
        try:
            options = uc.ChromeOptions()
            options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('--disable-images')
            options.add_argument('--disable-plugins')
            options.add_argument('--disable-extensions')
            
            self.driver = uc.Chrome(options=options, version_main=137)
            self.driver.set_page_load_timeout(30)
            self.driver.implicitly_wait(10)
            return True
        except Exception as e:
            logger.error(f"Failed to create Undetected Chrome driver: {e}")
            return False
            
    def quit(self) -> None:
        try:
            if self.driver:
                self.driver.quit()
        except Exception as e:
            logger.warning(f"Undetected Chrome cleanup warning: {e}")
            
    def get_page(self, url: str) -> bool:
        try:
            if self.driver:
                self.driver.get(url)
                return True
            return False
        except Exception as e:
            logger.error(f"Undetected Chrome navigation error: {e}")
            return False
            
    def find_elements(self, selector: str) -> List[WebElement]:
        try:
            if self.driver:
                return self.driver.find_elements(By.CSS_SELECTOR, selector)
            return []
        except Exception:
            return []
            
    def get_attribute(self, element: WebElement, attribute: str) -> str:
        try:
            if attribute == 'textContent':
                return element.text.strip()
            return element.get_attribute(attribute) or ""
        except Exception:
            return ""

    def scroll_to_bottom(self) -> None:
        if self.driver:
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

class EnhancedPharmacyScraper:
    def __init__(self):
        self.product_links: Dict[str, Set[str]] = {}
        self.broken_links: Dict[str, Set[str]] = {}  # Track broken links by category
        self.category_stats: Dict[str, Dict] = {}
        self.failed_categories: Set[str] = set()
        self.session = requests.Session()
        self.setup_session()
        self.lock = threading.Lock()
        self.global_stats = {
            'total_products': 0,
            'total_categories': len(CATEGORIES),
            'processed_categories': 0,
            'broken_links': 0,
            'start_time': None,
            'end_time': None
        }
        self.current_automation_method = 0
        
    def get_browser_automation(self) -> Optional[BrowserAutomation]:
        """Get browser automation instance with fallback support"""
        for _ in range(len(AUTOMATION_METHODS)):
            method = AUTOMATION_METHODS[self.current_automation_method]
            automation = None
            
            try:
                if method == 'playwright':
                    automation = PlaywrightAutomation()
                elif method == 'undetected-chromedriver':
                    automation = UndetectedChromeAutomation()
                
                if automation and automation.create_driver():
                    logger.info(f"Using {method} for browser automation")
                    return automation
                    
            except Exception as e:
                logger.warning(f"Failed to initialize {method}: {e}")
                
            # Try next method
            self.current_automation_method = (self.current_automation_method + 1) % len(AUTOMATION_METHODS)
            
        logger.error("All browser automation methods failed")
        return None

    def setup_session(self):
        """Setup requests session with proper headers"""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ar,en-US;q=0.7,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        self.session.headers.update(headers)

    def validate_url(self, url: str) -> bool:
        """Validate if URL is accessible"""
        try:
            response = self.session.head(url, timeout=10, allow_redirects=True)
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"URL validation failed for {url}: {e}")
            return False

    def check_page_exists(self, automation: BrowserAutomation) -> bool:
        """Check if current page exists and has products"""
        try:
            # Check for 404 indicators
            error_selectors = [
                ".error-404",
                ".page-not-found",
                "[class*='404']",
                "text/404",
                ".empty-results"
            ]
            
            for selector in error_selectors:
                if automation.find_elements(selector):
                    return False
            
            # Check if page has any products
            product_selectors = [
                ".product-item",
                ".item",
                "[class*='product']",
                ".product-card"
            ]
            
            for selector in product_selectors:
                if automation.find_elements(selector):
                    return True
            
            return False
        except Exception as e:
            logger.error(f"Error checking page existence: {e}")
            return False

    def get_category_name(self, url: str) -> str:
        """Extract category name from URL"""
        return url.split('/')[-1] if url.endswith('/') else url.split('/')[-1]

    def detect_category_pages(self, category_url: str) -> int:
        """Detect total pages for a specific category"""
        logger.info(f"Detecting pages for category: {self.get_category_name(category_url)}")
        
        automation = self.get_browser_automation()
        if not automation:
            return 0
            
        try:
            methods = [
                lambda: self._detect_pages_pagination(automation, category_url),
                lambda: self._detect_pages_progressive_search(automation, category_url),
                lambda: self._detect_pages_binary_search(automation, category_url, 1, 50),
                lambda: self._detect_pages_scroll_method(automation, category_url)
            ]
            
            for i, method in enumerate(methods):
                try:
                    pages = method()
                    if pages > 0:
                        # Validate the last page
                        url = f"{category_url}?page={pages}"
                        if automation.get_page(url) and self.check_page_exists(automation):
                            logger.info(f"Found {pages} valid pages using method {i+1}")
                            return pages
                        else:
                            logger.warning(f"Last page {pages} is invalid, retrying with next method")
                except Exception as e:
                    logger.warning(f"Method {i+1} failed: {e}")
                    continue
            
            # If all methods failed, try sequential search
            return self._sequential_page_search(automation, category_url)
            
        finally:
            automation.quit()

    def _sequential_page_search(self, automation: BrowserAutomation, category_url: str) -> int:
        """Search pages sequentially until finding an invalid page"""
        page = 1
        last_valid_page = 0
        consecutive_invalid = 0
        
        while consecutive_invalid < 2 and page <= 50:  # Cap at 50 pages
            url = f"{category_url}?page={page}"
            if not automation.get_page(url):
                consecutive_invalid += 1
                continue
                
            if self.check_page_exists(automation):
                last_valid_page = page
                consecutive_invalid = 0
            else:
                consecutive_invalid += 1
                
            page += 1
            time.sleep(2)  # Small delay between checks
        
        return last_valid_page

    def _detect_pages_pagination(self, automation: BrowserAutomation, category_url: str) -> int:
        """Detect pages from pagination elements"""
        url = f"{category_url}?sort=name&order=desc&limit=28"
        if not automation.get_page(url):
            return 0
            
        time.sleep(5)
        
        pagination_selectors = [
            ".pagination a", ".pagination span", ".pagination li a",
            ".pager a", "[class*='pagination'] a", ".page-numbers a",
            ".nav-links a", "[class*='page'] a", ".pagination-link",
            "[data-page]", ".page-item a", ".paginate_button"
        ]
        
        max_page = 0
        for selector in pagination_selectors:
            elements = automation.find_elements(selector)
            for element in elements:
                href = automation.get_attribute(element, 'href')
                if href and 'page=' in href:
                    page_match = re.search(r'page=(\d+)', href)
                    if page_match:
                        max_page = max(max_page, int(page_match.group(1)))
                        
                text = automation.get_attribute(element, 'textContent')
                if text and text.strip().isdigit():
                    max_page = max(max_page, int(text.strip()))
                    
                data_page = automation.get_attribute(element, 'data-page')
                if data_page and data_page.isdigit():
                    max_page = max(max_page, int(data_page))
                    
        return max_page

    def _detect_pages_scroll_method(self, automation: BrowserAutomation, category_url: str) -> int:
        """New method: Try to detect infinite scroll or load more functionality"""
        url = f"{category_url}?sort=name&order=desc&limit=28"
        if not automation.get_page(url):
            return 0
            
        time.sleep(5)
        
        # Check for infinite scroll indicators
        scroll_indicators = [
            "[class*='load-more']", "[class*='infinite']", 
            "[data-infinite]", ".load-more-btn"
        ]
        
        for selector in scroll_indicators:
            if automation.find_elements(selector):
                # If infinite scroll detected, estimate pages differently
                return self._estimate_infinite_scroll_pages(automation, category_url)
        
        return 0

    def _estimate_infinite_scroll_pages(self, automation: BrowserAutomation, category_url: str) -> int:
        """Estimate pages for infinite scroll sites"""
        try:
            initial_products = len(automation.find_elements(".item"))
            
            # Scroll and count a few times
            for _ in range(3):
                automation.scroll_to_bottom()
                time.sleep(3)
            
            final_products = len(automation.find_elements(".item"))
            
            # Rough estimation: if more products loaded, assume ~28 per page
            if final_products > initial_products:
                estimated_pages = max(10, final_products // 28)
                return min(estimated_pages, 50)  # Cap at 50 pages
                
        except Exception as e:
            logger.warning(f"Infinite scroll estimation failed: {e}")
        
        return 0

    def _detect_pages_progressive_search(self, automation: BrowserAutomation, category_url: str) -> int:
        """Progressive search to find last page with improved ranges"""
        test_pages = [100, 75, 50, 30, 20, 15, 10, 8, 6, 4, 3, 2]
        
        for test_page in test_pages:
            url = f"{category_url}?sort=name&order=desc&limit=28&page={test_page}"
            if not automation.get_page(url):
                continue
            
            products = automation.find_elements(".item")
            if len(products) > 0:
                # Found products, search more precisely
                return self._precise_search_pages(automation, category_url, test_page)
        
        return 1  # At least one page exists

    def _precise_search_pages(self, automation: BrowserAutomation, category_url: str, start_page: int) -> int:
        """More precise search around known valid page"""
        current_page = start_page
        consecutive_empty = 0
        
        while current_page <= start_page + 20 and consecutive_empty < 3:
            url = f"{category_url}?sort=name&order=desc&limit=28&page={current_page}"
            if not automation.get_page(url):
                continue
            
            products = automation.find_elements(".item")
            if len(products) == 0:
                consecutive_empty += 1
                if consecutive_empty >= 3:
                    return max(1, current_page - consecutive_empty)
            else:
                consecutive_empty = 0
                
            current_page += 1
        
        return current_page - 1

    def _detect_pages_binary_search(self, automation: BrowserAutomation, category_url: str, min_page: int, max_page: int) -> int:
        """Binary search to find exact last page"""
        original_max = max_page
        
        while min_page <= max_page:
            mid = (min_page + max_page) // 2
            url = f"{category_url}?sort=name&order=desc&limit=28&page={mid}"
            if not automation.get_page(url):
                continue
            
            products = automation.find_elements(".item")
            
            if products:
                min_page = mid + 1
            else:
                max_page = mid - 1
        
        # Validate result is reasonable
        result = max_page
        if result > original_max or result < 1:
            return min(10, original_max)
        
        return result

    def validate_product_link(self, url: str) -> bool:
        """Validate if product URL is accessible and returns a valid product page"""
        try:
            response = self.session.get(url, timeout=10, allow_redirects=True)
            if response.status_code != 200:
                return False
                
            # Check if response contains 404 indicators
            error_indicators = [
                'page-not-found',
                'error-404',
                'product-not-found',
                'no-longer-available'
            ]
            
            response_text = response.text.lower()
            return not any(indicator in response_text for indicator in error_indicators)
            
        except Exception as e:
            logger.warning(f"Product URL validation failed for {url}: {e}")
            return False

    def extract_category_links(self, category_url: str, page_num: int) -> Tuple[List[str], bool]:
        """Extract product links from a specific category page"""
        automation = self.get_browser_automation()
        if not automation:
            return [], False
            
        try:
            url = f"{category_url}?page={page_num}"
            logger.info(f"Loading URL: {url}")
            
            if not automation.get_page(url):
                return [], False
                
            # Check if page exists and has products
            if not self.check_page_exists(automation):
                logger.warning(f"Page {page_num} appears to be invalid or empty")
                return [], False
                
            time.sleep(8)
            
            # Find all product items with more specific selectors
            selectors = [
                ".product-item a[href*='nowProduct']",
                ".item a[href*='nowProduct']",
                "[class*='product'] a[href*='nowProduct']",
                "a.product_details_link",
                ".product-card a[href*='nowProduct']",
                ".product-list a[href*='nowProduct']",
                ".product a[href*='nowProduct']"
            ]
            
            links = []
            working_links = []
            category_name = self.get_category_name(category_url)
            
            for selector in selectors:
                items = automation.find_elements(selector)
                logger.info(f"Found {len(items)} product items with selector '{selector}' on page {page_num}")
                
                for item in items:
                    try:
                        link = automation.get_attribute(item, 'href')
                        if link and 'nowProduct' in link:
                            links.append(link)
                    except Exception as e:
                        logger.debug(f"Failed to extract link from item: {e}")
                        continue
                
                if links:
                    # Validate each link before adding
                    for link in links:
                        if self.validate_product_link(link):
                            working_links.append(link)
                        else:
                            logger.warning(f"Found broken product link: {link}")
                            with self.lock:
                                if category_name not in self.broken_links:
                                    self.broken_links[category_name] = set()
                                self.broken_links[category_name].add(link)
                                self.global_stats['broken_links'] += 1
                    break  # Stop if we found links with current selector
            
            # Remove duplicates while preserving order
            unique_links = list(dict.fromkeys(working_links))
            
            logger.info(f"Extracted {len(unique_links)} working product links from page {page_num}")
            if len(links) - len(unique_links) > 0:
                logger.warning(f"Found {len(links) - len(unique_links)} broken links on page {page_num}")
            
            return unique_links, len(unique_links) > 0
            
        except Exception as e:
            logger.error(f"Error extracting from {category_url} page {page_num}: {e}")
            return [], False
        finally:
            automation.quit()

    def scrape_category(self, category_url: str):
        """Scrape all products from a specific category with checkpoint support"""
        # Validate category URL first
        if not self.validate_url(category_url):
            logger.error(f"Category URL is not accessible: {category_url}")
            return

        category_name = self.get_category_name(category_url)
        logger.info(f"Starting category: {category_name}")
        
        # Initialize category data if not exists
        if category_name not in self.product_links:
            self.product_links[category_name] = set()
        if category_name not in self.category_stats:
            self.category_stats[category_name] = {
                'total_pages': 0,
                'processed_pages': 0,
                'total_products': 0,
                'failed_pages': set(),
                'processing_time': 0
            }
        
        start_time = time.time()
        
        try:
            # Detect total pages if not already done
            if self.category_stats[category_name]['total_pages'] == 0:
                total_pages = self.detect_category_pages(category_url)
                self.category_stats[category_name]['total_pages'] = total_pages
            else:
                total_pages = self.category_stats[category_name]['total_pages']
            
            if total_pages == 0:
                logger.error(f"No pages found for {category_name}")
                return
            
            logger.info(f"Processing {total_pages} pages for {category_name}")
            
            # Process pages sequentially for stability
            processed_pages = self.category_stats[category_name]['processed_pages']
            
            for page_num in range(processed_pages + 1, total_pages + 1):
                logger.info(f"{category_name} - Page {page_num}/{total_pages}")
                
                retry_count = 0
                success = False
                
                while retry_count < MAX_RETRIES and not success:
                    links, success = self.extract_category_links(category_url, page_num)
                    
                    if success:
                        self.product_links[category_name].update(links)
                        processed_pages += 1
                        self.category_stats[category_name]['processed_pages'] = processed_pages
                        logger.info(f"{category_name} - Page {page_num}: {len(links)} products")
                        
                        # Save checkpoint periodically
                        if processed_pages % 5 == 0:
                            self.save_checkpoint()
                        
                        # Small delay between requests
                        time.sleep(random.uniform(*REQUEST_DELAY))
                    else:
                        retry_count += 1
                        if retry_count < MAX_RETRIES:
                            wait_time = random.uniform(*SMART_RETRY_DELAY)
                            logger.warning(f"Retrying {category_name} page {page_num} in {wait_time:.1f}s (attempt {retry_count + 1})")
                            time.sleep(wait_time)
                            
                            # Try switching browser automation method on retry
                            self.current_automation_method = (self.current_automation_method + 1) % len(AUTOMATION_METHODS)
                        else:
                            logger.error(f"Failed {category_name} page {page_num} after {MAX_RETRIES} attempts")
                            self.category_stats[category_name]['failed_pages'].add(page_num)
            
            # Update final stats
            self.category_stats[category_name]['processed_pages'] = processed_pages
            self.category_stats[category_name]['total_products'] = len(self.product_links[category_name])
            self.category_stats[category_name]['processing_time'] = time.time() - start_time
            
            logger.info(f"{category_name} completed: {len(self.product_links[category_name])} products")
            
        except Exception as e:
            logger.error(f"Category {category_name} failed: {e}")
            self.failed_categories.add(category_name)

    def save_category_results(self, timestamp: str):
        """Save results organized by category with improved formatting"""
        results_dir = f"pharmacy_results_{timestamp}"
        os.makedirs(results_dir, exist_ok=True)
        
        all_products = []
        category_summary = []
        
        # Save broken links report
        broken_links_file = os.path.join(results_dir, "broken_links.csv")
        with open(broken_links_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Category", "Broken_URL"])
            for category, links in self.broken_links.items():
                for link in sorted(links):
                    writer.writerow([category, link])
        
        for category_name, links in self.product_links.items():
            if not links:
                continue
                
            links_list = sorted(list(links))
            stats = self.category_stats.get(category_name, {})
            
            # Save individual category file
            category_file = os.path.join(results_dir, f"{category_name}_products.csv")
            with open(category_file, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Product_URL", "Category", "Product_ID", "Extracted_At"])
                for i, link in enumerate(links_list, 1):
                    product_id = f"{category_name}_{i:04d}"
                    timestamp_str = datetime.now().isoformat()
                    writer.writerow([link, category_name, product_id, timestamp_str])
                    all_products.append([link, category_name, product_id, timestamp_str])
            
            # Add to summary
            broken_count = len(self.broken_links.get(category_name, set()))
            category_summary.append({
                'category': category_name,
                'total_pages': stats.get('total_pages', 0),
                'processed_pages': stats.get('processed_pages', 0),
                'failed_pages': len(stats.get('failed_pages', set())),
                'total_products': stats.get('total_products', 0),
                'broken_links': broken_count,
                'processing_time': f"{stats.get('processing_time', 0):.1f}s",
                'success_rate': f"{(stats.get('processed_pages', 0) / stats.get('total_pages', 1) * 100):.1f}%" if stats.get('total_pages', 0) > 0 else "0%"
            })
        
        # Save combined results
        combined_file = os.path.join(results_dir, "all_products_combined.csv")
        with open(combined_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Product_URL", "Category", "Product_ID", "Extracted_At"])
            writer.writerows(all_products)
        
        # Save detailed summary report
        summary_file = os.path.join(results_dir, "scraping_summary.json")
        with open(summary_file, "w", encoding="utf-8") as f:
            json.dump({
                'global_stats': self.global_stats,
                'category_summary': category_summary,
                'failed_categories': list(self.failed_categories),
                'total_unique_products': len(all_products),
                'scraper_config': {
                    'max_retries': MAX_RETRIES,
                    'request_delay': REQUEST_DELAY,
                    'batch_size': BATCH_SIZE,
                    'max_workers': MAX_WORKERS,
                    'automation_methods': AUTOMATION_METHODS
                }
            }, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Results saved in: {results_dir}/")
        logger.info(f"Combined file: all_products_combined.csv")
        logger.info(f"Summary: scraping_summary.json")
        logger.info(f"Individual category files: {len(self.product_links)} files")

    def load_checkpoint(self) -> bool:
        """Load previous progress from checkpoint file"""
        if os.path.exists(CHECKPOINT_FILE):
            try:
                with open(CHECKPOINT_FILE, 'r', encoding='utf-8') as f:
                    checkpoint = json.load(f)
                    
                # Convert lists back to sets
                for category in checkpoint.get('product_links', {}):
                    self.product_links[category] = set(checkpoint['product_links'][category])
                    
                self.category_stats = checkpoint.get('category_stats', {})
                # Convert lists back to sets for failed_pages
                for category in self.category_stats:
                    if 'failed_pages' in self.category_stats[category]:
                        self.category_stats[category]['failed_pages'] = set(
                            self.category_stats[category]['failed_pages']
                        )
                
                self.failed_categories = set(checkpoint.get('failed_categories', []))
                
                logger.info(f"Loaded checkpoint with {sum(len(links) for links in self.product_links.values())} products")
                return True
            except Exception as e:
                logger.error(f"Failed to load checkpoint: {e}")
        return False

    def save_checkpoint(self) -> None:
        """Save current progress to checkpoint file"""
        try:
            # Convert sets to lists for JSON serialization
            checkpoint = {
                'product_links': {k: list(v) for k, v in self.product_links.items()},
                'category_stats': {
                    k: {
                        **{sk: sv for sk, sv in v.items() if sk != 'failed_pages'},
                        'failed_pages': list(v.get('failed_pages', set()))
                    } for k, v in self.category_stats.items()
                },
                'failed_categories': list(self.failed_categories),
                'timestamp': datetime.now().isoformat()
            }
            
            with open(CHECKPOINT_FILE, 'w', encoding='utf-8') as f:
                json.dump(checkpoint, f, ensure_ascii=False, indent=2)
            
            logger.info("Checkpoint saved successfully")
        except Exception as e:
            logger.error(f"Failed to save checkpoint: {e}")

    def run(self):
        """Main execution method with checkpoint support"""
        self.global_stats['start_time'] = datetime.now().isoformat()
        start_time = time.time()
        
        logger.info("Enhanced Multi-Category Pharmacy Scraper Starting...")
        logger.info("="*80)
        logger.info(f"Processing {len(CATEGORIES)} categories")
        
        # Load checkpoint if exists
        if self.load_checkpoint():
            logger.info("Resuming from checkpoint...")
        
        logger.info("="*80)
        
        # Process each category
        for i, category_url in enumerate(CATEGORIES, 1):
            category_name = self.get_category_name(category_url)
            
            # Skip if already completed
            if category_name in self.category_stats:
                stats = self.category_stats[category_name]
                if stats.get('processed_pages', 0) >= stats.get('total_pages', 1):
                    logger.info(f"[{i}/{len(CATEGORIES)}] Skipping completed category: {category_name}")
                    self.global_stats['processed_categories'] += 1
                    continue
            
            logger.info(f"[{i}/{len(CATEGORIES)}] Processing: {category_name}")
            
            self.scrape_category(category_url)
            self.global_stats['processed_categories'] += 1
            
            # Calculate running totals
            total_products = sum(len(links) for links in self.product_links.values())
            self.global_stats['total_products'] = total_products
            
            logger.info(f"Progress: {i}/{len(CATEGORIES)} categories | {total_products} total products")
            
            # Save checkpoint after each category
            self.save_checkpoint()
            
            # Small delay between categories
            if i < len(CATEGORIES):
                time.sleep(random.uniform(5, 10))
        
        # Final results
        self.global_stats['end_time'] = datetime.now().isoformat()
        end_time = time.time()
        duration = end_time - start_time
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.save_category_results(timestamp)
        
        # Clean up checkpoint file
        if os.path.exists(CHECKPOINT_FILE):
            os.remove(CHECKPOINT_FILE)
        
        # Final report - Use plain text instead of emojis to avoid encoding issues
        logger.info("\n" + "="*80)
        logger.info("MULTI-CATEGORY SCRAPING COMPLETED!")
        logger.info(f"Total time: {duration:.1f} seconds ({duration/60:.1f} minutes)")
        logger.info(f"Categories processed: {self.global_stats['processed_categories']}/{len(CATEGORIES)}")
        logger.info(f"Total products collected: {self.global_stats['total_products']}")
        logger.info(f"Average speed: {self.global_stats['total_products']/duration:.1f} products/second")
        logger.info(f"Failed categories: {len(self.failed_categories)}")
        
        if self.failed_categories:
            logger.info(f"   Failed: {', '.join(self.failed_categories)}")
        
        logger.info("="*80)

def main():
    """Main function with error handling"""
    try:
        scraper = EnhancedPharmacyScraper()
        scraper.run()
    except KeyboardInterrupt:
        logger.info("Scraping interrupted by user")
    except Exception as e:
        logger.error(f"Scraping failed with error: {e}")
        raise

if __name__ == "__main__":
    main()
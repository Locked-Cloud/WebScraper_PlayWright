#!/usr/bin/env python3
"""
Turbo CSV Image Downloader - Ultra-fast version of the CSV Image Downloader
Optimized for maximum speed and parallelization with minimal overhead
"""

import os
import csv
import json
import time
import random
import requests
from urllib.parse import urlparse, urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager
from pathlib import Path
import hashlib
import re
from PIL import Image
import io
import logging
from logging.handlers import RotatingFileHandler
import argparse
from tqdm import tqdm
import traceback
import concurrent.futures
import gc

# --- Enhanced Configuration ---
class Config:
    # File paths
    CSV_FILE = "all_products_combined.csv"
    OUTPUT_DIR = "product_images"
    LOGS_DIR = "download_logs"
    CHECKPOINT_FILE = "csv_download_checkpoint.json"
    FAILED_PRODUCTS_FILE = "failed_products.json"
    DEBUG_LOG_FILE = "debug_log.txt"
    
    # Download settings - Extreme performance optimization
    MAX_WORKERS = 20  # Doubled from 10 to 20 for maximum parallelization
    BATCH_SIZE = 40   # Doubled from 20 to 40 for better throughput
    
    # Delays and timeouts - Minimized for speed
    PAGE_LOAD_DELAY = (0.2, 0.5)  # Reduced from (0.5, 1.5)
    REQUEST_TIMEOUT = 10     # Reduced from 15
    RETRY_DELAY = (1, 3)    # Reduced from (2, 5)
    MAX_RETRIES = 1         # Reduced from 2 to minimize waiting on failures
    SELENIUM_TIMEOUT = 5    # Reduced from 10
    
    # Image settings - More permissive
    SUPPORTED_FORMATS = ['jpg', 'jpeg', 'png', 'webp', 'gif', 'bmp']
    MAX_IMAGE_SIZE = 20 * 1024 * 1024  # Increased to 20MB
    MIN_IMAGE_SIZE = 256  # Reduced from 512 bytes for faster validation
    
    # Memory management - More aggressive
    CLEAR_MEMORY_INTERVAL = 25  # Reduced from 50 to clear memory more often
    
    # Cache settings - Enhanced
    ENABLE_URL_CACHE = True
    URL_CACHE_SIZE = 2000  # Doubled from 1000
    
    # Intelligent retry strategy - More aggressive
    ADAPTIVE_RETRY = True
    MAX_RETRY_MULTIPLIER = 1.2  # Reduced from 1.5 for faster retries
    
    # Enhanced error handling - More permissive
    MAX_ERRORS_BEFORE_COOLDOWN = 10  # Increased from 5
    COOLDOWN_PERIOD = 30  # Reduced from 60 seconds
    
    # Reduced selector list - Focus on high-probability selectors only
    IMAGE_SELECTORS = [
        # Primary product image selectors (most likely to succeed)
        ".single_product_image img",
        ".product-main-image img",
        ".product-image img",
        ".main-product-image",
        ".carousel-item.active img",
        ".carousel-item img",
        ".product-gallery img",
        "img[data-src*='cdn.chefaa.com']",
        "img[src*='cdn.chefaa.com']",
        
        # Generic fallbacks (only most common ones)
        "img[alt*='product']",
        "img[src*='uploads/products']",
        "img[src*='product']",
        "main img",
        ".container img"
    ]
    
    # Data selectors for product information
    DATA_SELECTORS = {
        'name': [
            'h1.header-extra',
            'h1[class*="product"]',
            'h1[class*="title"]',
            '.product-title',
            '.product-name',
            'h1',
            '.header-extra'
        ],
        'price': [
            '.product_price .header-extra',
            '.product-price',
            '.price',
            '[class*="price"]',
            '.product_price'
        ],
        'description': [
            '.description-product #nav-home',
            '.product-description',
            '.description',
            '[class*="description"]',
            '#nav-home'
        ]
    }
    
    # URL patterns to prioritize
    PRIORITY_URL_PATTERNS = [
        r'cdn\.chefaa\.com.*product',
        r'uploads/products/',
        r'product.*\.(jpg|jpeg|png|webp|gif)',
        r'images.*product'
    ]

class EnhancedCSVImageDownloader:
    def __init__(self, csv_file_path=None):
        self.csv_file = csv_file_path or Config.CSV_FILE
        self.setup_logging()
        self.setup_directories()
        self.products = []
        self.failed_products = []
        self.stats = {
            'total_products': 0,
            'total_processed': 0,
            'successful_downloads': 0,
            'already_exists': 0,
            'not_found': 0,
            'errors': 0,
            'invalid_images': 0,
            'data_extracted': 0,
            'start_time': None,
            'end_time': None,
            'by_category': {},
            'image_sources': {
                'primary_selector': 0,
                'lazy_loaded': 0,
                'fallback_selector': 0,
                'url_extraction': 0
            },
            'performance': {
                'avg_download_time': 0,
                'avg_processing_time': 0,
                'total_retries': 0,
                'cache_hits': 0,
                'cache_misses': 0
            }
        }
        self.lock = threading.Lock()
        self.session = requests.Session()
        self.setup_session()
        self.checkpoint = self.load_checkpoint()
        
        # Initialize caches
        self.url_cache = {}
        self.driver_pool = []
        self.error_counts = {}
        self.last_memory_clear = time.time()
        self.processed_count = 0
        
        # Initialize adaptive settings
        self.current_batch_size = Config.BATCH_SIZE
        self.current_workers = Config.MAX_WORKERS
        self.error_streak = 0
        self.success_streak = 0
        
    def setup_logging(self):
        """Initialize console and file logging"""
        log_dir = Config.LOGS_DIR
        os.makedirs(log_dir, exist_ok=True)
        self.logger = logging.getLogger('EnhancedCSVImageDownloader')
        if not self.logger.handlers:
            self.logger.setLevel(logging.DEBUG)
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            # Console handler (INFO+)
            ch = logging.StreamHandler()
            ch.setLevel(logging.INFO)
            ch.setFormatter(formatter)
            self.logger.addHandler(ch)
            # Rotating file handler (DEBUG)
            fh = RotatingFileHandler(os.path.join(log_dir, 'downloader.log'), maxBytes=2*1024*1024, backupCount=3, encoding='utf-8')
            fh.setLevel(logging.DEBUG)
            fh.setFormatter(formatter)
            self.logger.addHandler(fh)
            self.logger.propagate = False
        
    def debug_log(self, message):
        """Write debug messages to log file"""
        if hasattr(self, 'logger'):
            self.logger.debug(message)
        try:
            with open(Config.DEBUG_LOG_FILE, 'a', encoding='utf-8') as f:
                f.write(f"[{datetime.now()}] {message}\n")
        except Exception:
            pass
        
    def setup_directories(self):
        directories = [Config.OUTPUT_DIR, Config.LOGS_DIR]
        for directory in directories:
            try:
                os.makedirs(directory, exist_ok=True)
                print(f"✅ Directory ready: {directory}")
            except Exception as e:
                print(f"❌ Failed to create directory {directory}: {e}")
                return False
        
        if os.path.exists(self.csv_file):
            try:
                with open(self.csv_file, 'r', encoding='utf-8') as file:
                    reader = csv.DictReader(file)
                    categories = set()
                    for row in reader:
                        category = self.sanitize_filename(row.get('Category', 'unknown').strip())
                        categories.add(category)
                    for category in categories:
                        category_dir = os.path.join(Config.OUTPUT_DIR, category)
                        os.makedirs(category_dir, exist_ok=True)
                print(f"✅ Created {len(categories)} category directories")
            except Exception as e:
                print(f"⚠️ Warning: Could not create category directories: {e}")
        return True
        
    def sanitize_filename(self, filename):
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        filename = re.sub(r'\s+', '_', filename.strip())
        filename = re.sub(r'\.+', '.', filename)
        if len(filename) > 100:
            filename = filename[:100]
        return filename or 'unknown'
        
    def setup_session(self):
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'ar,en-US;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache'
        }
        self.session.headers.update(headers)
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
        retry_strategy = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
    def load_csv_products(self):
        if not os.path.exists(self.csv_file):
            print(f"❌ CSV file not found: {self.csv_file}")
            return False
        try:
            with open(self.csv_file, 'r', encoding='utf-8') as file:
                sample = file.read(1024)
                file.seek(0)
                delimiter = ','
                if sample.count(';') > sample.count(','):
                    delimiter = ';'
                elif sample.count('\t') > sample.count(','):
                    delimiter = '\t'
                reader = csv.DictReader(file, delimiter=delimiter)
                if reader.fieldnames is None:
                    print("❌ CSV file appears to be empty or missing header row.")
                    return False
                headers = [h.strip() for h in reader.fieldnames if h]
                print(f"📋 CSV Headers found: {headers}")
                url_field = category_field = id_field = None
                for header in headers:
                    header_lower = header.lower()
                    if 'url' in header_lower or 'link' in header_lower:
                        url_field = header
                    elif 'category' in header_lower or 'cat' in header_lower:
                        category_field = header
                    elif 'id' in header_lower or 'sku' in header_lower:
                        id_field = header
                if not all([url_field, category_field, id_field]):
                    print(f"❌ Could not map required fields. Found: URL={url_field}, Category={category_field}, ID={id_field}")
                    return False
                print(f"✅ Mapped fields: URL={url_field}, Category={category_field}, ID={id_field}")
                valid_products = 0
                for row_num, row in enumerate(reader, 1):
                    try:
                        url = row.get(url_field, '').strip()
                        category = row.get(category_field, 'unknown').strip()
                        product_id = row.get(id_field, f'product_{row_num}').strip()
                        if url and (url.startswith('http://') or url.startswith('https://')):
                            product = {
                                'url': url,
                                'category': self.sanitize_filename(category),
                                'product_id': self.sanitize_filename(product_id),
                                'row_number': row_num
                            }
                            self.products.append(product)
                            valid_products += 1
                            if product['category'] not in self.stats['by_category']:
                                self.stats['by_category'][product['category']] = {
                                    'total': 0, 'success': 0, 'exists': 0, 'errors': 0, 'not_found': 0, 'data_extracted': 0
                                }
                            self.stats['by_category'][product['category']]['total'] += 1
                    except Exception as e:
                        print(f"⚠️ Error processing row {row_num}: {e}")
                        continue
            self.stats['total_products'] = len(self.products)
            print(f"✅ Loaded {valid_products} valid products from {len(self.products)} total entries")
            print(f"📂 Categories found: {list(self.stats['by_category'].keys())}")
            return len(self.products) > 0
        except Exception as e:
            print(f"❌ Error reading CSV file: {e}")
            return False
    
    def load_checkpoint(self):
        try:
            if os.path.exists(Config.CHECKPOINT_FILE):
                with open(Config.CHECKPOINT_FILE, 'r') as f:
                    checkpoint = json.load(f)
                    checkpoint['completed_products'] = set(checkpoint.get('completed_products', []))
                    checkpoint['failed_products'] = set(checkpoint.get('failed_products', []))
                    print(f"📊 Checkpoint loaded: {len(checkpoint['completed_products'])} completed, {len(checkpoint['failed_products'])} failed")
                    return checkpoint
        except Exception as e:
            print(f"⚠️ Error loading checkpoint: {e}")
        return {'completed_products': set(), 'failed_products': set()}
    
    def save_checkpoint(self):
        try:
            checkpoint_data = {
                'completed_products': list(self.checkpoint['completed_products']),
                'failed_products': list(self.checkpoint['failed_products']),
                'last_update': datetime.now().isoformat(),
                'stats': self.stats
            }
            with open(Config.CHECKPOINT_FILE, 'w') as f:
                json.dump(checkpoint_data, f, indent=2, default=str)
            if self.failed_products:
                with open(Config.FAILED_PRODUCTS_FILE, 'w') as f:
                    json.dump(self.failed_products, f, indent=2, default=str)
        except Exception as e:
            print(f"⚠️ Error saving checkpoint: {e}")

    def create_optimized_driver(self):
        """Create a new WebDriver instance with extreme performance optimizations"""
        options = webdriver.ChromeOptions()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-software-rasterizer")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-background-timer-throttling")
        options.add_argument("--disable-backgrounding-occluded-windows")
        options.add_argument("--disable-renderer-backgrounding")
        options.add_argument("--disable-features=TranslateUI")
        options.add_argument("--disable-ipc-flooding-protection")
        options.add_argument("--log-level=3")
        options.add_argument("--silent")
        options.add_argument("--memory-pressure-off")
        options.add_argument("--max_old_space_size=4096")
        options.add_argument("--aggressive-cache-discard")
        options.add_argument("--window-size=1280,720")  # Reduced from 1920,1080 for less memory usage
        
        # Add safeguards against localStorage errors
        options.add_argument("--disable-web-security")
        options.add_argument("--allow-running-insecure-content")
        options.add_argument("--disable-site-isolation-trials")
        
        # Use fastest page load strategy
        options.page_load_strategy = 'eager'  # Changed from 'normal' to 'eager' for faster loads
        
        # Add language preferences for Arabic support
        options.add_argument("--lang=ar")
        
        prefs = {
            'profile.default_content_setting_values': {
                'cookies': 1,
                'images': 1,  # Keep images enabled for product scraping
                'plugins': 2,
                'popups': 2,
                'geolocation': 2,
                'notifications': 2,
                'media_stream': 2,
                'automatic_downloads': 2,
                'midi_sysex': 2,
                'push_messaging': 2,
                'ssl_cert_decisions': 2,
                'metro_switch_to_desktop': 2,
                'protected_media_identifier': 2,
                'app_banner': 2,
                'site_engagement': 2,
                'durable_storage': 2,
            },
            'profile.managed_default_content_settings': {
                'images': 1
            },
            'intl.accept_languages': 'ar,en-US,en',
            'disk-cache-size': 104857600,  # 100MB cache (doubled) for better performance
            'network.http.connection-timeout': 30,  # Reduced from 60
            # Disable localStorage and sessionStorage to prevent errors
            'dom.storage.enabled': False,
            # Disable saving history
            'history.saving_disabled': True,
            # Disable password saving
            'credentials_enable_service': False,
            'profile.password_manager_enabled': False
        }
        options.add_experimental_option('prefs', prefs)
        
        # Use a consistent user agent to improve cache hits
        options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        max_attempts = 2  # Reduced from 3 to 2
        for attempt in range(max_attempts):
            try:
                driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
                # Set minimal timeouts
                selenium_timeout = int(Config.SELENIUM_TIMEOUT) if Config.SELENIUM_TIMEOUT else 5
                driver.set_page_load_timeout(selenium_timeout)
                driver.set_script_timeout(selenium_timeout)
                driver.implicitly_wait(5)  # Reduced from 15
                
                # Test the driver with a simple operation that doesn't use localStorage
                driver.execute_script("return navigator.userAgent")
                return driver
            except Exception as e:
                self.debug_log(f"Driver creation attempt {attempt+1}/{max_attempts} failed: {e}")
                if attempt == max_attempts - 1:
                    self.debug_log(f"❌ Failed to create driver after {max_attempts} attempts: {e}")
                    return None
                time.sleep(1)  # Reduced from 2 seconds
        
        return None

    def safe_execute_script(self, driver, script, default_value=None):
        """Execute JavaScript safely, handling localStorage errors"""
        try:
            return driver.execute_script(script)
        except Exception as e:
            error_str = str(e).lower()
            if "localstorage" in error_str or "sessionstorage" in error_str:
                self.debug_log(f"Ignoring localStorage/sessionStorage error: {e}")
                return default_value
            else:
                # Re-raise other exceptions
                raise

    def wait_for_images_to_load(self, driver, timeout=5):  # Reduced from 20 to 5 seconds
        """Faster image loading with minimal waiting"""
        try:
            # Strategy 1: Wait for document to be ready
            try:
                # Use float division to ensure we get a float result
                half_timeout = float(timeout) / 2.0 if timeout is not None else 2.5
                WebDriverWait(driver, half_timeout).until(
                    lambda d: self.safe_execute_script(d, "return document.readyState") == "complete"
                )
            except TimeoutException:
                pass  # Continue anyway
            
            # Strategy 2: Quick scroll to trigger lazy loading
            try:
                # Use safe script execution with default values to prevent None
                total_height = self.safe_execute_script(driver, "return document.body.scrollHeight", 1000)
                # Ensure total_height is a number before division
                if total_height is not None:
                    scroll_position = total_height / 2
                else:
                    scroll_position = 500  # Default value if height is None
                self.safe_execute_script(driver, f"window.scrollTo(0, {scroll_position});")
                time.sleep(0.2)  # Reduced from 0.5
                self.safe_execute_script(driver, "window.scrollTo(0, 0);")
            except Exception:
                pass  # Ignore errors
            
            # Strategy 3: Wait for at least one image to load
            try:
                WebDriverWait(driver, timeout).until(
                    lambda d: self.safe_execute_script(d, 
                        """
                        const imgs = Array.from(document.images);
                        return imgs.some(img => img.complete && img.naturalWidth > 0);
                        """
                    ) == True
                )
            except TimeoutException:
                pass  # Continue with available images
            
            # Strategy 4: Trigger lazy loading (simplified)
            try:
                self.safe_execute_script(driver, """
                    document.querySelectorAll('img[data-src]').forEach(img => {
                        if (img.dataset.src) img.src = img.dataset.src;
                    });
                    window.dispatchEvent(new Event('scroll'));
                """)
            except Exception:
                pass  # Ignore errors
                
        except Exception as e:
            self.debug_log(f"⚠️ Error waiting for images: {e}")
            # Continue execution regardless of errors

    def extract_image_urls(self, driver, product_url):
        """Ultra-fast image URL extraction focusing on highest probability sources"""
        found_urls = []
        try:
            # Strategy 1: Quick CSS Selectors - only check the most likely selectors
            for i, selector in enumerate(Config.IMAGE_SELECTORS[:10]):  # Limit to first 10 selectors for speed
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements[:5]:  # Limit to first 5 elements per selector for speed
                        url = element.get_attribute('src') or element.get_attribute('data-src')
                        if url and self.is_valid_image_url(url):
                            priority = self.calculate_url_priority(url)
                            found_urls.append({
                                'url': url,
                                'priority': priority,
                                'selector_index': i,
                                'source': f'selector_{i}'
                            })
                except Exception:
                    continue
            
            # Strategy 2: Fast JavaScript extraction (single call instead of multiple DOM operations)
            if len(found_urls) < 3:  # Only if we haven't found enough images yet
                try:
                    js_urls = self.safe_execute_script(driver, """
                        try {
                            var results = [];
                            // Get src attributes
                            document.querySelectorAll('img[src*="product"], img[src*="cdn.chefaa"], img[src*="uploads"]').forEach(function(img) {
                                if (img.src && img.src.indexOf('data:') !== 0) {
                                    results.push({url: img.src, type: 'src'});
                                }
                            });
                            // Get data-src attributes
                            document.querySelectorAll('img[data-src]').forEach(function(img) {
                                if (img.dataset.src) {
                                    results.push({url: img.dataset.src, type: 'data-src'});
                                }
                            });
                            return results;
                        } catch(e) {
                            return [];
                        }
                    """)
                    
                    if js_urls:
                        for item in js_urls[:10]:  # Limit to first 10 results for speed
                            url = item.get('url')
                            if url and self.is_valid_image_url(url):
                                priority = self.calculate_url_priority(url)
                                found_urls.append({
                                    'url': url,
                                    'priority': priority,
                                    'selector_index': 500,
                                    'source': f'js_{item.get("type", "unknown")}'
                                })
                except Exception:
                    pass  # Ignore errors
            
            # Remove duplicates and sort by priority - limit to top candidates
            found_urls.sort(key=lambda x: (-x['priority'], x['selector_index']))
            seen_urls = set()
            unique_urls = []
            for item in found_urls:
                if item['url'] not in seen_urls:
                    seen_urls.add(item['url'])
                    unique_urls.append(item)
                    if len(unique_urls) >= 5:  # Only keep top 5 URLs for speed
                        break
            
            return unique_urls
            
        except Exception as e:
            self.debug_log(f"⚠️ Error extracting image URLs: {e}")
            return []

    def calculate_url_priority(self, url):
        priority = 0
        url_lower = url.lower()
        
        # Domain priority
        if 'cdn.chefaa.com' in url_lower:
            priority += 20
        
        # Path priority
        for pattern in Config.PRIORITY_URL_PATTERNS:
            if re.search(pattern, url_lower):
                priority += 10
        
        # Size indicators
        if any(size in url_lower for size in ['1024', '1200', '1920', 'large', 'big', '718x718', '1226x1374']):
            priority += 5
        if any(thumb in url_lower for thumb in ['thumb', 'small', '64x', '100x', '150x', '144x156']):
            priority -= 5
        
        # Quality indicators
        if any(orig in url_lower for orig in ['original', 'full', 'master']):
            priority += 3
        
        return priority

    def extract_product_data(self, driver):
        """Enhanced product data extraction with multiple selector attempts"""
        product_data = {
            'name': None,
            'price': None,
            'description': None
        }
        
        try:
            # Extract name
            for selector in Config.DATA_SELECTORS['name']:
                try:
                    element = driver.find_element(By.CSS_SELECTOR, selector)
                    product_data['name'] = element.text.strip()
                    if product_data['name']:
                        break
                except NoSuchElementException:
                    continue
            
            # Extract price
            for selector in Config.DATA_SELECTORS['price']:
                try:
                    element = driver.find_element(By.CSS_SELECTOR, selector)
                    product_data['price'] = element.text.strip()
                    if product_data['price']:
                        break
                except NoSuchElementException:
                    continue
            
            # Extract description
            for selector in Config.DATA_SELECTORS['description']:
                try:
                    element = driver.find_element(By.CSS_SELECTOR, selector)
                    product_data['description'] = element.get_attribute('innerHTML').strip()
                    if product_data['description']:
                        break
                except NoSuchElementException:
                    continue
            
            return product_data, "success"
            
        except Exception as e:
            self.debug_log(f"⚠️ Error extracting product data: {e}")
            return product_data, f"error: {str(e)}"

    def save_product_data(self, product_data, product, image_path=None):
        """Save product data to a JSON file"""
        try:
            category_dir = os.path.join(Config.OUTPUT_DIR, product['category'])
            data_filename = os.path.join(category_dir, f"{product['product_id']}.json")
            
            save_data = {
                **product_data,
                'image_path': image_path if image_path else None,
                'url': product['url'],
                'category': product['category'],
                'product_id': product['product_id'],
                'timestamp': datetime.now().isoformat()
            }
            
            with open(data_filename, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, indent=2, ensure_ascii=False)
            return True, data_filename
        except Exception as e:
            return False, f"save_error: {str(e)}"

    def is_product_not_found(self, driver):
        """Less aggressive not found detection"""
        try:
            # Check HTTP status
            current_url = driver.current_url
            if '404' in current_url:
                return True
            
            # Check title for obvious 404 indicators
            title = driver.title.lower()
            obvious_404_titles = ['404', 'not found', 'page not found']
            if any(phrase in title for phrase in obvious_404_titles):
                return True
            
            # Check for explicit error messages in common locations
            error_selectors = [
                '.error-404',
                '.not-found',
                '[class*="404"]',
                '[class*="error"]'
            ]
            
            for selector in error_selectors:
                try:
                    element = driver.find_element(By.CSS_SELECTOR, selector)
                    if element.is_displayed():
                        error_text = element.text.lower()
                        if any(phrase in error_text for phrase in ['404', 'not found', 'خطأ']):
                            return True
                except:
                    continue
            
            # If we can find basic page structure, assume it's valid
            basic_selectors = ['body', 'main', '.container', '#main', 'header']
            for selector in basic_selectors:
                try:
                    element = driver.find_element(By.CSS_SELECTOR, selector)
                    if element and len(element.text) > 100:  # Page has substantial content
                        return False
                except:
                    continue
            
            return False
            
        except Exception as e:
            self.debug_log(f"Error in is_product_not_found: {e}")
            return False

    def is_valid_image_url(self, url):
        if not url or url.startswith('data:') or len(url) < 10:
            return False
        if url.startswith('//'):
            url = 'https:' + url
        elif url.startswith('/'):
            return False
        try:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                return False
            path = parsed.path.lower()
            has_extension = any(f'.{ext}' in path for ext in Config.SUPPORTED_FORMATS)
            has_image_indicator = any(keyword in url.lower() for keyword in [
                'image', 'img', 'photo', 'picture', 'product', 'uploads', 'cdn.chefaa.com'
            ])
            return has_extension or has_image_indicator
        except Exception:
            return False

    def validate_downloaded_image(self, filepath):
        try:
            if not os.path.exists(filepath):
                return False, "file_not_exists"
            file_size = os.path.getsize(filepath)
            if file_size < Config.MIN_IMAGE_SIZE:
                return False, "file_too_small"
            if file_size > Config.MAX_IMAGE_SIZE:
                return False, "file_too_large"
            with Image.open(filepath) as img:
                img.verify()
            with Image.open(filepath) as img:
                width, height = img.size
                if width < 50 or height < 50:
                    return False, "image_too_small"
            return True, "valid"
        except Exception as e:
            return False, f"validation_error: {str(e)}"

    def download_image(self, img_url, product):
        """Optimized image download with minimal validation"""
        try:
            # Check cache first
            cached_data = self.get_cached_url(img_url)
            if cached_data:
                return cached_data
            
            # Ensure URL is absolute
            if img_url.startswith('//'):
                img_url = 'https:' + img_url
            elif img_url.startswith('/'):
                base_url = urlparse(product['url']).scheme + '://' + urlparse(product['url']).netloc
                img_url = urljoin(base_url, img_url)
            
            # Generate filename
            file_extension = '.jpg'  # Default to jpg
            if '.' in img_url.split('/')[-1]:
                ext = img_url.split('.')[-1].lower()
                if ext in Config.SUPPORTED_FORMATS:
                    file_extension = f'.{ext}'
            
            # Create safe filename
            safe_filename = f"{product['product_id']}{file_extension}"
            category_dir = os.path.join(Config.OUTPUT_DIR, product['category'])
            filepath = os.path.join(category_dir, safe_filename)
            
            # Check if file already exists
            if os.path.exists(filepath):
                # Quick size check instead of full validation
                file_size = os.path.getsize(filepath)
                if Config.MIN_IMAGE_SIZE <= file_size <= Config.MAX_IMAGE_SIZE:
                    # Cache the successful result
                    self.cache_url(img_url, (filepath, "already_exists"))
                    return filepath, "already_exists"
                else:
                    os.remove(filepath)
            
            # Fast download with minimal retries
            try:
                # Use streaming with a smaller chunk size for faster processing
                with self.session.get(
                    img_url,
                    timeout=Config.REQUEST_TIMEOUT,
                    stream=True,
                    allow_redirects=True,
                    headers={'Accept': 'image/*,*/*;q=0.8'}  # Prioritize images
                ) as response:
                    response.raise_for_status()
                    
                    # Skip content-type check for speed
                    
                    # Download with minimal validation
                    with open(filepath, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=16384):  # Larger chunks for speed
                            if chunk:
                                f.write(chunk)
                    
                    # Quick size validation only
                    file_size = os.path.getsize(filepath)
                    if Config.MIN_IMAGE_SIZE <= file_size <= Config.MAX_IMAGE_SIZE:
                        # Cache the successful result
                        self.cache_url(img_url, (filepath, "success"))
                        return filepath, "success"
                    else:
                        os.remove(filepath)
                        return None, "invalid_file_size"
            
            except requests.exceptions.RequestException as e:
                return None, f"download_error: {str(e)}"
            except Exception as e:
                if os.path.exists(filepath):
                    try:
                        os.remove(filepath)
                    except:
                        pass
                return None, f"unexpected_error: {str(e)}"
            
        except Exception as e:
            return None, f"download_setup_error: {str(e)}"

    def download_product_images(self, product):
        """Optimized product image download with minimal processing"""
        product_key = f"{product['category']}_{product['product_id']}"
        
        # Skip if already processed
        if product_key in self.checkpoint['completed_products']:
            with self.lock:
                self.stats['total_processed'] += 1
                self.stats['already_exists'] += 1
                self.stats['by_category'][product['category']]['exists'] += 1
            return {
                'product_id': product['product_id'],
                'status': 'already_processed',
                'category': product['category']
            }
        
        driver = None
        result = {
            'product_id': product['product_id'],
            'category': product['category'],
            'url': product['url'],
            'status': 'failed',
            'images_downloaded': 0,
            'error': None,
            'product_data': {},
            'image_path': None
        }
        
        try:
            # Create driver with a single attempt
            driver = self.create_optimized_driver()
            if not driver:
                result['error'] = "failed_to_create_driver"
                return result
            
            # Load page with a single attempt
            try:
                # Skip localStorage/sessionStorage operations
                driver.delete_all_cookies()
                
                # Load the page with timeout
                driver.get(product['url'])
                
                # Quick wait for page load
                try:
                    WebDriverWait(driver, Config.SELENIUM_TIMEOUT).until(
                        lambda d: self.safe_execute_script(d, "return document.readyState") == "complete"
                    )
                except:
                    pass  # Continue anyway
                
            except Exception as e:
                result['error'] = f"page_load_error: {str(e)}"
                return result
            
            # Quick check if product not found
            if self.is_product_not_found(driver):
                result['status'] = 'not_found'
                result['error'] = 'product_page_not_found'
                with self.lock:
                    self.stats['not_found'] += 1
                    self.stats['by_category'][product['category']]['not_found'] += 1
                return result
            
            # Minimal wait for images
            self.wait_for_images_to_load(driver)
            
            # Extract image URLs with a single attempt
            image_urls = self.extract_image_urls(driver, product['url'])
            
            if not image_urls:
                result['error'] = 'no_images_found'
                return result
            
            # Try to download images - only try the top 3 candidates
            for img_info in image_urls[:3]:
                img_url = img_info['url']
                
                downloaded_path, download_status = self.download_image(img_url, product)
                
                if downloaded_path and download_status in ['success', 'already_exists']:
                    result['images_downloaded'] = 1
                    result['status'] = 'success'
                    result['image_path'] = downloaded_path
                    
                    with self.lock:
                        if download_status == 'success':
                            self.stats['successful_downloads'] += 1
                            self.stats['by_category'][product['category']]['success'] += 1
                        else:
                            self.stats['already_exists'] += 1
                            self.stats['by_category'][product['category']]['exists'] += 1
                    
                    break  # Success, stop trying other URLs
            
            if result['status'] != 'success':
                result['error'] = 'all_downloads_failed'
        
        except Exception as e:
            result['error'] = f"unexpected_error: {str(e)}"
        
        finally:
            if driver:
                try:
                    driver.quit()
                except:
                    pass  # Ignore driver quit errors
            
            # Update progress
            with self.lock:
                self.stats['total_processed'] += 1
                
                if result['status'] == 'success':
                    self.checkpoint['completed_products'].add(product_key)
                elif result['status'] == 'failed':
                    self.stats['errors'] += 1
                    self.stats['by_category'][product['category']]['errors'] += 1
                    self.checkpoint['failed_products'].add(product_key)
        
        return result

    def process_batch(self, products_batch):
        """Process a batch of products with maximum parallelization"""
        results = []
        successful_products = 0
        start_time = time.time()
        
        # Use a larger thread pool for maximum parallelization
        with ThreadPoolExecutor(max_workers=self.current_workers) as executor:
            # Submit all jobs at once
            future_to_product = {
                executor.submit(self.download_product_images, product): product 
                for product in products_batch
            }
            
            # Process results as they complete
            for future in as_completed(future_to_product):
                product = future_to_product[future]
                try:
                    result = future.result()
                    results.append(result)
                    
                    # Update progress bar
                    if hasattr(self, 'progress_bar'):
                        self.progress_bar.update(1)
                    
                    # Track success/failure
                    if result['status'] == 'success':
                        successful_products += 1
                    
                    # Minimal status output - only show errors to reduce console output
                    if result['status'] == 'failed':
                        error_type = result.get('error', 'unknown').split(':')[0] if result.get('error') else 'unknown'
                        print(f"❌ {product['product_id']} | {error_type}")
                        
                        # Log errors for analysis
                        self.debug_log(f"Error for {result['product_id']}: {result.get('error')}")
                        self.error_counts[error_type] = self.error_counts.get(error_type, 0) + 1
                    
                except Exception as e:
                    print(f"❌ Thread error: {product['product_id']}")
                    results.append({
                        'product_id': product['product_id'],
                        'status': 'thread_error',
                        'error': str(e)
                    })
                    if hasattr(self, 'progress_bar'):
                        self.progress_bar.update(1)
                
                # Update processed count and clear memory if needed
                self.processed_count += 1
                self.clear_memory()
        
        # Calculate batch performance metrics
        batch_time = time.time() - start_time
        batch_size = len(products_batch)
        success_rate = successful_products / batch_size if batch_size > 0 else 0
        
        # Update performance stats
        with self.lock:
            self.stats['performance']['avg_processing_time'] = (
                (self.stats['performance']['avg_processing_time'] * (self.stats['total_processed'] - batch_size) +
                 batch_time) / self.stats['total_processed']
            )
        
        # Adjust batch settings based on performance
        self.adjust_batch_settings(success_rate)
        
        # Print minimal batch performance summary
        print(f"\n📊 Batch: {successful_products}/{batch_size} ({success_rate:.1%}) in {batch_time:.1f}s ({batch_time/batch_size:.1f}s/product)")
        
        return results

    def print_progress(self):
        """Print current progress statistics"""
        total = self.stats['total_products']
        processed = self.stats['total_processed']
        success = self.stats['successful_downloads']
        exists = self.stats['already_exists']
        errors = self.stats['errors']
        not_found = self.stats['not_found']
        data_extracted = self.stats['data_extracted']
        
        if total > 0:
            progress_pct = (processed / total) * 100
            success_rate = (success / processed * 100) if processed > 0 else 0
            
            print(f"\n📊 Progress: {processed}/{total} ({progress_pct:.1f}%)")
            print(f"   ✅ Success: {success} | 📁 Exists: {exists} | ❌ Errors: {errors}")
            print(f"   🔍 Not Found: {not_found} | 📄 Data Extracted: {data_extracted}")
            print(f"   📈 Success Rate: {success_rate:.1f}%")
            
            if self.stats['by_category']:
                print(f"   📂 By Category:")
                for cat, stats in self.stats['by_category'].items():
                    if stats['total'] > 0:
                        cat_success_rate = ((stats['success'] + stats['exists']) / stats['total']) * 100
                        print(f"      {cat}: {stats['success']+stats['exists']}/{stats['total']} ({cat_success_rate:.1f}%)")

    def run(self):
        """Main execution method with maximum performance optimizations"""
        print("🚀 Starting Enhanced CSV Image Downloader (Turbo Mode)")
        self.stats['start_time'] = datetime.now()
        
        # Load products
        if not self.load_csv_products():
            print("❌ Failed to load products from CSV")
            return False
        
        print(f"📊 Total products to process: {len(self.products)}")
        
        # Filter products that haven't been processed
        remaining_products = [
            p for p in self.products 
            if f"{p['category']}_{p['product_id']}" not in self.checkpoint['completed_products']
        ]
        
        if not remaining_products:
            print("✅ All products have already been processed!")
            return True
        
        print(f"🔄 Products remaining: {len(remaining_products)}")
        
        # Create a global tqdm progress bar
        self.progress_bar = tqdm(total=len(remaining_products), desc="Products", unit="prod", leave=True)
        
        # Pre-create all category directories to avoid race conditions
        self._ensure_all_category_directories()
        
        try:
            # Process in larger batches for better throughput
            total_batches = (len(remaining_products) + self.current_batch_size - 1) // self.current_batch_size
            
            for batch_num in range(total_batches):
                start_idx = batch_num * self.current_batch_size
                end_idx = min(start_idx + self.current_batch_size, len(remaining_products))
                batch = remaining_products[start_idx:end_idx]
                
                print(f"\n🔄 Batch {batch_num + 1}/{total_batches} ({len(batch)} products) - {self.current_workers} workers")
                
                # Process batch
                batch_results = self.process_batch(batch)
                
                # Save checkpoint after each batch
                self.save_checkpoint()
                
                # Print compact progress
                self._print_compact_progress()
                
                # No delay between batches for maximum speed
            
            # Skip retry mechanism for maximum speed - failed products will be retried on next run
            
        except KeyboardInterrupt:
            print("\n⚠️ Process interrupted by user. Saving progress...")
            self.save_checkpoint()
            if hasattr(self, 'progress_bar'):
                self.progress_bar.close()
            return False
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
            self.save_checkpoint()
            if hasattr(self, 'progress_bar'):
                self.progress_bar.close()
            return False
        finally:
            # Ensure progress bar is closed
            if hasattr(self, 'progress_bar'):
                self.progress_bar.close()
        
        # Final statistics
        self.stats['end_time'] = datetime.now()
        duration = self.stats['end_time'] - self.stats['start_time']
        
        print(f"\n🎯 Download Complete!")
        print(f"⏱️  Total time: {duration}")
        print(f"📊 Final Statistics: {self.stats['successful_downloads']} downloaded, {self.stats['errors']} errors")
        
        return True

    def _ensure_all_category_directories(self):
        """Pre-create all category directories at once to avoid race conditions"""
        for category in self.stats['by_category'].keys():
            category_dir = os.path.join(Config.OUTPUT_DIR, category)
            os.makedirs(category_dir, exist_ok=True)
    
    def _print_compact_progress(self):
        """Print compact progress statistics"""
        total = self.stats['total_products']
        processed = self.stats['total_processed']
        success = self.stats['successful_downloads']
        errors = self.stats['errors']
        
        if total > 0:
            progress_pct = (processed / total) * 100
            success_rate = (success / processed * 100) if processed > 0 else 0
            
            print(f"📊 Progress: {processed}/{total} ({progress_pct:.1f}%) | Success: {success} | Errors: {errors} | Rate: {success_rate:.1f}%")

    def clear_memory(self, force=False):
        """Clear memory periodically"""
        if force or (self.processed_count % Config.CLEAR_MEMORY_INTERVAL == 0):
            self.url_cache.clear()
            gc.collect()
            self.last_memory_clear = time.time()
            
    def adjust_batch_settings(self, batch_success_rate):
        """Aggressively adjust batch size and workers based on performance"""
        if batch_success_rate > 0.8:  # Very successful - be more aggressive
            self.current_batch_size = min(int(self.current_batch_size * 1.5), Config.BATCH_SIZE * 3)  # Allow up to 3x batch size
            self.current_workers = min(int(self.current_workers + 2), int(Config.MAX_WORKERS * 2))  # Allow up to 2x workers
            self.success_streak += 1
            self.error_streak = 0
        elif batch_success_rate < 0.5:  # Poor performance
            self.current_batch_size = max(int(self.current_batch_size * 0.7), int(Config.BATCH_SIZE * 0.3))  # Don't go below 30%
            self.current_workers = max(int(self.current_workers - 2), int(Config.MAX_WORKERS * 0.3))  # Don't go below 30%
            self.error_streak += 1
            self.success_streak = 0
            
        # Apply cooldown only if error streak is very high
        if self.error_streak >= Config.MAX_ERRORS_BEFORE_COOLDOWN:
            time.sleep(Config.COOLDOWN_PERIOD / 2)  # Use half the cooldown period
            self.error_streak = 0
            
    def get_cached_url(self, url):
        """Get URL from cache or download"""
        if not Config.ENABLE_URL_CACHE:
            return None
            
        cache_key = hashlib.md5(url.encode()).hexdigest()
        if cache_key in self.url_cache:
            self.stats['performance']['cache_hits'] += 1
            return self.url_cache[cache_key]
            
        self.stats['performance']['cache_misses'] += 1
        return None
        
    def cache_url(self, url, data):
        """Cache URL data"""
        if not Config.ENABLE_URL_CACHE:
            return
            
        cache_key = hashlib.md5(url.encode()).hexdigest()
        if len(self.url_cache) >= Config.URL_CACHE_SIZE:
            # Remove oldest entry
            self.url_cache.pop(next(iter(self.url_cache)))
        self.url_cache[cache_key] = data
        
    def get_retry_delay(self, attempt):
        """Get adaptive retry delay based on error patterns"""
        if not Config.ADAPTIVE_RETRY:
            return random.uniform(*Config.RETRY_DELAY)
            
        base_delay = Config.RETRY_DELAY[0]
        max_delay = Config.RETRY_DELAY[1]
        
        # Increase delay based on error streak
        multiplier = min(1 + (self.error_streak * 0.2), Config.MAX_RETRY_MULTIPLIER)
        delay = base_delay * multiplier * (attempt + 1)
        
        return min(delay, max_delay)

def main():
    """Main entry point for the script"""
    parser = argparse.ArgumentParser(description='Turbo CSV Image Downloader - Ultra-fast version')
    parser.add_argument('--csv', help='Path to the CSV file', default=Config.CSV_FILE)
    parser.add_argument('--output', help='Output directory', default=Config.OUTPUT_DIR)
    parser.add_argument('--workers', type=int, help='Number of worker threads', default=Config.MAX_WORKERS)
    parser.add_argument('--batch', type=int, help='Batch size', default=Config.BATCH_SIZE)
    parser.add_argument('--timeout', type=int, help='Selenium timeout in seconds', default=Config.SELENIUM_TIMEOUT)
    parser.add_argument('--retries', type=int, help='Maximum retries', default=Config.MAX_RETRIES)
    parser.add_argument('--no-cache', action='store_false', dest='cache', help='Disable URL caching')
    parser.add_argument('--no-adaptive', action='store_false', dest='adaptive', help='Disable adaptive retry')
    
    args = parser.parse_args()
    
    # Override config with command line arguments
    Config.CSV_FILE = args.csv
    Config.OUTPUT_DIR = args.output
    Config.MAX_WORKERS = args.workers
    Config.BATCH_SIZE = args.batch
    Config.SELENIUM_TIMEOUT = args.timeout
    Config.MAX_RETRIES = args.retries
    Config.ENABLE_URL_CACHE = args.cache
    Config.ADAPTIVE_RETRY = args.adaptive
    
    # Create and run the downloader
    downloader = EnhancedCSVImageDownloader(args.csv)
    downloader.run()

if __name__ == "__main__":
    main()
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
from typing import Optional, List, Any, Dict, Union, Tuple, Set, TypeVar, Type, cast
from tqdm import tqdm

# Define Playwright types
try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    print("⚠️ Playwright not available. Will use Selenium by default.")

# Type aliases for better readability
PlaywrightType = Any
BrowserType = Any
BrowserContextType = Any
PageType = Any

# --- Enhanced Configuration ---
class Config:
    # File paths
    CSV_FILE = "all_products_combined.csv"
    OUTPUT_DIR = "product_images"
    LOGS_DIR = "download_logs"
    CHECKPOINT_FILE = "csv_download_checkpoint.json"
    FAILED_PRODUCTS_FILE = "failed_products.json"
    DEBUG_LOG_FILE = "debug_log.txt"
    
    # Download settings - Anti-blocking optimization
    MAX_WORKERS = 5  # Reduced from 20 to avoid overwhelming the server
    BATCH_SIZE = 10  # Reduced from 40 to avoid detection
    
    # Delays and timeouts - Adjusted for website responsiveness
    PAGE_LOAD_DELAY = (4, 8)  # Increased to appear more human-like
    REQUEST_TIMEOUT = 45     # Increased from 30 to handle slow responses
    RETRY_DELAY = (5, 10)    # Increased to avoid rate limiting
    MAX_RETRIES = 3         # Increased to handle temporary failures
    SELENIUM_TIMEOUT = 45    # Increased from 30 to handle slow page loads
    
    # Browser settings to avoid detection
    BROWSER_HEADERS = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'ar,en-US;q=0.9,en;q=0.8',
        'Cache-Control': 'no-cache',
        'Pragma': 'no-cache',
        'Upgrade-Insecure-Requests': '1',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    # Random user agents to rotate
    USER_AGENTS = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    ]
    
    # Image settings
    SUPPORTED_FORMATS = ['jpg', 'jpeg', 'png', 'webp', 'gif', 'bmp']
    MAX_IMAGE_SIZE = 20 * 1024 * 1024
    MIN_IMAGE_SIZE = 100  # Reduced from 256 to accept smaller images
    ACCEPT_SMALL_IMAGES = True  # New flag to accept small images if no larger ones are found
    
    # Memory and cache settings
    CLEAR_MEMORY_INTERVAL = 25
    ENABLE_URL_CACHE = True
    URL_CACHE_SIZE = 2000
    
    # Error handling
    ADAPTIVE_RETRY = True
    MAX_RETRY_MULTIPLIER = 1.5
    MAX_ERRORS_BEFORE_COOLDOWN = 3  # Reduced to be more sensitive to errors
    COOLDOWN_PERIOD = 60  # Increased cooldown period
    
    # Browser automation settings
    BROWSER_AUTOMATION_TYPES = ['playwright', 'selenium']
    BROWSER_AUTOMATION = 'playwright'  # Default browser automation
    BROWSER_FALLBACK = True  # Enable fallback to other browser automation if primary fails
    
    # Enhanced selectors with more generic fallbacks
    IMAGE_SELECTORS = [
        # Primary product image selectors
        ".single_product_image img",
        ".product-main-image img",
        ".product-image img",
        ".main-product-image",
        
        # Carousel selectors
        ".carousel-item.active img",
        ".carousel-item img",
        "#carousel-slider img",
        "#carousel-slider-modal img",
        
        # Gallery selectors
        ".product-gallery img",
        ".single_product_images img",
        ".product-slider img",
        
        # Picture tag selectors
        ".single_product_image picture img",
        ".carousel-item picture img",
        "picture img[alt*='product']",
        
        # Lazy loading selectors
        "img.lazyload[data-src*='product']",
        "img.lazyloaded[src*='product']",
        "img[data-src*='cdn.chefaa.com']",
        "img[src*='cdn.chefaa.com']",
        
        # Generic fallbacks
        "img[alt*='product']",
        "img[src*='uploads/products']",
        "img[data-src*='uploads/products']",
        ".product-photo img",
        ".item-image img",
        "[class*='product'][class*='image'] img",
        ".zoom-image",
        "[class*='zoom'] img",
        ".single_product img",
        
        # Last resort - any image that might be a product
        "img[src*='product']",
        "img[data-src*='product']",
        "main img",
        "#main img",
        ".container img",
        
        # Additional fallbacks for any image
        "img[src*='uploads']",
        "img[src*='cdn']",
        "img"  # Last resort - any image
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
    
    @classmethod
    def set_browser_automation(cls, browser_type: str) -> None:
        """Set browser automation type with validation"""
        if browser_type in cls.BROWSER_AUTOMATION_TYPES:
            cls.BROWSER_AUTOMATION = browser_type
        else:
            print(f"⚠️ Invalid browser type '{browser_type}'. Using default: {cls.BROWSER_AUTOMATION}")
    
    # URL patterns to prioritize
    PRIORITY_URL_PATTERNS = [
        r'cdn\.chefaa\.com.*product',
        r'uploads/products/',
        r'product.*\.(jpg|jpeg|png|webp|gif)',
        r'images.*product'
    ]

    # New: Default image to use when no valid image is found
    DEFAULT_IMAGE_PATH = "default_product_image.png"
    USE_DEFAULT_IMAGE = True  # Set to True to use default image as fallback
    CREATE_DEFAULT_IMAGE = True  # Create a default image if it doesn't exist

class PlaywrightBrowser:
    """Playwright browser automation implementation with advanced anti-bot measures and performance optimizations"""
    def __init__(self):
        self.playwright: Optional[PlaywrightType] = None
        self.browser: Optional[BrowserType] = None
        self.context: Optional[BrowserContextType] = None
        self.page: Optional[PageType] = None
        
    def create(self) -> bool:
        """Create a new Playwright browser instance with advanced anti-bot measures"""
        try:
            # Check if playwright is installed
            if not PLAYWRIGHT_AVAILABLE:
                print("⚠️ Playwright not available. Please install it with: pip install playwright")
                print("⚠️ And install browsers with: playwright install chromium")
                return False
                
            playwright = sync_playwright().start()
            self.playwright = cast(PlaywrightType, playwright)
            if not self.playwright:
                return False
                
            # Use random user agent
            user_agent = random.choice(Config.USER_AGENTS)
                
            # Launch browser with optimized settings
            browser = self.playwright.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu',
                    '--disable-software-rasterizer',
                    '--disable-features=TranslateUI',
                    '--disable-extensions',
                    '--disable-component-extensions-with-background-pages',
                    '--disable-default-apps',
                    '--mute-audio',
                    '--no-default-browser-check',
                    '--no-first-run',
                    '--hide-scrollbars',
                    '--metrics-recording-only',
                    '--safebrowsing-disable-auto-update',
                ]
            )
            self.browser = cast(BrowserType, browser)
            if not self.browser:
                return False
            
            # Enhanced context settings with sophisticated anti-bot measures
            context = self.browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent=user_agent,
                locale='ar-EG',
                timezone_id='Africa/Cairo',
                ignore_https_errors=True,
                java_script_enabled=True,
                has_touch=True,
                is_mobile=False,
                color_scheme='light',
                reduced_motion='no-preference',
                forced_colors='none',
                extra_http_headers={
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'ar,en-US;q=0.9,en;q=0.8',
                    'Cache-Control': 'max-age=0',
                    'Upgrade-Insecure-Requests': '1',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'none',
                    'Sec-Fetch-User': '?1',
                }
            )
            self.context = cast(BrowserContextType, context)
            if not self.context:
                return False
            
            # Configure page settings with longer timeouts
            page = self.context.new_page()
            self.page = cast(PageType, page)
            if not self.page:
                return False
                
            # Set timeouts
            self.page.set_default_timeout(Config.SELENIUM_TIMEOUT * 1000)
            self.page.set_default_navigation_timeout(Config.SELENIUM_TIMEOUT * 1000)
            
            # Add sophisticated JavaScript to evade bot detection
            self.page.add_init_script("""
                // Advanced bot detection evasion
                (() => {
                    // Override WebDriver property
                    Object.defineProperty(navigator, 'webdriver', { get: () => false });
                    
                    // Add plugins to appear like a normal browser
                    if (navigator.plugins.length === 0) {
                        Object.defineProperty(navigator, 'plugins', { 
                            get: () => [
                                { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer' },
                                { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai' },
                                { name: 'Native Client', filename: 'internal-nacl-plugin' }
                            ] 
                        });
                    }
                    
                    // Add language preferences
                    Object.defineProperty(navigator, 'languages', { 
                        get: () => ['ar-EG', 'ar', 'en-US', 'en'] 
                    });
                    
                    // Fake user interaction
                    const createFakeMouseMovement = () => {
                        const events = ['mousemove', 'mousedown', 'mouseup', 'mouseover'];
                        const randomEvent = events[Math.floor(Math.random() * events.length)];
                        const x = Math.floor(Math.random() * window.innerWidth);
                        const y = Math.floor(Math.random() * window.innerHeight);
                        
                        const event = new MouseEvent(randomEvent, {
                            view: window,
                            bubbles: true,
                            cancelable: true,
                            clientX: x,
                            clientY: y
                        });
                        document.dispatchEvent(event);
                    };
                    
                    // Random scroll behavior
                    const randomScroll = () => {
                        if (Math.random() > 0.7) {
                            window.scrollBy({
                                top: (Math.random() - 0.5) * 100,
                                behavior: 'smooth'
                            });
                        }
                    };
                    
                    // Simulate human-like behavior with random intervals
                    setInterval(createFakeMouseMovement, 500 + Math.random() * 1000);
                    setInterval(randomScroll, 2000 + Math.random() * 3000);
                    
                    // Fix broken image loading
                    setTimeout(() => {
                        document.querySelectorAll('img').forEach(img => {
                            if (!img.complete || img.naturalHeight === 0) {
                                if (img.dataset.src) img.src = img.dataset.src;
                                if (img.dataset.original) img.src = img.dataset.original;
                            }
                        });
                    }, 1000);
                })();
            """)
            
            return True
        except Exception as e:
            print(f"❌ Failed to create Playwright browser: {e}")
            self.cleanup()
            return False
            
    def cleanup(self):
        """Clean up Playwright resources"""
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
            print(f"⚠️ Playwright cleanup warning: {e}")
            
    def get_page(self, url: str) -> bool:
        """Navigate to a URL with enhanced error handling and anti-bot measures"""
        try:
            if not self.page:
                return False
                
            # Add random delay before navigation (human-like)
            time.sleep(random.uniform(1.5, 3.0))
            
            # Clear cookies and cache before navigation
            if self.context:
                self.context.clear_cookies()
            
            # Navigate with intelligent retry logic
            max_attempts = 3
            for attempt in range(max_attempts):
                try:
                    # Navigate with longer timeout and wait for network idle
                    response = self.page.goto(
                        url,
                        wait_until='networkidle',
                        timeout=Config.SELENIUM_TIMEOUT * 1000
                    )
                    
                    if response and response.ok:
                        # Perform human-like interaction after page load
                        self._perform_human_interaction()
                        return True
                    elif response and response.status == 429:
                        print(f"⚠️ Rate limited (HTTP 429) for URL: {url}")
                        # Implement exponential backoff for rate limiting
                        cooldown = (attempt + 1) * 10  # 10, 20, 30 seconds
                        print(f"⏳ Cooling down for {cooldown} seconds before retry...")
                        time.sleep(cooldown)
                        if attempt < max_attempts - 1:
                            continue
                        return False
                    elif response and response.status >= 400:
                        print(f"⚠️ HTTP error {response.status} for URL: {url}")
                        if attempt < max_attempts - 1:
                            time.sleep(random.uniform(3, 6))
                            continue
                        return False
                    else:
                        if attempt < max_attempts - 1:
                            time.sleep(random.uniform(2, 4))
                            continue
                        return False
                except Exception as e:
                    if attempt < max_attempts - 1:
                        print(f"⚠️ Retrying navigation after error: {e}")
                        time.sleep(random.uniform(2, 4))
                        continue
                    print(f"⚠️ Navigation failed: {e}")
                    return False
            
            return False
        except Exception as e:
            print(f"⚠️ Playwright navigation error: {e}")
            return False
            
    def _perform_human_interaction(self):
        """Perform random human-like interactions on the page"""
        try:
            if not self.page:
                return
                
            # Wait a bit for the page to stabilize
            time.sleep(random.uniform(0.5, 1.5))
            
            # Perform random scrolling
            self.page.evaluate("""() => {
                const scrollSteps = Math.floor(Math.random() * 3) + 2;
                const maxScrollY = document.body.scrollHeight;
                
                let currentStep = 0;
                const scrollDown = () => {
                    if (currentStep >= scrollSteps) {
                        // Scroll back up a bit
                        window.scrollTo({
                            top: Math.max(0, window.scrollY - Math.random() * 300),
                            behavior: 'smooth'
                        });
                        return;
                    }
                    
                    const nextY = Math.min(
                        maxScrollY,
                        window.scrollY + (window.innerHeight * (Math.random() * 0.4 + 0.6))
                    );
                    
                    window.scrollTo({
                        top: nextY,
                        behavior: 'smooth'
                    });
                    
                    currentStep++;
                    setTimeout(scrollDown, Math.random() * 500 + 500);
                };
                
                scrollDown();
            }""")
            
            # Random delay after scrolling
            time.sleep(random.uniform(0.5, 1))
            
        except Exception as e:
            print(f"⚠️ Error during human interaction simulation: {e}")
            
    def wait_for_images(self, timeout: float = 20.0):
        """Wait for images to load with advanced Playwright optimizations"""
        try:
            if not self.page:
                return
                
            # Wait for network to be idle
            self.page.wait_for_load_state('networkidle', timeout=timeout * 1000)
            
            # Intelligent scroll pattern to trigger lazy loading
            self.page.evaluate("""() => {
                return new Promise((resolve) => {
                    const scrollStep = window.innerHeight / 3;
                    const totalHeight = document.body.scrollHeight;
                    let currentPosition = 0;
                    
                    const scroll = () => {
                        if (currentPosition >= totalHeight) {
                            window.scrollTo(0, 0);
                            setTimeout(resolve, 300);
                            return;
                        }
                        
                        currentPosition += scrollStep;
                        window.scrollTo({
                            top: currentPosition,
                            behavior: 'smooth'
                        });
                        
                        // Random delay between 200ms and 500ms
                        setTimeout(scroll, Math.random() * 300 + 200);
                    };
                    
                    scroll();
                });
            }""")
            
            # Wait for images to be loaded with a timeout
            try:
                self.page.evaluate("""() => {
                    return new Promise((resolve, reject) => {
                        // Get all images that are not loaded yet
                        const images = Array.from(document.images)
                            .filter(img => !img.complete);
                        
                        // If no images or all images are loaded, resolve immediately
                        if (images.length === 0) {
                            resolve();
                            return;
                        }
                        
                        // Set a timeout to avoid waiting forever
                        const timeout = setTimeout(() => {
                            resolve(); // Resolve anyway after timeout
                        }, 5000);
                        
                        // Count loaded images
                        let loadedCount = 0;
                        
                        // Add load and error event listeners to each image
                        images.forEach(img => {
                            img.addEventListener('load', imageLoaded);
                            img.addEventListener('error', imageLoaded);
                        });
                        
                        function imageLoaded() {
                            loadedCount++;
                            if (loadedCount === images.length) {
                                clearTimeout(timeout);
                                resolve();
                            }
                        }
                    });
                }""")
            except Exception as e:
                print(f"⚠️ Some images didn't load, continuing anyway: {e}")
            
            # Trigger lazy loading for common patterns
            self.page.evaluate("""() => {
                // Common lazy loading attributes
                const lazyAttributes = ['data-src', 'data-original', 'data-lazy', 'data-srcset', 'data-original-src'];
                
                // Process all images with lazy attributes
                document.querySelectorAll('img').forEach(img => {
                    // Check for lazy loading attributes
                    for (const attr of lazyAttributes) {
                        if (img.hasAttribute(attr)) {
                            const value = img.getAttribute(attr);
                            if (value) {
                                img.src = value;
                                break;
                            }
                        }
                    }
                    
                    // Fix broken images
                    if (!img.complete || img.naturalHeight === 0) {
                        img.style.visibility = 'visible';
                    }
                });
                
                // Dispatch events that might trigger lazy loading
                ['scroll', 'resize', 'lazyloaded', 'appear'].forEach(eventName => {
                    window.dispatchEvent(new Event(eventName));
                });
            }""")
            
        except Exception as e:
            print(f"⚠️ Error waiting for images: {e}")
            
    def find_elements(self, selector: str) -> List[Any]:
        """Find elements using Playwright's selector engine with error handling"""
        try:
            if not self.page:
                return []
                
            # Use a timeout to avoid hanging
            return self.page.query_selector_all(selector)
        except Exception as e:
            print(f"⚠️ Error finding elements with selector '{selector}': {e}")
            return []
            
    def get_attribute(self, element: Any, attribute: str) -> str:
        """Get element attribute with Playwright with enhanced handling"""
        try:
            if not element:
                return ''
                
            if attribute == 'src':
                # Try multiple possible image source attributes
                for attr in ['src', 'data-src', 'data-original', 'data-lazy']:
                    value = element.get_attribute(attr)
                    if value and not value.startswith('data:'):
                        return value
                return ''
            elif attribute == 'textContent':
                return element.text_content() or ''
            elif attribute == 'innerHTML':
                return element.inner_html() or ''
            else:
                return element.get_attribute(attribute) or ''
        except Exception as e:
            print(f"⚠️ Error getting attribute '{attribute}': {e}")
            return ''
            
    def execute_script(self, script: str, *args) -> Any:
        """Execute JavaScript in the page with enhanced error handling"""
        try:
            if not self.page:
                return None
                
            return self.page.evaluate(script, *args)
        except Exception as e:
            print(f"⚠️ Error executing script: {e}")
            return None
            
    def extract_product_data(self) -> Dict[str, Any]:
        """Extract product data from the current page"""
        try:
            if not self.page:
                return {}
                
            product_data = {
                'name': None,
                'price': None,
                'description': None,
                'meta': {}
            }
            
            # Helper function to clean product names
            def clean_product_name(name):
                if not name:
                    return None
                    
                # Remove common unwanted text
                unwanted_phrases = [
                    "اختر موقع التوصيل",
                    "اختر الموقع",
                    "حدد موقع التوصيل",
                    "اختيار الموقع"
                ]
                
                for phrase in unwanted_phrases:
                    name = name.replace(phrase, "").strip()
                    
                # Remove extra whitespace
                name = re.sub(r'\s+', ' ', name).strip()
                return name if name else None
            
            # Try to extract product data directly from JavaScript on the page
            try:
                js_data = self.page.evaluate("""() => {
                    // Try to find product name in various data structures
                    const extractProductData = () => {
                        // Check for product name in meta tags
                        const metaTags = {
                            title: document.querySelector('meta[property="og:title"]')?.content,
                            name: document.querySelector('meta[name="product:name"]')?.content || 
                                  document.querySelector('meta[property="product:name"]')?.content
                        };
                        
                        // Check for structured data
                        let structuredData = null;
                        try {
                            const jsonLdElements = document.querySelectorAll('script[type="application/ld+json"]');
                            for (const element of jsonLdElements) {
                                const data = JSON.parse(element.textContent);
                                if (data['@type'] === 'Product' || data['@type'] === 'ProductPage') {
                                    structuredData = data;
                                    break;
                                }
                            }
                        } catch(e) {}
                        
                        // Check for product data in window object
                        let windowData = null;
                        try {
                            if (window.product) windowData = window.product;
                            else if (window.Product) windowData = window.Product;
                            else if (window.productData) windowData = window.productData;
                        } catch(e) {}
                        
                        return {
                            metaTags,
                            structuredData,
                            windowData,
                            h1Text: document.querySelector('h1')?.textContent?.trim()
                        };
                    };
                    
                    return extractProductData();
                }""")
                
                if js_data:
                    # Try to extract product name from JavaScript data
                    if not product_data['name']:
                        # Check structured data first
                        if js_data.get('structuredData') and js_data['structuredData'].get('name'):
                            product_data['name'] = clean_product_name(js_data['structuredData']['name'])
                        
                        # Then check meta tags
                        elif js_data.get('metaTags'):
                            if js_data['metaTags'].get('name'):
                                product_data['name'] = clean_product_name(js_data['metaTags']['name'])
                            elif js_data['metaTags'].get('title'):
                                product_data['name'] = clean_product_name(js_data['metaTags']['title'])
                        
                        # Then check window data
                        elif js_data.get('windowData') and js_data['windowData'].get('name'):
                            product_data['name'] = clean_product_name(js_data['windowData']['name'])
                        
                        # Finally check h1 text
                        elif js_data.get('h1Text'):
                            product_data['name'] = clean_product_name(js_data['h1Text'])
            except Exception as e:
                print(f"⚠️ Error extracting JS data: {e}")
            
            # Extract name from h1.header-extra (primary product title)
            if not product_data['name']:
                try:
                    product_title = self.page.query_selector('h1.header-extra')
                    if product_title:
                        product_data['name'] = clean_product_name(product_title.text_content().strip())
                except Exception:
                    pass
                
            # Fallback to other name selectors if h1.header-extra didn't work
            if not product_data['name']:
                for selector in Config.DATA_SELECTORS['name']:
                    try:
                        element = self.page.query_selector(selector)
                        if element:
                            product_data['name'] = clean_product_name(element.text_content().strip())
                        if product_data['name']:
                            break
                    except Exception:
                        continue
            
            # Extract price
            for selector in Config.DATA_SELECTORS['price']:
                try:
                    element = self.page.query_selector(selector)
                    if element:
                        product_data['price'] = element.text_content().strip()
                    if product_data['price']:
                        break
                except Exception:
                    continue
            
            # Extract description
            for selector in Config.DATA_SELECTORS['description']:
                try:
                    element = self.page.query_selector(selector)
                    if element:
                        try:
                            product_data['description'] = element.inner_html().strip()
                        except Exception:
                            product_data['description'] = element.text_content().strip()
                    if product_data['description']:
                        break
                except Exception:
                    continue
            
            # Extract page title and URL for metadata
            try:
                page_title = self.page.title()
                product_data['title'] = page_title
                product_data['url'] = self.page.url
                product_data['meta']['page_title'] = page_title
                
                # Use page title as fallback for product name if needed
                if not product_data['name'] and page_title:
                    # Extract product name from page title (usually format: "Product Name - Chefaa")
                    title_parts = page_title.split(' - ')
                    if len(title_parts) > 1:
                        product_data['name'] = clean_product_name(title_parts[0])
                    else:
                        product_data['name'] = clean_product_name(page_title)
            except Exception:
                pass
                
            return product_data
            
        except Exception as e:
            print(f"⚠️ Error extracting product data: {e}")
            return {}
    
    def extract_all_image_urls(self) -> List[Dict[str, Any]]:
        """Extract all image URLs from the page using advanced techniques"""
        try:
            if not self.page:
                return []
                
            # Use JavaScript to extract all possible image URLs
            image_data = self.page.evaluate(r"""() => {
                const results = [];
                
                // Helper to check if URL is likely an image
                const isLikelyImageUrl = (url) => {
                    if (!url || url.startsWith('data:') || url.length < 10) return false;
                    
                    const imageExtensions = ['jpg', 'jpeg', 'png', 'webp', 'gif', 'bmp'];
                    const imageKeywords = ['image', 'img', 'photo', 'picture', 'product', 'uploads', 'cdn'];
                    
                    // Check for image extensions
                    const hasImageExtension = imageExtensions.some(ext => 
                        url.toLowerCase().includes('.' + ext)
                    );
                    
                    // Check for image-related keywords
                    const hasImageKeyword = imageKeywords.some(keyword => 
                        url.toLowerCase().includes(keyword)
                    );
                    
                    return hasImageExtension || hasImageKeyword;
                };
                
                // Process all images on the page
                document.querySelectorAll('img').forEach((img, index) => {
                    // Get all possible image source attributes
                    const sources = [];
                    
                    // Check standard attributes
                    if (img.src && !img.src.startsWith('data:')) sources.push({url: img.src, type: 'src'});
                    
                    // Check data attributes
                    ['data-src', 'data-original', 'data-lazy', 'data-lazy-src'].forEach(attr => {
                        if (img.getAttribute(attr) && !img.getAttribute(attr).startsWith('data:')) {
                            sources.push({url: img.getAttribute(attr), type: attr});
                        }
                    });
                    
                    // Check srcset
                    if (img.srcset) {
                        const srcsetUrls = img.srcset.split(',')
                            .map(src => src.trim().split(' ')[0])
                            .filter(url => url && !url.startsWith('data:'));
                        
                        srcsetUrls.forEach(url => {
                            sources.push({url, type: 'srcset'});
                        });
                    }
                    
                    // Get image dimensions if available
                    const width = img.naturalWidth || img.width || 0;
                    const height = img.naturalHeight || img.height || 0;
                    
                    // Get alt text for relevance checking
                    const alt = img.alt || '';
                    
                    // Check if image is visible
                    const rect = img.getBoundingClientRect();
                    const isVisible = rect.width > 0 && rect.height > 0;
                    
                    // Add each source to results
                    sources.forEach(source => {
                        if (isLikelyImageUrl(source.url)) {
                            results.push({
                                url: source.url,
                                type: source.type,
                                width,
                                height,
                                alt,
                                visible: isVisible,
                                index
                            });
                        }
                    });
                });
                
                // Also extract background images
                document.querySelectorAll('*').forEach(el => {
                    const style = window.getComputedStyle(el);
                    const bgImage = style.backgroundImage;
                    
                    if (bgImage && bgImage !== 'none') {
                        const match = bgImage.match(/url\(['"]?(.*?)['"]?\)/);
                        if (match && match[1] && !match[1].startsWith('data:')) {
                            const url = match[1];
                            if (isLikelyImageUrl(url)) {
                                const rect = el.getBoundingClientRect();
                                results.push({
                                    url,
                                    type: 'background',
                                    width: rect.width || 0,
                                    height: rect.height || 0,
                                    alt: el.getAttribute('aria-label') || '',
                                    visible: rect.width > 0 && rect.height > 0,
                                    index: -1
                                });
                            }
                        }
                    }
                });
                
                return results;
            }""")
            
            # Process and prioritize the results
            found_urls = []
            for item in image_data:
                url = item.get('url', '')
                if not url:
                    continue
                    
                # Calculate priority based on multiple factors
                priority = 0
                
                # Check for product-related keywords in URL
                url_lower = url.lower()
                if 'cdn.chefaa.com' in url_lower:
                    priority += 20
                if 'product' in url_lower:
                    priority += 10
                if 'large' in url_lower or 'original' in url_lower:
                    priority += 5
                
                # Prioritize visible images
                if item.get('visible', False):
                    priority += 5
                
                # Prioritize images with product-related alt text
                alt_text = item.get('alt', '').lower()
                if 'product' in alt_text:
                    priority += 3
                
                # Prioritize larger images
                width = item.get('width', 0)
                height = item.get('height', 0)
                if width >= 300 and height >= 300:
                    priority += 5
                
                found_urls.append({
                    'url': url,
                    'priority': priority,
                    'selector_index': item.get('index', 999),
                    'source': item.get('type', 'unknown'),
                    'width': width,
                    'height': height
                })
            
            # Sort by priority and remove duplicates
            found_urls.sort(key=lambda x: (-x['priority'], x['selector_index']))
            seen_urls = set()
            unique_urls = []
            for item in found_urls:
                if item['url'] not in seen_urls:
                    seen_urls.add(item['url'])
                    unique_urls.append(item)
            
            print(f"Found {len(unique_urls)} unique image URLs")
            return unique_urls
            
        except Exception as e:
            print(f"⚠️ Error extracting image URLs: {e}")
            return []

class EnhancedCSVImageDownloader:
    def __init__(self, csv_file_path=Config.CSV_FILE):
        self.csv_file = csv_file_path
        self.products = []
        self.checkpoint = {'completed_products': set(), 'failed_products': set()}
        self.failed_products = []
        self.lock = threading.Lock()
        self.stats = {
            'total_products': 0,
            'total_processed': 0,
            'successful_downloads': 0,
            'already_exists': 0,
            'errors': 0,
            'not_found': 0,
            'data_extracted': 0,
            'by_category': {},
            'performance': {
                'avg_download_time': 0,
                'avg_processing_time': 0,
                'cache_hits': 0,
                'cache_misses': 0,
                'total_retries': 0
            },
            'image_sources': {
                'primary_selector': 0,
                'fallback_selector': 0,
                'lazy_loaded': 0,
                'url_extraction': 0
            },
            'start_time': None,
            'end_time': None
        }
        self.url_cache = {}
        self.processed_count = 0
        self.last_memory_clear = time.time()
        self.current_batch_size = Config.BATCH_SIZE
        self.current_workers = Config.MAX_WORKERS
        self.success_streak = 0
        self.error_streak = 0
        self.error_counts = {}
        
        # Setup logging and directories
        self.setup_logging()
        self.setup_directories()
        
        # Create default image if needed
        if Config.USE_DEFAULT_IMAGE and Config.CREATE_DEFAULT_IMAGE:
            self.create_default_image()
        
        # Load checkpoint
        self.checkpoint = self.load_checkpoint()
        
        # Setup session
        self.session = requests.Session()
        self.setup_session()
    
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
    
    def setup_directories(self):
        """Create necessary directories for output and logs"""
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
        """Convert string to safe filename by removing invalid characters"""
        # Replace invalid characters with underscore
        invalid_chars = r'[<>:"/\\|?*\x00-\x1F]'
        sanitized = re.sub(invalid_chars, '_', filename)
        # Remove leading/trailing periods and spaces
        sanitized = sanitized.strip('. ')
        # Use default if empty
        if not sanitized:
            sanitized = 'unknown'
        return sanitized
    
    def load_checkpoint(self):
        """Load checkpoint data from file to resume previous download"""
        checkpoint = {'completed_products': set(), 'failed_products': set()}
        try:
            if os.path.exists(Config.CHECKPOINT_FILE):
                with open(Config.CHECKPOINT_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    checkpoint['completed_products'] = set(data.get('completed_products', []))
                    checkpoint['failed_products'] = set(data.get('failed_products', []))
                print(f"✅ Loaded checkpoint with {len(checkpoint['completed_products'])} completed and {len(checkpoint['failed_products'])} failed products")
            else:
                print("ℹ️ No checkpoint file found, starting fresh")
        except Exception as e:
            print(f"⚠️ Error loading checkpoint: {e}")
        return checkpoint
    
    def get_cached_url(self, url):
        """Get cached download result for URL if available"""
        if not Config.ENABLE_URL_CACHE:
            return None
            
        url_hash = hashlib.md5(url.encode()).hexdigest()
        if url_hash in self.url_cache:
            with self.lock:
                self.stats['performance']['cache_hits'] += 1
            return self.url_cache[url_hash]
        
        with self.lock:
            self.stats['performance']['cache_misses'] += 1
        return None
        
    def cache_url(self, url, result):
        """Cache download result for URL"""
        if not Config.ENABLE_URL_CACHE:
            return
            
        # Limit cache size
        if len(self.url_cache) >= Config.URL_CACHE_SIZE:
            # Remove random 10% of cache when full
            keys_to_remove = random.sample(list(self.url_cache.keys()), 
                                          int(Config.URL_CACHE_SIZE * 0.1))
            for key in keys_to_remove:
                self.url_cache.pop(key, None)
                
        url_hash = hashlib.md5(url.encode()).hexdigest()
        self.url_cache[url_hash] = result
    
    def validate_downloaded_image(self, filepath):
        """Validate that downloaded file is a valid image"""
        try:
            # Check file exists
            if not os.path.exists(filepath):
                return False, "file_not_found"
                
            # Check file size
            file_size = os.path.getsize(filepath)
            if file_size == 0:
                return False, "empty_file"
            if file_size > Config.MAX_IMAGE_SIZE:
                return False, "file_too_large"
                
            # Try to open as image
            with Image.open(filepath) as img:
                width, height = img.size
                
                # Check dimensions - but allow small images if configured
                if width < Config.MIN_IMAGE_SIZE or height < Config.MIN_IMAGE_SIZE:
                    if Config.ACCEPT_SMALL_IMAGES:
                        # Accept small images but log a warning
                        self.debug_log(f"Warning: Small image accepted {width}x{height}")
                        return True, f"small_image_accepted_{width}x{height}"
                    else:
                        return False, f"image_too_small_{width}x{height}"
                    
                # Check format
                if img.format and img.format.lower() not in [fmt.lower() for fmt in Config.SUPPORTED_FORMATS]:
                    return False, f"unsupported_format_{img.format}"
                
                return True, "valid_image"
        except Exception as e:
            return False, f"validation_error_{str(e)}"
    
    def get_retry_delay(self, attempt):
        """Calculate adaptive retry delay based on attempt number and settings"""
        base_min, base_max = Config.RETRY_DELAY
        
        if Config.ADAPTIVE_RETRY:
            # Increase delay with each attempt
            factor = min(Config.MAX_RETRY_MULTIPLIER, 1 + (attempt * 0.5))
            min_delay = base_min * factor
            max_delay = base_max * factor
        else:
            min_delay, max_delay = base_min, base_max
            
        # Add jitter for more human-like behavior
        delay = min_delay + (random.random() * (max_delay - min_delay))
        
        with self.lock:
            self.stats['performance']['total_retries'] += 1
            
        return delay
    
    def create_browser(self, use_fallback=False):
        """Create and configure browser instance with appropriate automation"""
        browser_type = Config.BROWSER_AUTOMATION
        
        # Use fallback if requested
        if use_fallback and Config.BROWSER_FALLBACK:
            if browser_type == 'playwright':
                browser_type = 'selenium'
            else:
                browser_type = 'playwright'
        
        # Try to create browser
        try:
            if browser_type == 'playwright' and PLAYWRIGHT_AVAILABLE:
                self.debug_log("Creating Playwright browser")
                browser = PlaywrightBrowser()
                if browser.create():
                    return browser
                else:
                    self.debug_log("Failed to create Playwright browser")
                    if not use_fallback and Config.BROWSER_FALLBACK:
                        self.debug_log("Falling back to Selenium")
                        return self.create_browser(use_fallback=True)
                    return None
            else:
                self.debug_log("Creating Selenium browser")
                options = webdriver.ChromeOptions()
                options.add_argument('--headless')
                options.add_argument('--no-sandbox')
                options.add_argument('--disable-dev-shm-usage')
                options.add_argument('--disable-gpu')
                options.add_argument('--disable-extensions')
                options.add_argument('--disable-infobars')
                options.add_argument('--mute-audio')
                options.add_argument(f'user-agent={random.choice(Config.USER_AGENTS)}')
                
                browser = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
                browser.set_page_load_timeout(Config.SELENIUM_TIMEOUT)
                browser.set_script_timeout(Config.SELENIUM_TIMEOUT)
                
                return browser
        except Exception as e:
            self.debug_log(f"Error creating browser: {e}")
            if not use_fallback and Config.BROWSER_FALLBACK:
                self.debug_log("Falling back to alternate browser")
                return self.create_browser(use_fallback=True)
            return None
    
    def wait_for_images_to_load(self, driver, timeout=20):
        """Wait for images to load in Selenium browser"""
        try:
            # Scroll to trigger lazy loading
            driver.execute_script("""
                window.scrollTo(0, 0);
                const scrollHeight = document.body.scrollHeight;
                const scrollStep = window.innerHeight / 2;
                let currentPosition = 0;
                
                function scrollDown() {
                    if (currentPosition < scrollHeight) {
                        currentPosition += scrollStep;
                        window.scrollTo(0, currentPosition);
                    } else {
                        window.scrollTo(0, 0);
                    }
                }
                
                // Scroll down in steps
                for (let i = 0; i < 5; i++) {
                    setTimeout(scrollDown, i * 300);
                }
            """)
            
            # Wait for images to be present
            for selector in Config.IMAGE_SELECTORS[:5]:  # Try first 5 selectors
                try:
                    WebDriverWait(driver, timeout / 4).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    break
                except Exception:
                    continue
            
            # Wait a bit more for images to load
            time.sleep(2)
            
        except Exception as e:
            self.debug_log(f"Error waiting for images: {e}")
    
    def extract_image_urls(self, browser, product_url):
        """Extract image URLs from page with priority ranking"""
        try:
            image_urls = []
            
            # Handle different browser types
            if isinstance(browser, PlaywrightBrowser):
                # Use Playwright's advanced extraction
                image_urls = browser.extract_all_image_urls()
            else:
                # Use Selenium extraction
                # First try with specific selectors
                for idx, selector in enumerate(Config.IMAGE_SELECTORS):
                    try:
                        elements = browser.find_elements(By.CSS_SELECTOR, selector)
                        if elements:
                            for element in elements:
                                try:
                                    # Try multiple attributes
                                    for attr in ['src', 'data-src', 'data-original']:
                                        url = element.get_attribute(attr)
                                        if url and not url.startswith('data:'):
                                            image_urls.append({
                                                'url': url,
                                                'priority': 100 - idx,  # Higher priority for earlier selectors
                                                'selector_index': idx,
                                                'source': attr,
                                                'width': 0,
                                                'height': 0
                                            })
                                            break
                                except Exception:
                                    continue
                    except Exception:
                        continue
                
                # Then try JavaScript extraction as fallback
                try:
                    js_images = browser.execute_script("""
                        const images = [];
                        document.querySelectorAll('img').forEach((img, index) => {
                            if (img.src && !img.src.startsWith('data:')) {
                                images.push({
                                    url: img.src,
                                    width: img.naturalWidth || img.width || 0,
                                    height: img.naturalHeight || img.height || 0,
                                    alt: img.alt || '',
                                    index: index
                                });
                            }
                            if (img.dataset.src && !img.dataset.src.startsWith('data:')) {
                                images.push({
                                    url: img.dataset.src,
                                    width: img.naturalWidth || img.width || 0,
                                    height: img.naturalHeight || img.height || 0,
                                    alt: img.alt || '',
                                    index: index
                                });
                            }
                        });
                        return images;
                    """)
                    
                    if js_images:
                        for idx, img in enumerate(js_images):
                            # Calculate priority based on image properties
                            priority = 30  # Base priority for JS-extracted images
                            
                            # Prioritize by size if available
                            width = img.get('width', 0)
                            height = img.get('height', 0)
                            if width >= 300 and height >= 300:
                                priority += 10
                                
                            # Prioritize by alt text
                            alt = img.get('alt', '').lower()
                            if 'product' in alt:
                                priority += 5
                                
                            # Add to results
                            image_urls.append({
                                'url': img['url'],
                                'priority': priority,
                                'selector_index': img.get('index', idx),
                                'source': 'js',
                                'width': width,
                                'height': height
                            })
                except Exception as e:
                    self.debug_log(f"Error extracting JS images: {e}")
            
            # Filter and deduplicate URLs
            unique_urls = []
            seen_urls = set()
            
            for img in image_urls:
                url = img['url']
                if not url or url in seen_urls:
                    continue
                    
                # Clean and normalize URL
                if url.startswith('//'):
                    url = 'https:' + url
                elif url.startswith('/'):
                    parsed = urlparse(product_url)
                    base = f"{parsed.scheme}://{parsed.netloc}"
                    url = urljoin(base, url)
                
                # Skip common UI elements and icons that are often small
                lower_url = url.lower()
                if any(pattern in lower_url for pattern in ['close-icon', 'user-register', 'filter.png', 'icon', 'logo']):
                    # Skip UI elements but keep track for debugging
                    self.debug_log(f"Skipping UI element: {url}")
                    continue
                
                img['url'] = url
                seen_urls.add(url)
                
                # Boost priority for known patterns
                for pattern in Config.PRIORITY_URL_PATTERNS:
                    if re.search(pattern, url, re.IGNORECASE):
                        img['priority'] += 20
                        break
                
                unique_urls.append(img)
            
            # Sort by priority
            unique_urls.sort(key=lambda x: -x['priority'])
            
            return unique_urls
            
        except Exception as e:
            self.debug_log(f"Error extracting image URLs: {e}")
            return []
    
    def save_product_data(self, product_data, product):
        """Save extracted product data to JSON file"""
        try:
            # Create directory for product data if it doesn't exist
            category_dir = os.path.join(Config.OUTPUT_DIR, product['category'])
            data_dir = os.path.join(category_dir, 'data')
            os.makedirs(data_dir, exist_ok=True)
            
            # Create filename based on product ID
            filename = os.path.join(data_dir, f"{product['product_id']}.json")
            
            # Helper function to convert HTML to plain text
            def html_to_plain_text(html_content):
                if not html_content:
                    return None
                
                # Remove HTML tags
                text = re.sub(r'<h[1-6][^>]*>', '\n\n', html_content)  # Replace headers with newlines
                text = re.sub(r'</h[1-6]>', '', text)
                text = re.sub(r'<br\s*/?>', '\n', text)  # Replace <br> with newline
                text = re.sub(r'<li[^>]*>', '\n• ', text)  # Replace list items with bullet points
                text = re.sub(r'</li>', '', text)
                text = re.sub(r'<ul[^>]*>', '\n', text)  # Add newline before lists
                text = re.sub(r'</ul>', '\n', text)
                text = re.sub(r'<p[^>]*>', '\n', text)  # Replace paragraphs with newlines
                text = re.sub(r'</p>', '\n', text)
                text = re.sub(r'<div[^>]*>', '\n', text)
                text = re.sub(r'</div>', '\n', text)
                
                # Remove all remaining HTML tags
                text = re.sub(r'<[^>]*>', '', text)
                
                # Fix spacing issues
                text = re.sub(r'\n{3,}', '\n\n', text)  # Replace multiple newlines with just two
                text = re.sub(r' {2,}', ' ', text)  # Replace multiple spaces with one
                
                return text.strip()
            
            # Process description to convert from HTML to plain text
            description = html_to_plain_text(product_data.get('description'))
            
            # Structure the data in a professional format
            formatted_data = {
                "product_info": {
                    "id": product['product_id'],
                    "category": product['category'],
                    "url": product['url'],
                    "extracted_at": datetime.now().isoformat()
                },
                "metadata": {
                    "scraper_version": "1.0.0",
                    "source": "chefaa.com"
                },
                "content": {
                    "name": product_data.get('name'),
                    "price": product_data.get('price'),
                    "description": description,
                    "title": product_data.get('title', product_data.get('name')),
                    "attributes": product_data.get('meta', {})
                }
            }
            
            # Write to file with proper indentation
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(formatted_data, f, ensure_ascii=False, indent=2)
            
            # Also save a plain text version for easy reading
            txt_filename = os.path.join(data_dir, f"{product['product_id']}.txt")
            with open(txt_filename, 'w', encoding='utf-8') as f:
                f.write(f"Product: {product_data.get('name', 'N/A')}\n")
                f.write(f"Title: {product_data.get('title', 'N/A')}\n")
                f.write(f"Price: {product_data.get('price', 'N/A')}\n")
                f.write(f"URL: {product['url']}\n")
                f.write(f"Category: {product['category']}\n")
                f.write(f"ID: {product['product_id']}\n\n")
                f.write("=" * 80 + "\n\n")
                f.write("DESCRIPTION:\n\n")
                f.write(description if description else "No description available")
                f.write("\n\n" + "=" * 80)
                
            return True
        except Exception as e:
            self.debug_log(f"Error saving product data: {e}")
            return False
    
    def run(self):
        """Main method to run the downloader"""
        try:
            print(f"🔍 Reading products from {self.csv_file}")
            self.stats['start_time'] = datetime.now()
            
            # Read products from CSV
            if not os.path.exists(self.csv_file):
                print(f"❌ CSV file not found: {self.csv_file}")
                return False
                
            with open(self.csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Normalize product data - match actual CSV format
                    product = {
                        'product_id': row.get('Product_ID', '').strip(),
                        'url': row.get('Product_URL', '').strip(),
                        'category': self.sanitize_filename(row.get('Category', 'unknown').strip()),
                        'extracted_at': row.get('Extracted_At', '')
                    }
                    
                    # Skip products without ID or URL
                    if not product['product_id'] or not product['url']:
                        continue
                        
                    self.products.append(product)
                    
                    # Initialize category stats if needed
                    if product['category'] not in self.stats['by_category']:
                        self.stats['by_category'][product['category']] = {
                            'total': 0,
                            'success': 0,
                            'errors': 0,
                            'exists': 0,
                            'data_extracted': 0
                        }
                    self.stats['by_category'][product['category']]['total'] += 1
            
            self.stats['total_products'] = len(self.products)
            print(f"📊 Found {self.stats['total_products']} products in {len(self.stats['by_category'])} categories")
            
            # Process products in batches with multiple threads
            with tqdm(total=self.stats['total_products'], desc="Downloading images") as pbar:
                for i in range(0, len(self.products), Config.BATCH_SIZE):
                    batch = self.products[i:i + Config.BATCH_SIZE]
                    
                    # Process batch with thread pool
                    with ThreadPoolExecutor(max_workers=Config.MAX_WORKERS) as executor:
                        futures = {executor.submit(self.download_product_images, product): product for product in batch}
                        
                        for future in as_completed(futures):
                            result = future.result()
                            pbar.update(1)
                            
                            # Update progress bar description
                            success_rate = int((self.stats['successful_downloads'] + self.stats['already_exists']) / 
                                              max(1, self.stats['total_processed']) * 100)
                            pbar.set_description(f"Success: {success_rate}% ({self.stats['successful_downloads']} new, {self.stats['already_exists']} exist)")
                    
                    # Save checkpoint after each batch
                    self.save_checkpoint()
                    
                    # Adaptive batch size based on error rate
                    self.adjust_batch_size()
                    
                    # Clear memory periodically
                    if time.time() - self.last_memory_clear > Config.CLEAR_MEMORY_INTERVAL:
                        self.clear_memory()
                    
                    # Add a delay between batches to avoid rate limiting
                    error_rate = self.stats['errors'] / max(1, self.stats['total_processed'])
                    if error_rate > 0.3:  # If more than 30% errors, add longer delay
                        cooldown = random.uniform(15, 30)
                        print(f"⏳ High error rate detected ({error_rate:.1%}). Cooling down for {cooldown:.1f} seconds...")
                        time.sleep(cooldown)
                    else:
                        # Normal delay between batches
                        time.sleep(random.uniform(5, 10))
            
            # Save final results
            self.stats['end_time'] = datetime.now()
            self.save_results()
            
            # Print summary
            duration = self.stats['end_time'] - self.stats['start_time']
            print(f"\n✅ Download completed in {duration}")
            print(f"📊 Summary: {self.stats['successful_downloads']} new downloads, {self.stats['already_exists']} already existed, {self.stats['errors']} errors")
            
            return True
            
        except KeyboardInterrupt:
            print("\n⚠️ Download interrupted by user")
            self.save_checkpoint()
            self.save_results()
            return False
        except Exception as e:
            print(f"❌ Error in download process: {e}")
            self.save_checkpoint()
            return False
    
    def save_checkpoint(self):
        """Save checkpoint to resume download later"""
        try:
            checkpoint_data = {
                'completed_products': list(self.checkpoint['completed_products']),
                'failed_products': list(self.checkpoint['failed_products']),
                'timestamp': datetime.now().isoformat(),
                'stats': self.stats
            }
            
            with open(Config.CHECKPOINT_FILE, 'w', encoding='utf-8') as f:
                json.dump(checkpoint_data, f, default=str)
                
            # Save failed products separately for analysis
            with open(Config.FAILED_PRODUCTS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.failed_products, f, default=str, indent=2)
                
        except Exception as e:
            print(f"⚠️ Error saving checkpoint: {e}")
    
    def save_results(self):
        """Save final results and statistics"""
        try:
            # Create timestamp for results directory
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            results_dir = f"pharmacy_results_{timestamp}"
            os.makedirs(results_dir, exist_ok=True)
            
            # Save summary as JSON with professional structure
            summary_file = os.path.join(results_dir, 'scraping_summary.json')
            
            # Format the stats in a more professional structure
            formatted_stats = {
                "execution_info": {
                    "start_time": self.stats['start_time'].isoformat() if isinstance(self.stats.get('start_time'), datetime) else None,
                    "end_time": self.stats['end_time'].isoformat() if isinstance(self.stats.get('end_time'), datetime) else None,
                    "duration_seconds": (self.stats['end_time'] - self.stats['start_time']).total_seconds() if (isinstance(self.stats.get('start_time'), datetime) and isinstance(self.stats.get('end_time'), datetime)) else None,
                    "timestamp": datetime.now().isoformat()
                },
                "summary": {
                    "total_products": self.stats.get('total_products', 0),
                    "processed": self.stats.get('total_processed', 0),
                    "successful": self.stats.get('successful_downloads', 0),
                    "already_existed": self.stats.get('already_exists', 0),
                    "errors": self.stats.get('errors', 0),
                    "not_found": self.stats.get('not_found', 0),
                    "data_extracted": self.stats.get('data_extracted', 0),
                    "success_rate": round(self.stats.get('successful_downloads', 0) / max(1, self.stats.get('total_processed', 1)) * 100, 2)
                },
                "categories": {
                    category: {
                        "total": stats.get('total', 0),
                        "successful": stats.get('success', 0),
                        "errors": stats.get('errors', 0),
                        "already_existed": stats.get('exists', 0),
                        "data_extracted": stats.get('data_extracted', 0),
                        "success_rate": round(stats.get('success', 0) / max(1, stats.get('total', 1)) * 100, 2)
                    } for category, stats in self.stats.get('by_category', {}).items()
                },
                "performance_metrics": {
                    "average_download_time_ms": self.stats.get('performance', {}).get('avg_download_time', 0),
                    "average_processing_time_ms": self.stats.get('performance', {}).get('avg_processing_time', 0),
                    "cache_hits": self.stats.get('performance', {}).get('cache_hits', 0),
                    "cache_misses": self.stats.get('performance', {}).get('cache_misses', 0),
                    "total_retries": self.stats.get('performance', {}).get('total_retries', 0)
                },
                "image_sources": {
                    "primary_selector": self.stats.get('image_sources', {}).get('primary_selector', 0),
                    "fallback_selector": self.stats.get('image_sources', {}).get('fallback_selector', 0),
                    "lazy_loaded": self.stats.get('image_sources', {}).get('lazy_loaded', 0),
                    "url_extraction": self.stats.get('image_sources', {}).get('url_extraction', 0)
                },
                "configuration": {
                    key: value for key, value in vars(Config).items() 
                    if not key.startswith('__') and not callable(value) and not isinstance(value, (dict, list))
                }
            }
            
            with open(summary_file, 'w', encoding='utf-8') as f:
                json.dump(formatted_stats, f, default=str, indent=2)
                
            # Save all products to CSV
            all_products_file = os.path.join(results_dir, 'all_products_combined.csv')
            with open(all_products_file, 'w', encoding='utf-8', newline='') as f:
                fieldnames = ['Product_URL', 'Category', 'Product_ID', 'Extracted_At', 'Status', 'Image_Path']
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                
                for product in self.products:
                    product_key = f"{product['category']}_{product['product_id']}"
                    status = 'completed' if product_key in self.checkpoint['completed_products'] else 'failed' if product_key in self.checkpoint['failed_products'] else 'not_processed'
                    
                    writer.writerow({
                        'Product_ID': product['product_id'],
                        'Category': product['category'],
                        'Product_URL': product['url'],
                        'Extracted_At': datetime.now().isoformat(),
                        'Status': status,
                        'Image_Path': os.path.join(Config.OUTPUT_DIR, product['category'], f"{product['product_id']}.jpg")
                    })
            
            # Save failed products with more detailed information
            failed_products_file = os.path.join(results_dir, 'failed_products.json')
            if self.failed_products:
                failed_data = {
                    "metadata": {
                        "generated_at": datetime.now().isoformat(),
                        "total_failed": len(self.failed_products)
                    },
                    "failed_products": [
                        {
                            "product_id": item['product'].get('product_id'),
                            "category": item['product'].get('category'),
                            "url": item['product'].get('url'),
                            "error_message": item['error'],
                            "timestamp": item['timestamp']
                        } for item in self.failed_products
                    ]
                }
                
                with open(failed_products_file, 'w', encoding='utf-8') as f:
                    json.dump(failed_data, f, default=str, indent=2)
                    
            print(f"✅ Results saved to {results_dir}")
            
        except Exception as e:
            print(f"⚠️ Error saving results: {e}")
    
    def adjust_batch_size(self):
        """Dynamically adjust batch size and worker count based on error rate"""
        if not Config.ADAPTIVE_RETRY:
            return
            
        error_rate = self.stats['errors'] / max(1, self.stats['total_processed'])
        
        # Increase batch size and workers if doing well
        if error_rate < 0.05 and self.success_streak > 2:
            self.current_batch_size = min(Config.BATCH_SIZE * 2, 50)
            self.current_workers = min(Config.MAX_WORKERS + 2, 10)
            self.success_streak = 0
            print(f"📈 Performance good, increasing batch size to {self.current_batch_size} and workers to {self.current_workers}")
            
        # Decrease if error rate is high
        elif error_rate > 0.2 and self.error_streak > 1:
            self.current_batch_size = max(5, int(Config.BATCH_SIZE * 0.5))
            self.current_workers = max(2, Config.MAX_WORKERS - 1)
            self.error_streak = 0
            print(f"📉 Error rate high, reducing batch size to {self.current_batch_size} and workers to {self.current_workers}")
            
        # Update streaks
        if error_rate < 0.1:
            self.success_streak += 1
            self.error_streak = 0
        elif error_rate > 0.2:
            self.error_streak += 1
            self.success_streak = 0
    
    def clear_memory(self):
        """Clear memory to prevent leaks during long runs"""
        self.last_memory_clear = time.time()
        
        # Clear URL cache if it's too large
        if len(self.url_cache) > Config.URL_CACHE_SIZE * 0.8:
            self.url_cache.clear()
            
        # Force garbage collection
        import gc
        gc.collect()
        
        print("🧹 Memory cleared")
    
    def debug_log(self, message):
        """Write debug messages to log file"""
        if hasattr(self, 'logger'):
            self.logger.debug(message)
        try:
            with open(Config.DEBUG_LOG_FILE, 'a', encoding='utf-8') as f:
                f.write(f"[{datetime.now()}] {message}\n")
        except Exception:
            pass
    
    def setup_session(self):
        """Initialize requests session with headers and retry strategy"""
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
    
    def download_image(self, img_url, product):
        """Download an image from URL with error handling and validation"""
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
            parsed_url = urlparse(img_url)
            path = parsed_url.path
            file_extension = os.path.splitext(path)[1].lower()
            
            if not file_extension or file_extension not in [f'.{ext}' for ext in Config.SUPPORTED_FORMATS]:
                file_extension = '.jpg'
            
            # Create safe filename
            safe_filename = f"{product['product_id']}{file_extension}"
            category_dir = os.path.join(Config.OUTPUT_DIR, product['category'])
            filepath = os.path.join(category_dir, safe_filename)
            
            # Check if file already exists
            if os.path.exists(filepath):
                is_valid, validation_msg = self.validate_downloaded_image(filepath)
                if is_valid:
                    # Cache the successful result
                    self.cache_url(img_url, (filepath, "already_exists"))
                    return filepath, "already_exists"
                else:
                    os.remove(filepath)
            
            # Download with adaptive retries
            for attempt in range(Config.MAX_RETRIES):
                try:
                    # Use streaming to check content type before downloading
                    with self.session.get(
                        img_url,
                        timeout=Config.REQUEST_TIMEOUT,
                        stream=True,
                        allow_redirects=True
                    ) as response:
                        response.raise_for_status()
                        
                        # Check content type early
                        content_type = response.headers.get('content-type', '').lower()
                        if not any(img_type in content_type for img_type in ['image/', 'application/octet-stream']):
                            return None, f"invalid_content_type: {content_type}"
                        
                        # Download with size limit check
                        with open(filepath, 'wb') as f:
                            total_size = 0
                            for chunk in response.iter_content(chunk_size=8192):
                                if chunk:
                                    total_size += len(chunk)
                                    if total_size > Config.MAX_IMAGE_SIZE:
                                        f.close()
                                        os.remove(filepath)
                                        return None, "file_too_large_during_download"
                                    f.write(chunk)
                        
                        # Validate downloaded image
                        is_valid, validation_msg = self.validate_downloaded_image(filepath)
                        if is_valid:
                            # Cache the successful result
                            self.cache_url(img_url, (filepath, "success"))
                            return filepath, "success"
                        else:
                            if os.path.exists(filepath):
                                os.remove(filepath)
                            return None, f"invalid_image: {validation_msg}"
                
                except requests.exceptions.RequestException as e:
                    if attempt < Config.MAX_RETRIES - 1:
                        delay = self.get_retry_delay(attempt)
                        time.sleep(delay)
                        continue
                    return None, f"download_error: {str(e)}"
                except Exception as e:
                    if os.path.exists(filepath):
                        try:
                            os.remove(filepath)
                        except:
                            pass
                    return None, f"unexpected_error: {str(e)}"
            
            return None, "max_retries_exceeded"
            
        except Exception as e:
            return None, f"download_setup_error: {str(e)}"
    
    def download_product_images(self, product):
        """Main method to download images for a single product with browser automation support"""
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
        
        browser = None
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
            # Add random delay before processing each product to avoid rate limiting
            time.sleep(random.uniform(1.5, 3.0))
            
            # Create browser with retry and fallback
            max_browser_attempts = 2
            for browser_attempt in range(max_browser_attempts):
                browser = self.create_browser(use_fallback=(browser_attempt > 0))
                if browser:
                    break
                time.sleep(2)
                
            if not browser:
                result['error'] = "failed_to_create_browser_after_multiple_attempts"
                return result
            
            # Load page with retry
            max_page_attempts = 2
            for page_attempt in range(max_page_attempts):
                try:
                    if isinstance(browser, PlaywrightBrowser):
                        success = browser.get_page(product['url'])
                    else:
                        browser.delete_all_cookies()
                        browser.get(product['url'])
                        success = True
                        
                    if success:
                        delay = random.uniform(*Config.PAGE_LOAD_DELAY)
                        time.sleep(delay)
                        break
                except Exception as e:
                    if page_attempt == max_page_attempts - 1:
                        result['error'] = f"page_load_error: {str(e)}"
                        return result
                    time.sleep(2)
            
            # Wait for images to load
            try:
                if isinstance(browser, PlaywrightBrowser):
                    browser.wait_for_images(Config.SELENIUM_TIMEOUT)
                else:
                    self.wait_for_images_to_load(browser)
            except Exception as e:
                self.debug_log(f"Warning: Error waiting for images: {e}")
            
            # Extract product data if using Playwright
            if isinstance(browser, PlaywrightBrowser):
                try:
                    product_data = browser.extract_product_data()
                    if product_data:
                        result['product_data'] = product_data
                        self.stats['data_extracted'] += 1
                        self.stats['by_category'][product['category']]['data_extracted'] += 1
                        
                        # Save product data
                        self.save_product_data(product_data, product)
                except Exception as e:
                    self.debug_log(f"Error extracting product data: {e}")
            
            # Extract image URLs
            image_urls = self.extract_image_urls(browser, product['url'])
            
            if not image_urls:
                self.debug_log(f"No images found for product {product['product_id']}")
                
                # Use default image if configured
                if Config.USE_DEFAULT_IMAGE:
                    default_image_path = os.path.join(Config.OUTPUT_DIR, Config.DEFAULT_IMAGE_PATH)
                    if os.path.exists(default_image_path):
                        # Copy default image to product location
                        category_dir = os.path.join(Config.OUTPUT_DIR, product['category'])
                        os.makedirs(category_dir, exist_ok=True)
                        
                        # Create safe filename for the product
                        file_extension = os.path.splitext(Config.DEFAULT_IMAGE_PATH)[1].lower()
                        safe_filename = f"{product['product_id']}{file_extension}"
                        filepath = os.path.join(category_dir, safe_filename)
                        
                        # Copy the default image
                        import shutil
                        shutil.copy(default_image_path, filepath)
                        
                        # Update result
                        result['status'] = 'success'
                        result['images_downloaded'] = 1
                        result['image_path'] = filepath
                        result['error'] = None
                        
                        with self.lock:
                            self.stats['successful_downloads'] += 1
                            self.stats['by_category'][product['category']]['success'] += 1
                            
                        # Mark as completed
                        self.checkpoint['completed_products'].add(product_key)
                        
                        return result
                else:
                    result['error'] = 'no_images_found'
                    return result
            
            # Try to download images - only try the top 5 candidates
            downloaded_count = 0
            last_error = None
            image_path = None
            
            for img_info in image_urls[:10]:  # Try up to 10 candidates (increased from 5)
                img_url = img_info['url']
                self.debug_log(f"Attempting to download: {img_url} (priority: {img_info['priority']})")
                
                downloaded_path, download_status = self.download_image(img_url, product)
                
                if downloaded_path and download_status in ['success', 'already_exists', 'small_image_accepted']:
                    downloaded_count += 1
                    image_path = downloaded_path
                    result['images_downloaded'] = downloaded_count
                    result['status'] = 'success'
                    result['image_path'] = image_path
                    
                    with self.lock:
                        if download_status == 'success':
                            self.stats['successful_downloads'] += 1
                            self.stats['by_category'][product['category']]['success'] += 1
                        else:
                            self.stats['already_exists'] += 1
                            self.stats['by_category'][product['category']]['exists'] += 1
                    
                    break  # Success, stop trying other URLs
                else:
                    last_error = download_status
                    continue
            
            if downloaded_count == 0:
                # No image downloaded successfully, try default image as last resort
                if Config.USE_DEFAULT_IMAGE:
                    default_image_path = os.path.join(Config.OUTPUT_DIR, Config.DEFAULT_IMAGE_PATH)
                    if os.path.exists(default_image_path):
                        # Copy default image to product location
                        category_dir = os.path.join(Config.OUTPUT_DIR, product['category'])
                        os.makedirs(category_dir, exist_ok=True)
                        
                        # Create safe filename for the product
                        file_extension = os.path.splitext(Config.DEFAULT_IMAGE_PATH)[1].lower()
                        safe_filename = f"{product['product_id']}{file_extension}"
                        filepath = os.path.join(category_dir, safe_filename)
                        
                        # Copy the default image
                        import shutil
                        shutil.copy(default_image_path, filepath)
                        
                        # Update result
                        result['status'] = 'success'
                        result['images_downloaded'] = 1
                        result['image_path'] = filepath
                        result['error'] = None
                        
                        with self.lock:
                            self.stats['successful_downloads'] += 1
                            self.stats['by_category'][product['category']]['success'] += 1
                            
                        return result
                else:
                    result['error'] = last_error or 'all_downloads_failed'
                    result['status'] = 'failed'
            
        except Exception as e:
            result['error'] = f"unexpected_error: {str(e)}"
            self.debug_log(f"Unexpected error processing {product['url']}: {e}")
        
        finally:
            if browser:
                try:
                    if isinstance(browser, PlaywrightBrowser):
                        browser.cleanup()
                    else:
                        browser.quit()
                except Exception as e:
                    self.debug_log(f"Error cleaning up browser: {e}")
            
            # Update progress
            with self.lock:
                self.stats['total_processed'] += 1
                
                if result['status'] == 'success':
                    self.checkpoint['completed_products'].add(product_key)
                elif result['status'] in ['failed', 'not_found']:
                    if result['status'] == 'failed':
                        self.stats['errors'] += 1
                        self.stats['by_category'][product['category']]['errors'] += 1
                    self.checkpoint['failed_products'].add(product_key)
                    self.failed_products.append({
                        'product': product,
                        'error': result['error'],
                        'timestamp': datetime.now().isoformat()
                    })
        
        return result
    
    def create_default_image(self):
        """Create a default image to use when no valid image is found"""
        try:
            default_image_path = os.path.join(Config.OUTPUT_DIR, Config.DEFAULT_IMAGE_PATH)
            
            # Skip if default image already exists
            if os.path.exists(default_image_path):
                return
                
            # Create a simple colored image with text
            from PIL import Image, ImageDraw, ImageFont
            
            # Create a white image
            width, height = 400, 400
            image = Image.new('RGB', (width, height), color=(255, 255, 255))
            draw = ImageDraw.Draw(image)
            
            # Add a border
            draw.rectangle([(0, 0), (width-1, height-1)], outline=(200, 200, 200), width=2)
            
            # Add text
            try:
                # Try to use a system font
                font = ImageFont.truetype("arial.ttf", 20)
            except:
                # Fallback to default font
                font = ImageFont.load_default()
                
            text = "No Image Available"
            text_width = draw.textlength(text, font=font)
            text_position = ((width - text_width) / 2, height / 2)
            draw.text(text_position, text, fill=(100, 100, 100), font=font)
            
            # Save the image
            os.makedirs(os.path.dirname(default_image_path), exist_ok=True)
            image.save(default_image_path)
            print(f"✅ Created default image: {default_image_path}")
            
        except Exception as e:
            print(f"⚠️ Could not create default image: {e}")

def main():
    print("Inside main()...")
    print("\n🚀 Starting Enhanced CSV Image Downloader (default settings)")
    try:
        # Define global variables
        global sync_playwright, PLAYWRIGHT_AVAILABLE
        
        # Check if Playwright is available and install browsers if needed
        if Config.BROWSER_AUTOMATION == 'playwright':
            if not PLAYWRIGHT_AVAILABLE:
                print("⚠️ Playwright not installed. Installing required packages...")
                try:
                    import subprocess
                    subprocess.check_call(["pip", "install", "playwright"])
                    print("✅ Playwright installed successfully!")
                    print("⚠️ Installing Playwright browsers (this may take a while)...")
                    subprocess.check_call(["playwright", "install", "chromium"])
                    print("✅ Playwright browsers installed successfully!")
                    
                    # Reload the module to make Playwright available
                    from playwright.sync_api import sync_playwright
                    PLAYWRIGHT_AVAILABLE = True
                except Exception as e:
                    print(f"❌ Failed to install Playwright: {e}")
                    print("⚠️ Falling back to Selenium")
                    Config.set_browser_automation('selenium')
            else:
                print("✅ Playwright is available")
                
                # Check if browsers are installed
                try:
                    with sync_playwright() as p:
                        print("✅ Playwright browsers are installed")
                except Exception as e:
                    print(f"⚠️ Playwright browser check failed: {e}")
                    print("⚠️ Installing Playwright browsers (this may take a while)...")
                    try:
                        import subprocess
                        subprocess.check_call(["playwright", "install", "chromium"])
                        print("✅ Playwright browsers installed successfully!")
                    except Exception as e:
                        print(f"❌ Failed to install Playwright browsers: {e}")
                        print("⚠️ Falling back to Selenium")
                        Config.set_browser_automation('selenium')
        
        # Use default config values
        downloader = EnhancedCSVImageDownloader(csv_file_path=Config.CSV_FILE)
        success = downloader.run()
        return 0 if success else 1
    except KeyboardInterrupt:
        print("\n⚠️ Download interrupted by user")
        return 1
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        return 1

if __name__ == "__main__":
    exit(main())
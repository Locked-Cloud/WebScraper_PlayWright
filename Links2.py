import time
import random
import csv
import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, WebDriverException
import requests
from urllib.parse import urljoin, urlparse
import re
from datetime import datetime

# --- Configuration ---
CATEGORIES = [
    "https://chefaa.com:443/eg-ar/now/brands/Ardell",
    "https://chefaa.com:443/eg-ar/now/brands/AZHA",
    "https://chefaa.com:443/eg-ar/now/brands/Betadine",
    "https://chefaa.com:443/eg-ar/now/brands/Penta",
    "https://chefaa.com:443/eg-ar/now/brands/sekem",
    "https://chefaa.com:443/eg-ar/now/brands/ever-pure",
    "https://chefaa.com:443/eg-ar/now/brands/five-fives",
    "https://chefaa.com:443/eg-ar/now/brands/mood",
    "https://chefaa.com:443/eg-ar/now/brands/Blob",
    "https://chefaa.com:443/eg-ar/now/brands/Blue-Bell",
    "https://chefaa.com:443/eg-ar/now/brands/Schwarzkopf",
    "https://chefaa.com:443/eg-ar/now/brands/Byphasse",
    "https://chefaa.com:443/eg-ar/now/brands/finetest",
    "https://chefaa.com:443/eg-ar/now/brands/macks",
    "https://chefaa.com:443/eg-ar/now/brands/man-look",
    "https://chefaa.com:443/eg-ar/now/brands/Capixy",
    "https://chefaa.com:443/eg-ar/now/brands/Depurdent",
    "https://chefaa.com:443/eg-ar/now/brands/palmolive",
    "https://chefaa.com:443/eg-ar/now/brands/papia",
    "https://chefaa.com:443/eg-ar/now/brands/al-burhan",
    "https://chefaa.com:443/eg-ar/now/brands/Bronchicum",
    "https://chefaa.com:443/eg-ar/now/brands/Elevit",
    "https://chefaa.com:443/eg-ar/now/brands/Bisolvon",
    "https://chefaa.com:443/eg-ar/now/brands/Maxilase",
    "https://chefaa.com:443/eg-ar/now/brands/Doliprane",
    "https://chefaa.com:443/eg-ar/now/brands/Nasacort",
    "https://chefaa.com:443/eg-ar/now/brands/Buscopan",
    "https://chefaa.com:443/eg-ar/now/brands/Essentiale",
    "https://chefaa.com:443/eg-ar/now/brands/Enterogermina",
    "https://chefaa.com:443/eg-ar/now/brands/Voltaren",
    "https://chefaa.com:443/eg-ar/now/brands/Otrivin",
    "https://chefaa.com:443/eg-ar/now/brands/Sanofi-Pasteur",
    "https://chefaa.com:443/eg-ar/now/brands/brufen",
    "https://chefaa.com:443/eg-ar/now/brands/Influvac",
    "https://chefaa.com:443/eg-ar/now/brands/The-bathland",
    "https://chefaa.com:443/eg-ar/now/brands/SkinSide",
    "https://chefaa.com:443/eg-ar/now/brands/Nascare",
    "https://chefaa.com:443/eg-ar/now/brands/Acadia",
    "https://chefaa.com:443/eg-ar/now/brands/Bio-Me",
    "https://chefaa.com:443/eg-ar/now/brands/Dermactive",
    "https://chefaa.com:443/eg-ar/now/brands/Mash-Premiere",
    "https://chefaa.com:443/eg-ar/now/brands/The-Hair-Addict",
    "https://chefaa.com:443/eg-ar/now/brands/Omegal-Man",
    "https://chefaa.com:443/eg-ar/now/brands/Aloekita",
    "https://chefaa.com:443/eg-ar/now/brands/Cleopatra",
    "https://chefaa.com:443/eg-ar/now/brands/Drakon",
    "https://chefaa.com:443/eg-ar/now/brands/La-Frutta",
    "https://chefaa.com:443/eg-ar/now/brands/Marvel",
    "https://chefaa.com:443/eg-ar/now/brands/YOLO",
    "https://chefaa.com:443/eg-ar/now/brands/Yara",
    "https://chefaa.com:443/eg-ar/now/brands/Schick",
    "https://chefaa.com:443/eg-ar/now/brands/Favelin",
    "https://chefaa.com:443/eg-ar/now/brands/Banana-Boat",
    "https://chefaa.com:443/eg-ar/now/brands/creme-21",
    "https://chefaa.com:443/eg-ar/now/brands/%D8%A4ybele",
    "https://chefaa.com:443/eg-ar/now/brands/el-sada",
    "https://chefaa.com:443/eg-ar/now/brands/roofa",
    "https://chefaa.com:443/eg-ar/now/brands/bodylicious",
    "https://chefaa.com:443/eg-ar/now/brands/dear",
    "https://chefaa.com:443/eg-ar/now/brands/trio",
    "https://chefaa.com:443/eg-ar/now/brands/twist-go",
    "https://chefaa.com:443/eg-ar/now/brands/estiara",
    "https://chefaa.com:443/eg-ar/now/brands/eucerin",
    "https://chefaa.com:443/eg-ar/now/brands/evony",
    "https://chefaa.com:443/eg-ar/now/brands/future-pharma",
    "https://chefaa.com:443/eg-ar/now/brands/coco",
    "https://chefaa.com:443/eg-ar/now/brands/cordoba",
    "https://chefaa.com:443/eg-ar/now/brands/disaar-beauty",
    "https://chefaa.com:443/eg-ar/now/brands/dazzling-white",
    "https://chefaa.com:443/eg-ar/now/brands/fresh-look",
    "https://chefaa.com:443/eg-ar/now/brands/dabur-herbl",
    "https://chefaa.com:443/eg-ar/now/brands/dago",
    "https://chefaa.com:443/eg-ar/now/brands/maqam",
    "https://chefaa.com:443/eg-ar/now/brands/modish",
    "https://chefaa.com:443/eg-ar/now/brands/stevia",
    "https://chefaa.com:443/eg-ar/now/brands/ossum",
    "https://chefaa.com:443/eg-ar/now/brands/qualita",
    "https://chefaa.com:443/eg-ar/now/brands/potato",
    "https://chefaa.com:443/eg-ar/now/brands/root-ro-rnd",
    "https://chefaa.com:443/eg-ar/now/brands/sanita",
    "https://chefaa.com:443/eg-ar/now/brands/secret",
    "https://chefaa.com:443/eg-ar/now/brands/tola-hair",
    "https://chefaa.com:443/eg-ar/now/brands/Diclopro",
    "https://chefaa.com:443/eg-ar/now/brands/Exeedogast",
    "https://chefaa.com:443/eg-ar/now/brands/Controloc",
    "https://chefaa.com:443/eg-ar/now/brands/Linorose",
    "https://chefaa.com:443/eg-ar/now/brands/Bionorica",
    "https://chefaa.com:443/eg-ar/now/brands/Rennie",
    "https://chefaa.com:443/eg-ar/now/brands/Linex",
    "https://chefaa.com:443/eg-ar/now/brands/Cataflam",
    "https://chefaa.com:443/eg-ar/now/brands/Abimol",
    "https://chefaa.com:443/eg-ar/now/brands/Oplex",
    "https://chefaa.com:443/eg-ar/now/brands/Benmuv",
    "https://chefaa.com:443/eg-ar/now/brands/Sinupret",
    "https://chefaa.com:443/eg-ar/now/brands/Duspatalin",
    "https://chefaa.com:443/eg-ar/now/brands/Nasonex",
    "https://chefaa.com:443/eg-ar/now/brands/Aerius",
    "https://chefaa.com:443/eg-ar/now/brands/Sleevar",
    "https://chefaa.com:443/eg-ar/now/brands/Rotahelex",
    "https://chefaa.com:443/eg-ar/now/brands/Justin-Blue",
    "https://chefaa.com:443/eg-ar/now/brands/Hyper-oil",
]

CHECKPOINT_FILE = "multi_category_scraping_checkpoint.json"
MAX_WORKERS = 3  # Number of parallel browsers
BATCH_SIZE = 3   # Pages per batch (reduced for stability)
REQUEST_DELAY = (2, 4)  # Random delay range
SMART_RETRY_DELAY = (10, 20)
MAX_RETRIES = 3  # Maximum retries per page

class EnhancedPharmacyScraper:
    def __init__(self):
        self.product_links = {}  # Dictionary to store links by category
        self.category_stats = {}  # Statistics for each category
        self.failed_categories = set()
        self.session = requests.Session()
        self.setup_session()
        self.lock = threading.Lock()
        self.global_stats = {
            'total_products': 0,
            'total_categories': len(CATEGORIES),
            'processed_categories': 0,
            'start_time': None,
            'end_time': None
        }
        
    def setup_session(self):
        """Setup requests session with proper headers"""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ar,en-US;q=0.7,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        self.session.headers.update(headers)

    def get_category_name(self, url):
        """Extract category name from URL"""
        return url.split('/')[-1] if url.endswith('/') else url.split('/')[-1]

    def create_optimized_driver(self):
        """Create optimized Chrome driver for fast scraping"""
        options = uc.ChromeOptions()
        
        # Performance optimizations
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--disable-images')
        options.add_argument('--disable-javascript')
        options.add_argument('--disable-plugins')
        options.add_argument('--disable-extensions')
        options.add_argument('--disable-background-networking')
        options.add_argument('--disable-background-timer-throttling')
        options.add_argument('--disable-renderer-backgrounding')
        options.add_argument('--disable-backgrounding-occluded-windows')
        options.add_argument('--disable-client-side-phishing-detection')
        options.add_argument('--disable-sync')
        options.add_argument('--disable-translate')
        options.add_argument('--hide-scrollbars')
        options.add_argument('--mute-audio')
        options.add_argument('--disable-web-security')
        options.add_argument('--disable-features=VizDisplayCompositor')
        
        # Memory optimizations
        options.add_argument('--memory-pressure-off')
        options.add_argument('--max_old_space_size=4096')
        
        # Block unnecessary resources
        prefs = {
            'profile.default_content_setting_values': {
                'images': 2,
                'plugins': 2,
                'popups': 2,
                'geolocation': 2,
                'notifications': 2,
                'media_stream': 2,
            },
            'profile.managed_default_content_settings': {
                'images': 2
            }
        }
        options.add_experimental_option('prefs', prefs)
        
        # Random user agent
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        ]
        options.add_argument(f'--user-agent={random.choice(user_agents)}')
        
        try:
            driver = uc.Chrome(options=options)
            driver.set_page_load_timeout(30)
            driver.implicitly_wait(5)
            return driver
        except Exception as e:
            print(f"❌ Failed to create driver: {e}")
            return None

    def safe_driver_quit(self, driver):
        """Safely quit driver"""
        try:
            if driver:
                driver.quit()
        except Exception as e:
            print(f"⚠️  Driver cleanup warning: {e}")
            try:
                driver.service.stop()
            except:
                pass

    def detect_category_pages(self, category_url):
        """Detect total pages for a specific category"""
        print(f"🔍 Detecting pages for category: {self.get_category_name(category_url)}")
        
        driver = self.create_optimized_driver()
        if not driver:
            return 0
            
        try:
            # Try different methods to detect pages
            methods = [
                lambda: self._detect_pages_pagination(driver, category_url),
                lambda: self._detect_pages_progressive_search(driver, category_url),
                lambda: self._detect_pages_binary_search(driver, category_url, 1, 20)
            ]
            
            for i, method in enumerate(methods):
                try:
                    pages = method()
                    if pages > 0:
                        print(f"✅ Found {pages} pages using method {i+1}")
                        return pages
                except Exception as e:
                    print(f"⚠️  Method {i+1} failed: {e}")
                    continue
            
            print("⚠️  All methods failed, defaulting to 10 pages")
            return 10
            
        finally:
            self.safe_driver_quit(driver)

    def _detect_pages_pagination(self, driver, category_url):
        """Detect pages from pagination elements"""
        url = f"{category_url}?sort=name&order=desc&limit=28"
        driver.get(url)
        time.sleep(3)
        
        pagination_selectors = [
            ".pagination a", ".pagination span", ".pagination li a",
            ".pager a", "[class*='pagination'] a", ".page-numbers a",
            ".nav-links a", "[class*='page'] a"
        ]
        
        max_page = 0
        for selector in pagination_selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                for element in elements:
                    # Check href
                    href = element.get_attribute('href')
                    if href and 'page=' in href:
                        page_match = re.search(r'page=(\d+)', href)
                        if page_match:
                            max_page = max(max_page, int(page_match.group(1)))
                    
                    # Check text
                    text = element.text.strip()
                    if text.isdigit():
                        max_page = max(max_page, int(text))
            except:
                continue
        
        return max_page

    def _detect_pages_progressive_search(self, driver, category_url):
        """Progressive search to find last page"""
        test_pages = [50, 30, 20, 15, 10, 8, 6, 4, 3, 2]
        
        for test_page in test_pages:
            url = f"{category_url}?sort=name&order=desc&limit=28&page={test_page}"
            driver.get(url)
            time.sleep(2)
            
            products = driver.find_elements(By.CSS_SELECTOR, ".product-card-new")
            if len(products) > 0:
                # Found products, search more precisely
                return self._precise_search_pages(driver, category_url, test_page)
        
        return 1  # At least one page exists

    def _precise_search_pages(self, driver, category_url, start_page):
        """More precise search around known valid page"""
        current_page = start_page
        while current_page <= start_page + 10:
            url = f"{category_url}?sort=name&order=desc&limit=28&page={current_page}"
            driver.get(url)
            time.sleep(2)
            
            products = driver.find_elements(By.CSS_SELECTOR, ".product-card-new")
            if len(products) == 0:
                return current_page - 1
                
            current_page += 1
        
        return current_page - 1

    def _detect_pages_binary_search(self, driver, category_url, min_page, max_page):
        """Binary search to find exact last page"""
        while min_page <= max_page:
            mid = (min_page + max_page) // 2
            url = f"{category_url}?sort=name&order=desc&limit=28&page={mid}"
            driver.get(url)
            time.sleep(2)
            
            products = driver.find_elements(By.CSS_SELECTOR, ".product-card-new")
            
            if products:
                min_page = mid + 1
            else:
                max_page = mid - 1
        
        return max_page

    def extract_category_links(self, category_url, page_num):
        """Extract product links from a specific category page"""
        driver = self.create_optimized_driver()
        if not driver:
            return [], False
            
        try:
            url = f"{category_url}?sort=name&order=desc&limit=28&page={page_num}"
            driver.get(url)
            
            # Wait for products to load
            WebDriverWait(driver, 10).until(
                lambda d: d.find_elements(By.CSS_SELECTOR, ".product-card-new") or 
                         "no products" in d.page_source.lower()
            )
            
            # Extract links
            cards = driver.find_elements(By.CSS_SELECTOR, ".product-card-new a.product-image-container")
            links = []
            
            for card in cards:
                try:
                    link = card.get_attribute("href")
                    if link:
                        links.append(link)
                except:
                    continue
            
            return links, len(links) > 0
            
        except Exception as e:
            print(f"❌ Error extracting from {category_url} page {page_num}: {e}")
            return [], False
        finally:
            self.safe_driver_quit(driver)

    def scrape_category(self, category_url):
        """Scrape all products from a specific category"""
        category_name = self.get_category_name(category_url)
        print(f"\n🚀 Starting category: {category_name}")
        
        # Initialize category data
        self.product_links[category_name] = set()
        self.category_stats[category_name] = {
            'total_pages': 0,
            'processed_pages': 0,
            'total_products': 0,
            'failed_pages': set(),
            'processing_time': 0
        }
        
        start_time = time.time()
        
        try:
            # Detect total pages
            total_pages = self.detect_category_pages(category_url)
            self.category_stats[category_name]['total_pages'] = total_pages
            
            if total_pages == 0:
                print(f"❌ No pages found for {category_name}")
                return
            
            print(f"📄 Processing {total_pages} pages for {category_name}")
            
            # Process pages sequentially for stability
            processed_pages = 0
            for page_num in range(1, total_pages + 1):
                print(f"🔍 {category_name} - Page {page_num}/{total_pages}")
                
                retry_count = 0
                success = False
                
                while retry_count < MAX_RETRIES and not success:
                    links, success = self.extract_category_links(category_url, page_num)
                    
                    if success:
                        self.product_links[category_name].update(links)
                        processed_pages += 1
                        print(f"✅ {category_name} - Page {page_num}: {len(links)} products")
                        
                        # Small delay between requests
                        time.sleep(random.uniform(*REQUEST_DELAY))
                    else:
                        retry_count += 1
                        if retry_count < MAX_RETRIES:
                            wait_time = random.uniform(*SMART_RETRY_DELAY)
                            print(f"🔄 Retrying {category_name} page {page_num} in {wait_time:.1f}s (attempt {retry_count + 1})")
                            time.sleep(wait_time)
                        else:
                            print(f"❌ Failed {category_name} page {page_num} after {MAX_RETRIES} attempts")
                            self.category_stats[category_name]['failed_pages'].add(page_num)
            
            # Update stats
            self.category_stats[category_name]['processed_pages'] = processed_pages
            self.category_stats[category_name]['total_products'] = len(self.product_links[category_name])
            self.category_stats[category_name]['processing_time'] = time.time() - start_time
            
            print(f"✅ {category_name} completed: {len(self.product_links[category_name])} products")
            
        except Exception as e:
            print(f"❌ Category {category_name} failed: {e}")
            self.failed_categories.add(category_name)

    def save_category_results(self, timestamp):
        """Save results organized by category"""
        results_dir = f"pharmacy_results_{timestamp}"
        os.makedirs(results_dir, exist_ok=True)
        
        all_products = []
        category_summary = []
        
        for category_name, links in self.product_links.items():
            if not links:
                continue
                
            links_list = sorted(list(links))
            stats = self.category_stats[category_name]
            
            # Save individual category file
            category_file = os.path.join(results_dir, f"{category_name}_products.csv")
            with open(category_file, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Product_URL", "Category", "Product_ID"])
                for i, link in enumerate(links_list, 1):
                    writer.writerow([link, category_name, f"{category_name}_{i}"])
                    all_products.append([link, category_name, f"{category_name}_{i}"])
            
            # Add to summary
            category_summary.append({
                'category': category_name,
                'total_pages': stats['total_pages'],
                'processed_pages': stats['processed_pages'],
                'failed_pages': len(stats['failed_pages']),
                'total_products': stats['total_products'],
                'processing_time': f"{stats['processing_time']:.1f}s",
                'success_rate': f"{(stats['processed_pages'] / stats['total_pages'] * 100):.1f}%" if stats['total_pages'] > 0 else "0%"
            })
        
        # Save combined results
        combined_file = os.path.join(results_dir, "all_products_combined.csv")
        with open(combined_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Product_URL", "Category", "Product_ID"])
            writer.writerows(all_products)
        
        # Save summary report
        summary_file = os.path.join(results_dir, "scraping_summary.json")
        with open(summary_file, "w", encoding="utf-8") as f:
            json.dump({
                'global_stats': self.global_stats,
                'category_summary': category_summary,
                'failed_categories': list(self.failed_categories),
                'total_unique_products': len(all_products)
            }, f, ensure_ascii=False, indent=2)
        
        print(f"\n💾 Results saved in: {results_dir}/")
        print(f"   📊 Combined file: all_products_combined.csv")
        print(f"   📋 Summary: scraping_summary.json")
        print(f"   📁 Individual category files: {len(self.product_links)} files")

    def run(self):
        """Main execution method"""
        self.global_stats['start_time'] = datetime.now().isoformat()
        start_time = time.time()
        
        print("🚀 Enhanced Multi-Category Pharmacy Scraper Starting...")
        print("="*80)
        print(f"📂 Processing {len(CATEGORIES)} categories")
        print("="*80)
        
        # Process each category
        for i, category_url in enumerate(CATEGORIES, 1):
            category_name = self.get_category_name(category_url)
            print(f"\n📂 [{i}/{len(CATEGORIES)}] Processing: {category_name}")
            
            self.scrape_category(category_url)
            self.global_stats['processed_categories'] += 1
            
            # Calculate running totals
            total_products = sum(len(links) for links in self.product_links.values())
            self.global_stats['total_products'] = total_products
            
            print(f"📊 Progress: {i}/{len(CATEGORIES)} categories | {total_products} total products")
            
            # Small delay between categories
            if i < len(CATEGORIES):
                time.sleep(random.uniform(5, 10))
        
        # Final results
        self.global_stats['end_time'] = datetime.now().isoformat()
        end_time = time.time()
        duration = end_time - start_time
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.save_category_results(timestamp)
        
        # Final report
        print("\n" + "="*80)
        print("🎉 MULTI-CATEGORY SCRAPING COMPLETED!")
        print(f"⏱️  Total time: {duration:.1f} seconds ({duration/60:.1f} minutes)")
        print(f"📂 Categories processed: {self.global_stats['processed_categories']}/{len(CATEGORIES)}")
        print(f"🔗 Total products collected: {self.global_stats['total_products']}")
        print(f"⚡ Average speed: {self.global_stats['total_products']/duration:.1f} products/second")
        print(f"❌ Failed categories: {len(self.failed_categories)}")
        
        if self.failed_categories:
            print(f"   Failed: {', '.join(self.failed_categories)}")
        
        print("="*80)

def main():
    """Main function"""
    scraper = EnhancedPharmacyScraper()
    scraper.run()

if __name__ == "__main__":
    main()
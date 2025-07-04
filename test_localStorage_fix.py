import sys
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By

def create_driver():
    """Create a WebDriver with localStorage error prevention"""
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    
    # Add safeguards against localStorage errors
    options.add_argument("--disable-web-security")
    options.add_argument("--allow-running-insecure-content")
    options.add_argument("--disable-site-isolation-trials")
    
    prefs = {
        'profile.default_content_setting_values': {
            'cookies': 1,
            'images': 1
        },
        # Disable localStorage and sessionStorage to prevent errors
        'dom.storage.enabled': False
    }
    options.add_experimental_option('prefs', prefs)
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    driver.set_page_load_timeout(30)
    return driver

def safe_execute_script(driver, script, default_value=None):
    """Safely execute JavaScript with error handling for localStorage issues"""
    try:
        # Check if we're on a data: URL
        current_url = driver.current_url
        if current_url.startswith('data:'):
            print(f"Skipping script execution on data: URL")
            return default_value
            
        # Execute the script with a timeout
        return driver.execute_script(script)
    except Exception as e:
        error_str = str(e).lower()
        if 'storage' in error_str or 'localStorage' in error_str or 'sessionStorage' in error_str:
            print(f"Storage-related error in script execution: {e}")
        else:
            print(f"Error in script execution: {e}")
        return default_value

def test_url(url):
    """Test a URL for localStorage errors"""
    print(f"\nTesting URL: {url}")
    driver = None
    try:
        driver = create_driver()
        
        # Load the page
        print("Loading page...")
        driver.get(url)
        time.sleep(2)
        
        # Check if we got redirected to a data: URL
        current_url = driver.current_url
        print(f"Current URL: {current_url[:50]}...")
        
        if current_url.startswith('data:'):
            print("WARNING: Redirected to data: URL")
            
        # Try to access localStorage (this would normally fail on data: URLs)
        print("\nTesting localStorage access:")
        try:
            driver.execute_script("window.localStorage.clear();")
            print("✅ Direct localStorage access succeeded")
        except Exception as e:
            print(f"❌ Direct localStorage access failed: {e}")
        
        # Try our safe execution method
        print("\nTesting safe script execution:")
        result = safe_execute_script(driver, "try { window.localStorage.clear(); return true; } catch(e) { return false; }")
        if result:
            print("✅ Safe localStorage access succeeded")
        else:
            print("⚠️ Safe localStorage access handled gracefully")
            
        # Try to extract images
        print("\nTesting image extraction:")
        elements = driver.find_elements(By.CSS_SELECTOR, "img")
        print(f"Found {len(elements)} images")
        
        # Try our safe script for image extraction
        js_urls = safe_execute_script(driver, """
            try {
                var urls = [];
                var images = document.querySelectorAll('img');
                images.forEach(function(img) {
                    if (img.src && img.src.indexOf('data:') !== 0) {
                        urls.push(img.src);
                    }
                });
                return urls;
            } catch(e) {
                return [];
            }
        """, [])
        
        print(f"Found {len(js_urls)} image URLs via safe script")
        
        print("\nTest completed successfully")
        return True
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        return False
    finally:
        if driver:
            driver.quit()

if __name__ == "__main__":
    # Get URL from command line or use default
    url = sys.argv[1] if len(sys.argv) > 1 else "https://chefaa.com/product/mom-baby_0054"
    test_url(url) 
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, WebDriverException
import time
import os

BASE_URL = "https://www.moreyeahs.com"
PAGES = [
    "/",              # Home
    "/Services",      # Services
    "/Product",      # Products
    "/Case Study",    # Case Studies
    "/About Us",      # About Us
    "/Career",        # Careers
    "/Contact Us"     # Contact Us
]

def setup_driver():
    """Setup Chrome driver with appropriate options"""
    chrome_options = Options()
    
    # Add options for better compatibility
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    
    # Uncomment the line below if you want to run in headless mode (no browser window)
    # chrome_options.add_argument("--headless")
    
    try:
        driver = webdriver.Chrome(options=chrome_options)
        return driver
    except WebDriverException as e:
        print(f" Error setting up Chrome driver: {e}")
        print(" Make sure you have ChromeDriver installed and in your PATH")
        print(" You can download it from: https://chromedriver.chromium.org/")
        return None

def scrape_page_content(driver, url):
    """Scrape content from a single page"""
    try:
        print(f" Loading: {url}")
        driver.get(url)
        
        # Wait for page to load
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        
        # Additional wait for dynamic content
        time.sleep(2)
        
        # Remove script and style elements
        driver.execute_script("""
            var scripts = document.querySelectorAll('script');
            var styles = document.querySelectorAll('style');
            scripts.forEach(function(script) { script.remove(); });
            styles.forEach(function(style) { style.remove(); });
        """)
        
        # Extract text content from various elements
        text_elements = driver.find_elements(By.CSS_SELECTOR, 
            "p, li, h1, h2, h3, h4, h5, h6, span, div, article, section, main"
        )
        
        # Filter and collect text
        text_content = []
        for element in text_elements:
            try:
                text = element.text.strip()
                if text and len(text) > 2 and text not in text_content:
                    text_content.append(text)
            except:
                continue
        
        if text_content:
            return " ".join(text_content)
        else:
            # Fallback: get all text from body
            body = driver.find_element(By.TAG_NAME, "body")
            return body.text.strip()
            
    except TimeoutException:
        print(f" Timeout loading {url}")
        return None
    except Exception as e:
        print(f" Error scraping {url}: {e}")
        return None

def scrape_website():
    """Main scraping function"""
    driver = setup_driver()
    if not driver:
        return ""
    
    all_text = []
    successful_scrapes = 0
    
    try:
        for page in PAGES:
            url = BASE_URL + page
            content = scrape_page_content(driver, url)
            
            if content:
                all_text.append(f"\n{'='*60}")
                all_text.append(f"Content from {url}")
                all_text.append(f"{'='*60}")
                all_text.append(content)
                successful_scrapes += 1
                print(f" Successfully scraped: {url}")
            else:
                print(f" Failed to scrape: {url}")
            
            # Small delay between requests
            time.sleep(1)
            
    finally:
        driver.quit()
        print(f"\n Scraping complete: {successful_scrapes}/{len(PAGES)} pages successful")
    
    return "\n".join(all_text)

def main():
    print(" Starting Selenium web scraper...")
    print(f" Target website: {BASE_URL}")
    print(f" Pages to scrape: {len(PAGES)}")
    print("-" * 60)
    
    # Check if ChromeDriver is available
    try:
        driver = setup_driver()
        if driver:
            driver.quit()
            print(" ChromeDriver is available")
        else:
            print(" ChromeDriver setup failed")
            return
    except:
        print(" ChromeDriver not found or not working")
        return
    
    # Scrape the website
    print("\n Starting scraping process...")
    data = scrape_website()
    
    if data.strip():
        # Preview first 4000 characters in terminal
        print("\n Preview of scraped data:")
        print("-" * 60)
        preview = data[:4000]
        print(preview)
        if len(data) > 4000:
            print(f"\n... (showing first 4000 of {len(data)} total characters)")
        
        # Save entire scraped content to file
        try:
            with open("scraped_data.txt", "w", encoding="utf-8") as f:
                f.write(data)
            print(f"\n Scraped data written to scraped_data.txt ({len(data)} characters)")
            
            # Also save as JSON for structured data
            import json
            structured_data = {
                "website": BASE_URL,
                "scraped_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "content": data,
                "pages_scraped": len(PAGES)
            }
            
            with open("scraped_data.json", "w", encoding="utf-8") as f:
                json.dump(structured_data, f, indent=2, ensure_ascii=False)
            print(" Structured data saved to scraped_data.json")
        
        except Exception as e:
            print(f" Error writing to file: {e}")
    else:
        print(" No data was scraped. Check the website URL and page paths.")

if __name__ == "__main__":
    main()
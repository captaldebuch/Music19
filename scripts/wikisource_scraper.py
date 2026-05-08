import os
import requests
from bs4 import BeautifulSoup
import time

def scrape_wikisource_category(language_code, category_name, output_dir):
    """
    Scrapes dictionary entries from a specific Wikisource category.
    Example: language_code='ru', category_name='Музыкальный_словарь_Римана'
    """
    print(f"--- Wikisource: Fetching {category_name} ({language_code}) ---")
    base_url = f"https://{language_code}.wikisource.org"
    api_url = f"{base_url}/w/api.php"
    
    os.makedirs(output_dir, exist_ok=True)
    out_file_path = os.path.join(output_dir, f"wikisource_{language_code}_{category_name}.txt")
    
    params = {
        "action": "query",
        "list": "categorymembers",
        "cmtitle": f"Category:{category_name}",
        "cmlimit": "50", # Reduced limit for test purposes
        "format": "json"
    }
    
    entries = []
    
    try:
        response = requests.get(api_url, params=params)
        response.raise_for_status()
        data = response.json()
        
        pages = data.get("query", {}).get("categorymembers", [])
        print(f"Found {len(pages)} pages in category (limited to 50 for testing).")
        
        for page in pages:
            title = page["title"]
            page_url = f"{base_url}/wiki/{title}"
            
            # Fetch the actual page content
            page_res = requests.get(page_url)
            if page_res.status_code == 200:
                soup = BeautifulSoup(page_res.text, 'html.parser')
                content_div = soup.find(id="mw-content-text")
                if content_div:
                    text = content_div.get_text(separator="\n", strip=True)
                    entries.append(f"=== {title} ===\n{text}\n")
            
            time.sleep(0.5) # Polite scraping
            
    except Exception as e:
        print(f"Error fetching from Wikisource: {e}")
        return False
        
    if entries:
        with open(out_file_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(entries))
        print(f"Saved {len(entries)} entries to {out_file_path}")
        return True
    return False

def main():
    # Example: Russian Brockhaus and Efron Encyclopedic Dictionary (ESBE) category or Riemann
    # Replace with actual category names from Wikisource
    categories = [
        {"lang": "ru", "cat": "Музыкальный_словарь_Римана"}
    ]
    
    for cat_info in categories:
        scrape_wikisource_category(cat_info['lang'], cat_info['cat'], 'data_ocr/wikisource')

if __name__ == "__main__":
    main()

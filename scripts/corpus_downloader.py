import os
import json
import requests
import xml.etree.ElementTree as ET
import time
import internetarchive as ia

def download_from_archive_org(identifier, output_dir):
    """
    Downloads OCR text from Archive.org using the internetarchive library.
    """
    print(f"--- Archive.org: Fetching {identifier} ---")
    try:
        item = ia.get_item(identifier)
        if not item.exists:
            print(f"Item {identifier} does not exist.")
            return False
            
        # List all files for debugging
        all_files = [f['name'] for f in item.files]
        #print(f"Available files: {all_files}")
        
        # Find the text file
        text_files = [f['name'] for f in item.files if f['name'].endswith('.txt')]
        
        if not text_files:
            print(f"No .txt files found for {identifier}. Available formats: {[f.get('format') for f in item.files]}")
            return False
        
        # Prefer files with 'djvu' in the name as they are usually the cleaner OCR
        djvu_files = [f for f in text_files if 'djvu' in f]
        file_to_download = djvu_files[0] if djvu_files else text_files[0]
        
        print(f"Downloading {file_to_download}...")
        item.download(files=[file_to_download], destdir=output_dir, verbose=False)
        return True
    except Exception as e:
        print(f"Error downloading from Archive.org: {e}")
        return False

def download_from_gallica(ark_id, output_dir):
    """
    Downloads OCR text from Gallica using robust session handling.
    Fetches the IIIF manifest to determine the number of pages, then downloads page by page.
    Fallback to a default page range if manifest fails.
    """
    print(f"--- Gallica: Fetching {ark_id} ---")
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
    })

    # Get manifest for page count
    manifest_url = f"https://gallica.bnf.fr/iiif/ark:/12148/{ark_id}/manifest.json"
    try:
        res = session.get(manifest_url, timeout=10)
        if res.status_code == 200:
            manifest = res.json()
            canvases = manifest.get('sequences', [])[0].get('canvases', [])
            num_pages = len(canvases)
            print(f"Found {num_pages} pages in IIIF manifest.")
        else:
            print(f"Failed to fetch manifest (Status {res.status_code}), defaulting to 50 pages fallback.")
            num_pages = 50
    except Exception as e:
        print(f"Error fetching manifest: {e}, defaulting to 50 pages fallback.")
        num_pages = 50

    out_file_path = os.path.join(output_dir, f"{ark_id}_gallica.txt")
    if os.path.exists(out_file_path):
        print(f"File {out_file_path} already exists. Skipping.")
        return True

    text_content = []
    
    # We will limit for tests
    limit = min(num_pages, 200) 
    
    print(f"Starting download of up to {limit} pages...")
    for page in range(1, limit + 1):
        # Alternative URL format: f1.texteBrut
        text_url = f"https://gallica.bnf.fr/ark:/12148/{ark_id}/f{page}.texteBrut"
        success = False
        for attempt in range(3):
            try:
                res = session.get(text_url, timeout=15)
                if res.status_code == 200:
                    if len(res.text.strip()) > 10: # Avoid empty pages
                        text_content.append(f"--- Page {page} ---\n{res.text}")
                    success = True
                    break
                elif res.status_code == 403:
                    print(f"Page {page}: 403 Forbidden. Sleeping...")
                    time.sleep(5 * (attempt + 1))
                elif res.status_code == 500:
                    print(f"Page {page}: 500 Server Error. Retrying...")
                    time.sleep(2 * (attempt + 1))
            except requests.exceptions.RequestException as e:
                print(f"Page {page}: Request Exception {e}. Retrying...")
                time.sleep(2 * (attempt + 1))
        
        if not success:
            print(f"Failed to fetch page {page} after 3 attempts.")
        
        if page % 10 == 0:
            print(f"Progress: {page}/{limit} pages...")
        
        time.sleep(0.3) # Polite delay

    if text_content:
        with open(out_file_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(text_content))
        print(f"Saved extracted text to {out_file_path} ({len(text_content)} pages)")
        return True
    else:
        print("No text content could be extracted.")
    return False

def main():
    with open('metadata/dictionary_inventory.json', 'r') as f:
        inventory = json.load(f)
    
    os.makedirs('data_ocr', exist_ok=True)
    
    # Test a few items
    test_items = [
        "LA-TINCTORIS-1475",
        "LA-ISIDORE-625",
        "LA-GROCHEIO-1300",
        "LA-JEROME-1275"
    ]
    
    # Map of IDs to Archive.org Identifiers if they differ
    ia_map = {
        "LA-TINCTORIS-1475": "dictionaryofmusi0000tinc",
        "LA-ISIDORE-625": "isidori-hispalensis-etymologiarum-sive-opus-de-origine-quarumdam-rerum-libri-xx",
        "LA-GROCHEIO-1300": "concerningmusicd0000joha",
        "LA-JEROME-1275": "bub_gb_0EgoAAAAYAAJ_2"
    }
    
    for item_id in test_items:
        item = next((i for i in inventory if i['id'] == item_id), None)
        if not item: continue
        
        print(f"\nProcessing {item['id']}: {item['title']}")
        
        if "gallica.bnf.fr" in item['source_url']:
            ark_id = item['source_url'].split('/')[-1]
            download_from_gallica(ark_id, 'data_ocr')
        elif "archive.org" in item['source_url']:
            identifier = ia_map.get(item['id'], item['source_url'].split('/')[-1])
            download_from_archive_org(identifier, 'data_ocr')

if __name__ == "__main__":
    main()

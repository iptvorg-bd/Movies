import urllib.request
import urllib.error
import json
import sys
import os

# Set console encoding to UTF-8 for Windows compatibility
sys.stdout.reconfigure(encoding='utf-8')

API_URL = "https://cinexo.pages.dev/api/sync-data"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*'
}

# Output structure inside the "dudemove" folder
PARENT_DIR = "dudemove"
MOVIES_DIR = os.path.join(PARENT_DIR, "movies")
INDEX_FILE = os.path.join(PARENT_DIR, "movies.json")

def process_stream_urls(item):
    """
    Extracts 1080p, 720p, 480p URLs from hls_sources into top-level keys
    compatible with your original JSON format.
    """
    item['stream_url_1080p'] = None
    item['stream_url_720p'] = None
    item['stream_url_480p'] = None

    for src in item.get('hls_sources', []):
        res = src.get('res')
        url = src.get('url')
        if not url:
            continue
            
        if res == '1080p' and not item['stream_url_1080p']:
            item['stream_url_1080p'] = url
        elif res == '720p' and not item['stream_url_720p']:
            item['stream_url_720p'] = url
        elif res == '480p' and not item['stream_url_480p']:
            item['stream_url_480p'] = url

    return item

def main():
    print("=" * 60)
    print("               Cinexo Sync Data Fetcher               ")
    print("=" * 60)

    # 1. Ensure output folders exist
    os.makedirs(MOVIES_DIR, exist_ok=True)

    print(f"Connecting to API: {API_URL} ...")
    
    try:
        req = urllib.request.Request(API_URL, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=15) as res:
            raw_data = json.loads(res.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        print(f"HTTP Error: {e.code} - {e.reason}")
        return
    except Exception as e:
        print(f"Request Error: {e}")
        return

    # 2. Extract and merge items (sliderItems, trendItems, latestItems)
    seen_ids = set()
    all_movies = []

    sections = ['sliderItems', 'trendItems', 'latestItems']
    for section in sections:
        items = raw_data.get(section, [])
        for item in items:
            item_id = item.get('id')
            if item_id and item_id not in seen_ids:
                seen_ids.add(item_id)
                
                # Standardize stream fields
                processed_item = process_stream_urls(item)
                all_movies.append(processed_item)

                # Save individual movie JSON
                individual_file = os.path.join(MOVIES_DIR, f"{item_id}.json")
                with open(individual_file, "w", encoding="utf-8") as f:
                    json.dump(processed_item, f, indent=2, ensure_ascii=False)

    print(f"Successfully processed {len(all_movies)} items.")

    # 3. Save master movies.json
    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(all_movies, f, indent=2, ensure_ascii=False)

    print(f"Saved master index to: {INDEX_FILE}")
    print(f"Individual files stored in: {MOVIES_DIR}/")
    print("=" * 60)

if __name__ == "__main__":
    main()

import urllib.request
import urllib.parse
import urllib.error
import json
import time
import sys
import math
import os
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed

# Set console encoding to UTF-8 for Windows compatibility
sys.stdout.reconfigure(encoding='utf-8')

BASE_URL = "https://moviebaaz.baby"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Referer': f'{BASE_URL}/'
}

# Output structure inside the "dudemove" folder
PARENT_DIR = "dudemove"
MOVIES_DIR = os.path.join(PARENT_DIR, "movies")
INDEX_FILE = os.path.join(PARENT_DIR, "movies.json")

def fetch_stream_sources(movie):
    """
    Fetches streaming URLs by calling admin-ajax.php with gdmax_refresh action.
    """
    movie_id = movie.get('id')
    if not movie_id:
        return movie

    ajax_url = f"{BASE_URL}/wp-admin/admin-ajax.php"
    
    # Form data based on the network tab payload
    form_data = {
        'action': 'gdmax_refresh',
        'post_id': str(movie_id),
        'ep': '0'
    }
    encoded_data = urllib.parse.urlencode(form_data).encode('utf-8')
    
    req_headers = HEADERS.copy()
    req_headers['Content-Type'] = 'application/x-www-form-urlencoded; charset=UTF-8'
    req_headers['X-Requested-With'] = 'XMLHttpRequest'

    retries = 3
    movie['sources'] = []
    movie['stream_url_1080p'] = None
    movie['stream_url_720p'] = None
    movie['stream_url_480p'] = None

    for attempt in range(retries):
        try:
            req = urllib.request.Request(ajax_url, data=encoded_data, headers=req_headers, method='POST')
            time.sleep(0.3)
            with urllib.request.urlopen(req, timeout=10) as res:
                res_data = json.loads(res.read().decode('utf-8'))
                
                if res_data.get('success') and 'data' in res_data:
                    sources = res_data['data'].get('sources', [])
                    movie['sources'] = sources
                    
                    # Extract specific qualities
                    for src in sources:
                        q = src.get('q')
                        url = src.get('url')
                        if q == '1080p':
                            movie['stream_url_1080p'] = url
                        elif q == '720p':
                            movie['stream_url_720p'] = url
                        elif q == '480p':
                            movie['stream_url_480p'] = url
                break
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep((attempt + 1) * 2)
            else:
                time.sleep(0.5)
        except Exception:
            time.sleep(0.5)

    # Save individual movie details inside 'dudemove/movies/'
    individual_file = os.path.join(MOVIES_DIR, f"{movie_id}.json")
    with open(individual_file, "w", encoding="utf-8") as ind_f:
        json.dump(movie, ind_f, indent=2, ensure_ascii=False)

    return movie

def get_movies_from_page(page_num, per_page=10):
    """
    Fetches a page of movies using the WordPress REST API endpoint.
    """
    url = f"{BASE_URL}/wp-json/wp/v2/movies?page={page_num}&per_page={per_page}"
    retries = 3
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=10) as res:
                total_movies = int(res.headers.get('X-WP-Total', 0))
                total_pages = int(res.headers.get('X-WP-TotalPages', 0))
                data = json.loads(res.read().decode('utf-8'))
                
                # Format movie metadata
                cleaned_movies = []
                for item in data:
                    cleaned_movies.append({
                        'id': item.get('id'),
                        'slug': item.get('slug'),
                        'title': item.get('title', {}).get('rendered', ''),
                        'link': item.get('link', ''),
                        'date': item.get('date', '')
                    })
                    
                return cleaned_movies, total_movies, total_pages
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep((attempt + 1) * 2)
            else:
                time.sleep(1)
        except Exception as e:
            time.sleep(1)

    return [], 0, 0

def main():
    parser = argparse.ArgumentParser(description="Fetch movies and stream links into dudemove folder.")
    parser.add_argument("--pages", type=int, help="Number of pages to fetch.")
    parser.add_argument("--all", action="store_true", help="Fetch all available pages.")
    args, unknown = parser.parse_known_args()

    print("=" * 60)
    print("             MovieBaaz Content & Streaming Fetcher            ")
    print("=" * 60)
    
    os.makedirs(MOVIES_DIR, exist_ok=True)
    
    # 1. Fetch first page to inspect totals
    per_page = 10
    print("\nConnecting to WordPress API...")
    first_page_movies, total_movies, total_pages = get_movies_from_page(1, per_page=per_page)
    
    if not total_movies:
        print("Failed to fetch initial data. Check if the site blocked the request or Cloudflare challenge is active.")
        return
        
    print(f"Total Movies found: {total_movies}")
    print(f"Total Pages available: {total_pages} ({per_page} per page)")
    
    if args.all:
        max_pages = total_pages
    elif args.pages is not None:
        max_pages = min(args.pages, total_pages)
    else:
        try:
            limit_input = input("\nEnter number of pages to fetch (Press Enter for ALL): ").strip()
            max_pages = int(limit_input) if limit_input else total_pages
        except Exception:
            max_pages = total_pages
            
    max_pages = min(max_pages, total_pages)
    print(f"Fetching {max_pages} page(s)...")
    
    # 2. Collect movies from list pages
    all_movies = []
    for page in range(1, max_pages + 1):
        print(f"[{page}/{max_pages}] Fetching list...")
        movies, _, _ = get_movies_from_page(page, per_page=per_page)
        all_movies.extend(movies)
        time.sleep(0.4)
        
    print(f"\nCollected metadata for {len(all_movies)} movies.")
    print("Fetching streaming URLs via AJAX...")
    
    # 3. Fetch stream URLs concurrently
    completed_count = 0
    final_movies = []
    
    for index, movie in enumerate(all_movies):
        movie['_index'] = index
        
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(fetch_stream_sources, movie): movie for movie in all_movies}
        
        for future in as_completed(futures):
            movie = future.result()
            final_movies.append(movie)
            completed_count += 1
            sys.stdout.write(f"\rProgress: {completed_count}/{len(all_movies)} processed...")
            sys.stdout.flush()
            
    final_movies.sort(key=lambda x: x.get('_index', 0))
    for movie in final_movies:
        movie.pop('_index', None)
            
    print("\n\nCompleted successfully!")
    
    # 4. Save results to JSON file
    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(final_movies, f, indent=2, ensure_ascii=False)
        
    print(f"Saved {len(final_movies)} records to: {INDEX_FILE}")
    print(f"Individual files stored in: {MOVIES_DIR}/")
    print("=" * 60)

if __name__ == "__main__":
    main()

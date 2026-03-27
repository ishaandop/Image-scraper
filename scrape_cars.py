# Car image scraper - fetches 8 reference images per car from CarWale
"""Scrape car reference images from CarWale using requests (no browser needed).

CarWale is a Next.js app. Each page embeds a __NEXT_DATA__ JSON blob containing
structured image data with high-res CDN URLs hosted on imgd.aeplcdn.com.
This script extracts that JSON to find and download 8 specific angles per car.

Target: 80 images total (8 angles x 10 cars).
"""

import json
import os
import re
import time

import requests

CARS = {
    "Tata Punch": "https://www.carwale.com/tata-cars/punch/images/",
    "Hyundai Creta": "https://www.carwale.com/hyundai-cars/creta/images/",
    "Tata Sierra": "https://www.carwale.com/tata-cars/sierra/images/",
    "Tata Punch EV": "https://www.carwale.com/tata-cars/punch-ev/images/",
    "Kia Seltos": "https://www.carwale.com/kia-cars/seltos/images/",
    "Maruti Invicto": "https://www.carwale.com/maruti-suzuki-cars/invicto/images/",
    "Tata Nexon": "https://www.carwale.com/tata-cars/nexon/images/",
    "Mahindra Scorpio N": "https://www.carwale.com/mahindra-cars/scorpio-n/images/",
    "Maruti Fronx": "https://www.carwale.com/maruti-suzuki-cars/fronx/images/",
    "Hyundai Venue": "https://www.carwale.com/hyundai-cars/venue/images/",
}

# 8 target views: filename -> (keywords to match, keywords to exclude)
VIEWS = {
    "front_straight": {
        "keywords": ["front-view", "front view", "grille", "bumper", "headlamp", "head-lamp", "head lamp"],
        "exclude": ["three-quarter", "3/4", "quarter", "side"],
        "category": "exterior",
    },
    "front_3q": {
        "keywords": ["front-three-quarter", "right-front-three-quarter", "left-front-three-quarter",
                      "front three quarter", "front 3/4", "front quarter"],
        "exclude": [],
        "category": "exterior",
    },
    "side_left": {
        "keywords": ["left-side-view", "left side view", "left-view", "left view", "left side"],
        "exclude": ["front", "rear", "quarter", "three-quarter"],
        "category": "exterior",
    },
    "side_right": {
        "keywords": ["right-side-view", "right side view", "right-view", "right view", "right side"],
        "exclude": ["front", "rear", "quarter", "three-quarter"],
        "category": "exterior",
    },
    "rear_straight": {
        "keywords": ["rear-view", "rear view", "tail-lamp", "tail lamp", "taillamp", "taillight",
                      "boot", "rear-left-view", "rear-right-view"],
        "exclude": ["three-quarter", "3/4", "quarter", "seat"],
        "category": "exterior",
    },
    "interior_dashboard": {
        "keywords": ["dashboard", "dash-board", "interior-front", "cabin-front", "interior front"],
        "exclude": ["steering", "seat", "rear"],
        "category": "interior",
    },
    "interior_steering": {
        "keywords": ["steering", "steering-wheel", "steering wheel"],
        "exclude": [],
        "category": "interior",
    },
    "interior_rear_seats": {
        "keywords": ["rear-seat", "rear seat", "back-seat", "back seat", "rear-passenger",
                      "rear passenger", "second-row", "second row"],
        "exclude": [],
        "category": "interior",
    },
}

OUTPUT_DIR = "car_references"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


def sanitize_filename(name: str) -> str:
    """Convert a string to a safe filename."""
    return re.sub(r"[^\w\s-]", "", name).strip().replace(" ", "_")


def download_image(url: str, filepath: str) -> bool:
    """Download an image from a URL and save it to filepath."""
    print(f"    Downloading: {url}")
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30, stream=True)
        resp.raise_for_status()
        content_length = len(resp.content)
        if content_length < 1000:
            print(f"    -> Skipped (too small: {content_length} bytes, likely not a real image)")
            return False
        with open(filepath, "wb") as f:
            f.write(resp.content)
        print(f"    -> Saved {filepath} ({content_length} bytes)")
        return True
    except Exception as e:
        print(f"    -> Download failed: {e}")
        return False


def upscale_url(url: str) -> str:
    """Replace resolution in CDN URL with a higher resolution."""
    return re.sub(r"/\d+x\d+/", "/1056x594/", url)


def extract_next_data(html: str) -> dict | None:
    """Extract __NEXT_DATA__ JSON from the page HTML."""
    match = re.search(
        r'<script\s+id="__NEXT_DATA__"\s+type="application/json">(.*?)</script>',
        html,
        re.DOTALL,
    )
    if match:
        try:
            data = json.loads(match.group(1))
            print("  [DEBUG] Found __NEXT_DATA__ JSON blob")
            return data
        except json.JSONDecodeError as e:
            print(f"  [DEBUG] Failed to parse __NEXT_DATA__: {e}")
    return None


def extract_images_from_json(data: dict) -> list[dict]:
    """Recursively search the JSON data for image objects."""
    images = []

    def _search(obj, depth=0):
        if depth > 15:
            return
        if isinstance(obj, dict):
            # Look for objects that have image URL fields
            url = None
            if obj.get("hostUrl") and obj.get("imagePath"):
                url = obj["hostUrl"] + obj["imagePath"]
            else:
                url = (
                    obj.get("imageUrl")
                    or obj.get("imagePath")
                    or obj.get("originalImageUrl")
                )
            alt = (
                obj.get("imageAlt")
                or obj.get("altText")
                or obj.get("caption")
                or obj.get("imageTitle")
                or obj.get("heading")
                or ""
            )
            category = obj.get("categoryName") or obj.get("category") or ""

            if url and isinstance(url, str) and ("aeplcdn" in url or "carwale" in url or "cardekho" in url):
                images.append({"url": url, "alt": str(alt), "category": str(category)})

            for v in obj.values():
                _search(v, depth + 1)
        elif isinstance(obj, list):
            for item in obj:
                _search(item, depth + 1)

    _search(data)
    return images


def extract_images_from_html(html: str) -> list[dict]:
    """Fallback: extract image URLs directly from the HTML source using regex."""
    images = []
    pattern = r'(https?://imgd[.-]aeplcdn\.com/[^\s"\'<>]+\.(?:jpg|jpeg|png|webp))'
    for match in re.finditer(pattern, html, re.IGNORECASE):
        url = match.group(1)
        images.append({"url": url, "alt": url.split("/")[-1], "category": ""})

    pattern2 = r'(https?://[a-z0-9.-]*carwale\.com/[^\s"\'<>]+\.(?:jpg|jpeg|png|webp))'
    for match in re.finditer(pattern2, html, re.IGNORECASE):
        url = match.group(1)
        images.append({"url": url, "alt": url.split("/")[-1], "category": ""})

    seen = set()
    unique = []
    for img in images:
        if img["url"] not in seen:
            seen.add(img["url"])
            unique.append(img)
    return unique


def match_candidate(candidate: dict, view_config: dict) -> bool:
    """Check if a candidate image matches a specific view configuration."""
    searchable = f"{candidate['alt']} {candidate['category']} {candidate['url']}".lower()

    # Must match at least one keyword
    if not any(kw in searchable for kw in view_config["keywords"]):
        return False

    # Must not match any exclude keyword
    if view_config["exclude"] and any(kw in searchable for kw in view_config["exclude"]):
        return False

    return True


def scrape_car_images(car: str, url: str) -> None:
    """Scrape 8 images for a single car model from its CarWale images page."""
    car_folder = os.path.join(OUTPUT_DIR, sanitize_filename(car))
    os.makedirs(car_folder, exist_ok=True)

    print(f"  Fetching page: {url}")
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        print(f"  [DEBUG] Page fetched OK, status={resp.status_code}, length={len(resp.text)} chars")
    except Exception as e:
        print(f"  -> Failed to fetch page: {e}")
        return

    html = resp.text

    # Strategy 1: Extract from __NEXT_DATA__ JSON
    candidates = []
    next_data = extract_next_data(html)
    if next_data:
        candidates = extract_images_from_json(next_data)
        print(f"  [DEBUG] Found {len(candidates)} images from __NEXT_DATA__")

    # Strategy 2: Regex fallback on raw HTML
    if len(candidates) < 8:
        html_images = extract_images_from_html(html)
        print(f"  [DEBUG] Found {len(html_images)} images from HTML regex fallback")
        existing_urls = {c["url"] for c in candidates}
        for img in html_images:
            if img["url"] not in existing_urls:
                candidates.append(img)

    if not candidates:
        print(f"  -> WARNING: No images found at all for {car}")
        print(f"  [DEBUG] First 2000 chars of HTML:\n{html[:2000]}")
        return

    # Print all candidates for debugging
    print(f"  [DEBUG] Total candidates: {len(candidates)}")
    for i, c in enumerate(candidates[:30]):
        alt_preview = c["alt"][:80] if c["alt"] else "(no alt)"
        print(f"    [{i}] {alt_preview}")
        print(f"         URL: {c['url'][:120]}")

    # Match candidates to each of the 8 views
    saved_views = set()
    used_urls = set()

    for view_name, view_config in VIEWS.items():
        for candidate in candidates:
            if candidate["url"] in used_urls:
                continue
            if match_candidate(candidate, view_config):
                img_url = upscale_url(candidate["url"])
                filepath = os.path.join(car_folder, f"{view_name}.jpg")
                print(f"  [{view_name}] Matched: {candidate['alt'][:60]}")
                if download_image(img_url, filepath):
                    saved_views.add(view_name)
                    used_urls.add(candidate["url"])
                    break

    # Relaxed pass: for missing views, try broader keyword matching (just category)
    missing_views = [v for v in VIEWS if v not in saved_views]
    if missing_views:
        print(f"  [DEBUG] Missing after strict match: {missing_views}")
        for view_name in list(missing_views):
            view_config = VIEWS[view_name]
            target_cat = view_config["category"]
            for candidate in candidates:
                if candidate["url"] in used_urls:
                    continue
                cat = candidate["category"].lower()
                alt = candidate["alt"].lower()
                url_path = candidate["url"].lower()
                # Match on category (exterior/interior) from alt or category field
                if target_cat in cat or target_cat in alt or target_cat in url_path:
                    img_url = upscale_url(candidate["url"])
                    filepath = os.path.join(car_folder, f"{view_name}.jpg")
                    print(f"  [{view_name}] Relaxed match: {candidate['alt'][:60]}")
                    if download_image(img_url, filepath):
                        saved_views.add(view_name)
                        used_urls.add(candidate["url"])
                        missing_views.remove(view_name)
                        break

    # Final fallback: assign any remaining candidates to missing views
    missing_views = [v for v in VIEWS if v not in saved_views]
    if missing_views:
        print(f"  [DEBUG] Missing after relaxed match: {missing_views}")
        for candidate in candidates:
            if not missing_views:
                break
            if candidate["url"] in used_urls:
                continue
            view_name = missing_views.pop(0)
            img_url = upscale_url(candidate["url"])
            filepath = os.path.join(car_folder, f"{view_name}.jpg")
            print(f"  [{view_name}] Fallback: {candidate['alt'][:60]}")
            if download_image(img_url, filepath):
                saved_views.add(view_name)
                used_urls.add(candidate["url"])
            else:
                missing_views.insert(0, view_name)

    final_missing = [v for v in VIEWS if v not in saved_views]
    if final_missing:
        print(f"  -> WARNING: Still missing views: {final_missing}")
    else:
        print(f"  -> All 8 views saved successfully!")


def main() -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"Scraping 8 images each for {len(CARS)} car models (80 total)...\n")

    for car, url in CARS.items():
        print(f"\n{'='*60}")
        print(f"  Scraping: {car}")
        print(f"{'='*60}")
        scrape_car_images(car, url)
        time.sleep(1)  # Be polite between requests

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    total = 0
    for car in CARS:
        car_folder = os.path.join(OUTPUT_DIR, sanitize_filename(car))
        if os.path.isdir(car_folder):
            files = sorted(os.listdir(car_folder))
            count = len(files)
            total += count
            print(f"  {car}: {count}/8 images -> {files}")
        else:
            print(f"  {car}: NO FOLDER CREATED")

    print(f"\n  TOTAL: {total}/80 images downloaded")
    print(f"  Saved to: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()

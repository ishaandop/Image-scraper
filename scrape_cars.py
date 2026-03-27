# Car image scraper - fetches reference images from CarWale via embedded JSON data
"""Scrape car reference images from CarWale using requests (no browser needed).

CarWale is a Next.js app. Each page embeds a __NEXT_DATA__ JSON blob containing
structured image data with high-res CDN URLs hosted on imgd.aeplcdn.com.
This script extracts that JSON to find and download images by view category.
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

VIEW_KEYWORDS = {
    "front": ["front", "headlamp", "head lamp", "grille", "bumper front", "front-three-quarter"],
    "side": ["side", "profile", "left-view", "right-view", "left side", "right side"],
    "rear": ["rear", "tail lamp", "taillamp", "tail-lamp", "back", "boot", "rear-three-quarter"],
    "interior": ["interior", "dashboard", "steering", "cabin", "infotainment"],
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


def match_view(text: str, view: str) -> bool:
    """Check if text matches a desired view category."""
    text_lower = text.lower()
    return any(kw in text_lower for kw in VIEW_KEYWORDS[view])


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
            url = (
                obj.get("imageUrl")
                or obj.get("imagePath")
                or obj.get("originalImageUrl")
                or obj.get("hostUrl", "")
                + obj.get("imagePath", "")
                if obj.get("hostUrl") and obj.get("imagePath")
                else None
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
    # Match CDN image URLs in the HTML
    pattern = r'(https?://imgd[.-]aeplcdn\.com/[^\s"\'<>]+\.(?:jpg|jpeg|png|webp))'
    for match in re.finditer(pattern, html, re.IGNORECASE):
        url = match.group(1)
        images.append({"url": url, "alt": url.split("/")[-1], "category": ""})

    # Also try carwale CDN
    pattern2 = r'(https?://[a-z0-9.-]*carwale\.com/[^\s"\'<>]+\.(?:jpg|jpeg|png|webp))'
    for match in re.finditer(pattern2, html, re.IGNORECASE):
        url = match.group(1)
        images.append({"url": url, "alt": url.split("/")[-1], "category": ""})

    # Deduplicate
    seen = set()
    unique = []
    for img in images:
        if img["url"] not in seen:
            seen.add(img["url"])
            unique.append(img)
    return unique


def scrape_car_images(car: str, url: str) -> None:
    """Scrape images for a single car model from its CarWale images page."""
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
    if len(candidates) < 4:
        html_images = extract_images_from_html(html)
        print(f"  [DEBUG] Found {len(html_images)} images from HTML regex fallback")
        # Append only new URLs
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
    for i, c in enumerate(candidates[:20]):
        alt_preview = c["alt"][:80] if c["alt"] else "(no alt)"
        print(f"    [{i}] {alt_preview}")
        print(f"         URL: {c['url'][:120]}")

    # Match candidates to views
    saved_views = set()
    for view in VIEW_KEYWORDS:
        for candidate in candidates:
            searchable = f"{candidate['alt']} {candidate['category']} {candidate['url']}"
            if match_view(searchable, view):
                img_url = upscale_url(candidate["url"])
                filepath = os.path.join(car_folder, f"{view}.jpg")
                print(f"  [{view}] Matched: {candidate['alt'][:60]}")
                if download_image(img_url, filepath):
                    saved_views.add(view)
                    break

    # Fallback: assign remaining unmatched images to missing views
    missing = [v for v in VIEW_KEYWORDS if v not in saved_views]
    if missing:
        print(f"  [DEBUG] Missing views after keyword match: {missing}")
        used_urls = set()
        idx = 0
        for candidate in candidates:
            if not missing:
                break
            if candidate["url"] in used_urls:
                continue
            view = missing.pop(0)
            img_url = upscale_url(candidate["url"])
            filepath = os.path.join(car_folder, f"{view}.jpg")
            print(f"  [{view}] Fallback image #{idx}: {candidate['alt'][:60]}")
            if download_image(img_url, filepath):
                used_urls.add(candidate["url"])
            else:
                missing.insert(0, view)  # Put it back if download failed
            idx += 1

    final_missing = [v for v in VIEW_KEYWORDS if v not in saved_views]
    if final_missing:
        print(f"  -> WARNING: Still missing views: {final_missing}")
    else:
        print(f"  -> All 4 views saved successfully!")


def main() -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"Scraping images for {len(CARS)} car models...\n")

    for car, url in CARS.items():
        print(f"\n{'='*60}")
        print(f"  Scraping: {car}")
        print(f"{'='*60}")
        scrape_car_images(car, url)
        time.sleep(1)  # Be polite between requests

    # Summary
    print(f"\n{'='*60}")
    print(f"SUMMARY")
    print(f"{'='*60}")
    for car in CARS:
        car_folder = os.path.join(OUTPUT_DIR, sanitize_filename(car))
        if os.path.isdir(car_folder):
            files = os.listdir(car_folder)
            print(f"  {car}: {len(files)} images -> {files}")
        else:
            print(f"  {car}: NO FOLDER CREATED")

    print(f"\nDone! Images saved to: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()

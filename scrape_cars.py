# Car image scraper - fetches reference images from CarWale using requests + BeautifulSoup
"""Scrape car reference images from CarWale without a browser."""

import os
import re
import time

import requests
from bs4 import BeautifulSoup

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
    "front": ["front", "head lamp", "headlamp", "grille", "bumper front"],
    "side": ["side", "profile", "left side", "right side"],
    "rear": ["rear", "tail lamp", "taillamp", "back", "boot"],
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
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30, stream=True)
        resp.raise_for_status()
        with open(filepath, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        return True
    except Exception as e:
        print(f"  -> Download failed: {e}")
        return False


def match_view(alt_text: str, view: str) -> bool:
    """Check if an image's alt text matches a desired view category."""
    alt_lower = alt_text.lower()
    return any(kw in alt_lower for kw in VIEW_KEYWORDS[view])


def scrape_car_images(car: str, url: str) -> None:
    """Scrape images for a single car model from its CarWale images page."""
    car_folder = os.path.join(OUTPUT_DIR, sanitize_filename(car))
    os.makedirs(car_folder, exist_ok=True)

    print(f"  Fetching: {url}")
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        print(f"  -> Failed to fetch page: {e}")
        return

    soup = BeautifulSoup(resp.text, "html.parser")

    # Collect all image candidates with their alt text and src
    candidates = []
    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src") or img.get("data-original") or ""
        alt = img.get("alt") or img.get("title") or ""
        if not src or not alt:
            continue
        # Only consider actual car images (typically hosted on CarWale CDN)
        if "carwale" not in src and "imgcdnx" not in src and "cwmedia" not in src:
            continue
        # Prefer higher resolution images
        src = re.sub(r"/img/\d+x\d+/", "/img/800x600/", src)
        src = re.sub(r"\?.*$", "", src)
        if not src.startswith("http"):
            src = "https:" + src if src.startswith("//") else "https://www.carwale.com" + src
        candidates.append({"src": src, "alt": alt})

    saved_views = set()
    for view in VIEW_KEYWORDS:
        if view in saved_views:
            continue
        for candidate in candidates:
            if match_view(candidate["alt"], view):
                filepath = os.path.join(car_folder, f"{view}.jpg")
                print(f"  [{view}] Found: {candidate['alt'][:60]}")
                if download_image(candidate["src"], filepath):
                    print(f"  -> Saved {filepath}")
                    saved_views.add(view)
                    break
        else:
            print(f"  [{view}] No matching image found")

    # Fallback: if some views are missing, grab the first N available images
    missing = [v for v in VIEW_KEYWORDS if v not in saved_views]
    if missing and candidates:
        used_srcs = set()
        for candidate in candidates:
            if not missing:
                break
            if candidate["src"] in used_srcs:
                continue
            view = missing.pop(0)
            filepath = os.path.join(car_folder, f"{view}.jpg")
            print(f"  [{view}] Fallback: {candidate['alt'][:60]}")
            if download_image(candidate["src"], filepath):
                print(f"  -> Saved {filepath}")
                used_srcs.add(candidate["src"])


def main() -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"Scraping images for {len(CARS)} car models...\n")

    for car, url in CARS.items():
        print(f"{'='*50}")
        print(f"Scraping: {car}")
        print(f"{'='*50}")
        scrape_car_images(car, url)
        time.sleep(1)  # Be polite between requests

    print(f"\nDone! Images saved to: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()

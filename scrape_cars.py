# Car image scraper - fetches reference images from CarWale for 10 popular models
"""Scrape car reference images from CarWale using Playwright."""

import os
import re
import time
import urllib.parse

from playwright.sync_api import sync_playwright

CARS = [
    "Tata Punch",
    "Hyundai Creta",
    "Tata Sierra",
    "Tata Punch EV",
    "Kia Seltos",
    "Maruti Invicto",
    "Tata Nexon",
    "Mahindra Scorpio N",
    "Maruti Fronx",
    "Hyundai Venue",
]

IMAGE_VIEWS = [
    "Front face",
    "Side profile",
    "Rear 3/4",
    "Interior dashboard",
]

OUTPUT_DIR = "car_references"


def sanitize_filename(name: str) -> str:
    """Convert a string to a safe filename."""
    return re.sub(r"[^\w\s-]", "", name).strip().replace(" ", "_")


def scrape_car_images(car: str, views: list[str], output_dir: str) -> None:
    """Scrape images for a single car model from CarWale."""
    car_folder = os.path.join(output_dir, sanitize_filename(car))
    os.makedirs(car_folder, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()

        for view in views:
            query = f"CarWale {car} {view}"
            search_url = (
                "https://www.google.com/search?tbm=isch&q="
                + urllib.parse.quote(query)
            )
            print(f"[{car}] Searching: {query}")

            try:
                page.goto(search_url, timeout=30000)
                page.wait_for_load_state("domcontentloaded")
                time.sleep(2)

                # Click the first image thumbnail to open the preview
                thumbnails = page.locator("img.YQ4gaf")
                if thumbnails.count() == 0:
                    thumbnails = page.locator("#search img")

                if thumbnails.count() > 0:
                    thumbnails.first.click()
                    time.sleep(2)

                    # Try to grab the full-resolution image from the side panel
                    full_img = page.locator(
                        "img.sFlh5c.FyHeAf.iPVvYb, img.r48jcc.pT0Scc.iPVvYb"
                    )
                    if full_img.count() > 0:
                        src = full_img.first.get_attribute("src")
                    else:
                        # Fallback: grab the thumbnail src
                        src = thumbnails.first.get_attribute("src")

                    if src and src.startswith("http"):
                        view_name = sanitize_filename(view)
                        file_path = os.path.join(car_folder, f"{view_name}.jpg")

                        # Download the image
                        response = page.request.get(src)
                        if response.ok:
                            with open(file_path, "wb") as f:
                                f.write(response.body())
                            print(f"  -> Saved {file_path}")
                        else:
                            print(f"  -> Failed to download image for {view}")
                    else:
                        print(f"  -> No valid image URL found for {view}")
                else:
                    print(f"  -> No thumbnails found for {view}")

            except Exception as e:
                print(f"  -> Error scraping {view}: {e}")

        browser.close()


def main() -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"Scraping images for {len(CARS)} car models...")

    for car in CARS:
        print(f"\n{'='*50}")
        print(f"Scraping: {car}")
        print(f"{'='*50}")
        scrape_car_images(car, IMAGE_VIEWS, OUTPUT_DIR)

    print("\nDone! Images saved to:", OUTPUT_DIR)


if __name__ == "__main__":
    main()

import os
import re
import json
import requests
from bs4 import BeautifulSoup

# Pobieranie danych z GitHub Secrets
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Link z filtrami: RAM DDR4 16GB, laptop, cena do 160 zł, sortowanie od najtańszych
# Na Allegro Lokalnie ogłoszenia "Kup teraz" mają etykietę Kup teraz / brak informacji o licytacji
URL = (
    "https://allegrolokalnie.pl/oferty/czesci-do-laptopow/pamiec-ram-77809/q/"
    "ram%20ddr4%2016gb?cena_do=160&zrodlo=lokalnie&zrodlo=allegro&sort=price-asc"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7",
}

SEEN_FILE = "seen_offers.json"


def load_seen_offers():
    """Wczytuje listę ofert, o których już wysłano powiadomienie."""
    if os.path.exists(SEEN_FILE):
        try:
            with open(SEEN_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()


def save_seen_offers(seen_offers):
    """Zapisuje listę widzianych ofert do pliku."""
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(list(seen_offers), f, ensure_ascii=False, indent=2)


def send_telegram_alert(title, price, link):
    """Wysyła wiadomość na Telegram."""
    text = (
        f"🔥 <b>Nowy RAM DDR4 16GB!</b>\n\n"
        f"📦 <b>Tytuł:</b> {title}\n"
        f"💰 <b>Cena:</b> {price} zł\n"
        f"🔗 <b>Link:</b> {link}"
    )
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    requests.post(url, json=payload, timeout=10)


def run_check():
    seen = load_seen_offers()
    resp = requests.get(URL, headers=HEADERS, timeout=15)
    if resp.status_code != 200:
        print(f"Błąd pobierania strony: kod {resp.status_code}")
        return

    soup = BeautifulSoup(resp.text, "html.parser")
    articles = soup.find_all("article")
    new_found = False

    for item in articles:
        text_content = item.get_text(" ", strip=True).lower()

        # Odrzucamy licytacje - interesuje nas tylko Kup Teraz
        if "licytacja" in text_content and "kup teraz" not in text_content:
            continue

        link_tag = item.find("a", href=True)
        if not link_tag:
            continue

        href = link_tag["href"]
        full_url = href if href.startswith("http") else f"https://allegrolokalnie.pl{href}"
        # Unikalny identyfikator oferty (ścieżka URL bez zbędnych parametrów)
        offer_id = full_url.split("?")[0]

        # Wyciąganie tytułu
        title = link_tag.get_text(strip=True) or "Pamięć RAM DDR4 16GB"

        # Wyciąganie ceny
        price_match = re.search(r"(\d+[\d\s]*)(?:,\d{2})?\s*zł", item.get_text())
        if not price_match:
            continue

        raw_price = price_match.group(1).replace(" ", "")
        try:
            price_val = float(raw_price)
        except ValueError:
            continue

        # Sprawdzamy limit ceny i czy oferta nie była już zgłaszana
        if price_val <= 160.0 and offer_id not in seen:
            print(f"Znaleziono nową ofertę: {title} za {price_val} zł")
            send_telegram_alert(title, price_val, full_url)
            seen.add(offer_id)
            new_found = True

    if new_found:
        save_seen_offers(seen)
    else:
        print("Brak nowych ofert spełniających kryteria.")


if __name__ == "__main__":
    run_check()

"""
Google Maps Web Scraping Engine with Playwright Stealth.
Extracts business leads (Name, Phone, Address, Rating, Reviews, Website),
executes live website audits, calculates Growth Hacking Lead Scores,
and persists valid qualified leads with real-time SSE progress streaming.
"""

import os
import re
import time
import json
import logging
import threading
import urllib.parse
from typing import Dict, Any, List, Optional, Callable

from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page, TimeoutError as PlaywrightTimeoutError

import database
import auditor
import pitch_generator

logger = logging.getLogger("NexusScraper")
logger.setLevel(logging.INFO)

# Brazilian phone regex pattern
PHONE_REGEX = re.compile(
    r"(?:(?:\+|00)?55\s*)?(?:\(?([1-9]{2})\)?\s*)?(?:(9\s*\d{4}|\d{4})[-.\s]?(\d{4}))"
)

# Global scraper controller for cancellation and real-time state
class ScraperController:
    def __init__(self):
        self.is_running = False
        self.stop_requested = False
        self.current_campaign_id = None
        self.leads_count = 0
        self.target_count = 100
        self.current_lead_name = ""
        self.status_message = "Pronto para iniciar"
        self.thread = None
        self.subscribers: List[Callable[[Dict[str, Any]], None]] = []

    def reset(self, campaign_id: int, target: int):
        self.is_running = True
        self.stop_requested = False
        self.current_campaign_id = campaign_id
        self.leads_count = 0
        self.target_count = target
        self.current_lead_name = ""
        self.status_message = "Iniciando motor de busca..."

    def stop(self):
        self.stop_requested = True
        self.status_message = "Interrupção solicitada pelo usuário..."

    def notify(self, data: Dict[str, Any]):
        for sub in list(self.subscribers):
            try:
                sub(data)
            except Exception:
                pass


active_scraper = ScraperController()


def extract_phone_from_text(text: str) -> Optional[str]:
    """Finds and formats a valid Brazilian phone number from arbitrary text."""
    if not text:
        return None
    matches = PHONE_REGEX.findall(text)
    if matches:
        ddd, p1, p2 = matches[0]
        p1 = p1.replace(" ", "")
        p2 = p2.replace(" ", "")
        if ddd:
            return f"({ddd}) {p1}-{p2}"
        return f"{p1}-{p2}"
    return None


def run_scraping_worker(niche: str, city: str, target_count: int, campaign_id: int):
    """
    Main background worker executing Playwright Google Maps extraction.
    """
    active_scraper.reset(campaign_id, target_count)
    database.add_log(f"Iniciando varredura para nicho '{niche}' em '{city}'. Meta: {target_count} leads válidos.", "INFO", campaign_id)

    query = f"{niche} em {city}".strip()
    encoded_query = urllib.parse.quote_plus(query)
    maps_url = f"https://www.google.com/maps/search/{encoded_query}?hl=pt-BR"

    qualified_count = 0
    without_site_count = 0
    need_modernization_count = 0
    processed_names = set()

    browser = None
    playwright_inst = None

    try:
        playwright_inst = sync_playwright().start()

        # Launch using native Chrome or fallback to Edge
        launch_options = {
            "headless": True,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-infobars",
                "--window-size=1366,768",
                "--ignore-certificate-errors",
            ],
        }

        try:
            browser = playwright_inst.chromium.launch(channel="chrome", **launch_options)
            database.add_log("Navegador Google Chrome nativo inicializado com sucesso.", "INFO", campaign_id)
        except Exception as e_chrome:
            database.add_log(f"Chrome indisponível, tentando Microsoft Edge: {e_chrome}", "WARNING", campaign_id)
            browser = playwright_inst.chromium.launch(channel="msedge", **launch_options)

        context = browser.new_context(
            viewport={"width": 1366, "height": 768},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="pt-BR",
        )
        page = context.new_page()

        database.add_log(f"Acessando Google Maps: {query}", "INFO", campaign_id)
        active_scraper.status_message = f"Pesquisando '{query}' no Google Maps..."
        active_scraper.notify({"type": "status", "message": active_scraper.status_message, "count": qualified_count})

        page.goto(maps_url, timeout=30000, wait_until="domcontentloaded")
        time.sleep(3)

        # Handle cookie consent popup if present
        try:
            consent_btn = page.query_selector(
                "button[aria-label*='Aceitar'], button[aria-label*='Concordo'], form button[jsname]"
            )
            if consent_btn:
                consent_btn.click()
                time.sleep(1)
        except Exception:
            pass

        # Look for the scrollable feed container
        feed_selector = 'div[role="feed"], div[aria-label*="Resultados para"]'
        try:
            page.wait_for_selector(feed_selector, timeout=12000)
        except PlaywrightTimeoutError:
            database.add_log("Aguardando carregamento da grade de resultados...", "INFO", campaign_id)

        scroll_attempts = 0
        max_scroll_attempts = 60

        while qualified_count < target_count and not active_scraper.stop_requested and scroll_attempts < max_scroll_attempts:
            scroll_attempts += 1

            # Select cards currently visible in the feed
            cards = page.query_selector_all('div.Nv2PK, div[role="article"]')
            if not cards:
                cards = page.query_selector_all('a.hfpxzc')

            database.add_log(f"Varrendo grade do Google Maps: {len(cards)} empresas visíveis no feed...", "INFO", campaign_id)

            for card in cards:
                if qualified_count >= target_count or active_scraper.stop_requested:
                    break

                try:
                    # 1. Company Name
                    name = None
                    # Try title element or aria-label
                    title_elem = card.query_selector('.qBF1Pd, font')
                    if title_elem:
                        name = title_elem.inner_text().strip()
                    if not name:
                        link_elem = card.query_selector('a.hfpxzc')
                        if link_elem:
                            name = link_elem.get_attribute("aria-label")

                    if not name or name in processed_names or len(name) < 2:
                        continue

                    processed_names.add(name)
                    active_scraper.current_lead_name = name

                    # 2. Rating & Reviews
                    rating = 0.0
                    reviews_count = 0
                    rating_elem = card.query_selector('.MW4etd')
                    if rating_elem:
                        try:
                            rating = float(rating_elem.inner_text().replace(",", "."))
                        except Exception:
                            pass

                    reviews_elem = card.query_selector('.UY7F9')
                    if reviews_elem:
                        try:
                            rev_str = re.sub(r"\D", "", reviews_elem.inner_text())
                            if rev_str:
                                reviews_count = int(rev_str)
                        except Exception:
                            pass

                    # 3. Card text for initial quick inspection
                    card_text = card.inner_text() or ""
                    phone = extract_phone_from_text(card_text)

                    # 4. Check for direct website link in card
                    website = None
                    web_elem = card.query_selector('a[data-value="Website"], a.lcr4fd, a[aria-label*="website"]')
                    if web_elem:
                        website = web_elem.get_attribute("href")

                    # If phone or website not immediately found on card, click card to view details pane
                    if not phone or not website:
                        try:
                            card.click()
                            time.sleep(1.2)

                            # Detail pane phone search
                            phone_btn = page.query_selector('button[data-tooltip*="telefone"], button[data-item-id*="phone"], button[aria-label*="Telefone"]')
                            if phone_btn:
                                phone_text = phone_btn.inner_text() or phone_btn.get_attribute("aria-label") or ""
                                phone = extract_phone_from_text(phone_text) or phone

                            # Detail pane website search
                            if not website:
                                site_btn = page.query_selector('a[data-item-id="authority"], a[aria-label*="site"], a[aria-label*="website"]')
                                if site_btn:
                                    website = site_btn.get_attribute("href")
                        except Exception as e_click:
                            pass

                    # Resolve any Google tracking / ad URLs to real destination domain
                    if website:
                        website = pitch_generator.resolve_google_ad_url(website)

                    # Address extraction
                    address = f"{city} - Brasil"
                    addr_elem = card.query_selector('.W4Efsd:last-child')
                    if addr_elem:
                        address_candidate = addr_elem.inner_text().strip()
                        if len(address_candidate) > 5:
                            address = address_candidate

                    # Maps URL
                    maps_place_url = page.url

                    # ==========================================
                    # QUALIFICATION FILTER:
                    # ==========================================
                    # Requisito rigoroso: Deve consolidar leads válidos com TELEFONE disponível
                    if not phone:
                        continue  # Ignora leads sem telefone para manter a lista estritamente comercial

                    # Website Audit & Diagnosis
                    audit_res = auditor.audit_website(website)
                    qual_status = audit_res["status"]
                    qual_detail = audit_res["detail"]

                    if "Sem Site" in qual_status:
                        without_site_count += 1
                    elif "Modernização" in qual_status:
                        need_modernization_count += 1

                    # Lead Score & Growth Script Generation
                    score, temperature = pitch_generator.calculate_lead_score(
                        qual_status, rating, reviews_count, phone, website or "", audit_res
                    )

                    scripts = pitch_generator.generate_scripts(
                        {
                            "name": name,
                            "rating": rating,
                            "reviews_count": reviews_count,
                            "phone": phone,
                            "website": website or "",
                            "qualification_status": qual_status,
                            "qualification_detail": qual_detail,
                        },
                        niche=niche,
                        city=city,
                    )

                    lead_dict = {
                        "campaign_id": campaign_id,
                        "name": name,
                        "phone": phone,
                        "clean_phone": pitch_generator.clean_phone_number(phone),
                        "address": address,
                        "rating": rating,
                        "reviews_count": reviews_count,
                        "website": website or "",
                        "maps_url": maps_place_url,
                        "qualification_status": qual_status,
                        "qualification_detail": qual_detail,
                        "lead_score": score,
                        "lead_temperature": temperature,
                        "crm_status": "Novo",
                        "notes": f"Identificado via Google Maps ({niche})",
                        "cold_call_script": scripts["cold_call_script"],
                        "whatsapp_script": scripts["whatsapp_script"],
                    }

                    lead_id = database.save_lead(lead_dict)
                    qualified_count += 1
                    active_scraper.leads_count = qualified_count

                    msg = (
                        f"[{qualified_count}/{target_count}] Lead Qualificado: {name} | "
                        f"Score: {score} ({temperature}) | {qual_status} | Tel: {phone}"
                    )
                    database.add_log(msg, "SUCCESS", campaign_id)
                    active_scraper.notify({
                        "type": "new_lead",
                        "lead": {**lead_dict, "id": lead_id, "whatsapp_url": scripts["whatsapp_url"]},
                        "count": qualified_count,
                        "target": target_count,
                        "without_site": without_site_count,
                        "modernization": need_modernization_count,
                    })

                except Exception as e_lead:
                    logger.error(f"Erro processando lead card: {e_lead}")
                    continue

            # Scroll feed to trigger dynamic loading
            try:
                page.evaluate(
                    '''() => {
                        const feed = document.querySelector('div[role="feed"]');
                        if (feed) {
                            feed.scrollTop += 1200;
                        } else {
                            window.scrollBy(0, 1000);
                        }
                    }'''
                )
                time.sleep(2.0)
            except Exception:
                time.sleep(1.0)

            # Check for end of list banner
            if "Você chegou ao final da lista" in (page.content() or ""):
                database.add_log("Fim da lista de resultados do Google Maps alcançado para esta região.", "INFO", campaign_id)
                break

        final_status = "completed" if qualified_count >= target_count else ("stopped" if active_scraper.stop_requested else "completed")
        database.update_campaign_status(
            campaign_id,
            status=final_status,
            total_found=qualified_count,
            without_site=without_site_count,
            modernization=need_modernization_count,
        )
        active_scraper.status_message = f"Processamento finalizado. {qualified_count} leads qualificados capturados."
        database.add_log(active_scraper.status_message, "SUCCESS", campaign_id)
        active_scraper.notify({
            "type": "finished",
            "count": qualified_count,
            "status": final_status,
        })

    except Exception as e_global:
        database.add_log(f"Erro na execução da raspagem: {str(e_global)}", "ERROR", campaign_id)
        active_scraper.status_message = f"Erro: {str(e_global)[:60]}"
        database.update_campaign_status(campaign_id, status="failed", total_found=qualified_count)
        active_scraper.notify({"type": "error", "message": str(e_global)})

    finally:
        active_scraper.is_running = False
        try:
            if browser:
                browser.close()
        except Exception:
            pass
        try:
            if playwright_inst:
                playwright_inst.stop()
        except Exception:
            pass


def start_scraping(niche: str, city: str, target_count: int = 100) -> int:
    """Spawns background scraping thread for the specified niche and city."""
    if active_scraper.is_running:
        raise RuntimeError("Uma raspagem já está em andamento.")

    database.init_db()
    campaign_id = database.create_campaign(niche, city, target_count)
    active_scraper.thread = threading.Thread(
        target=run_scraping_worker,
        args=(niche, city, target_count, campaign_id),
        daemon=True,
    )
    active_scraper.thread.start()
    return campaign_id


def stop_scraping():
    """Requests running scraper to stop."""
    if active_scraper.is_running:
        active_scraper.stop()
        return True
    return False

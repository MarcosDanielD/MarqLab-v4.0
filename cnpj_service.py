"""
CNPJ Discovery & Enrichment Service for Marq Lab.
Searches public registries and queries BrasilAPI / ReceitaWS to uncover:
- CNPJ number & official Razao Social
- Cadastral Status (ATIVA, BAIXADA, INAPTA, SUSPENSA)
- Company Partners & Owners (Quadro de Socios - QSA)
- Market Longevity (Data de Abertura)
- Company Size (MEI, ME, EPP, LTDA)
"""

import re
import json
import urllib.request
import urllib.parse
import unicodedata
from typing import Dict, Any, Optional, List

import database

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def _clean_company_name(name: str) -> str:
    """Removes special characters and trims excess spaces."""
    if not name:
        return ""
    # Normalize unicode and strip extra punctuation
    clean = re.sub(r"[^\w\s\-\.]", " ", name)
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean


def _extract_city_from_address(address: str) -> Optional[str]:
    """Tries to extract municipality from standard Google Maps Brazilian addresses."""
    if not address:
        return None
    # Matches patterns like 'Curitiba - PR' or 'Araucária - PR' or 'São Paulo - SP'
    match = re.search(r",\s*([^,\-]+)\s*-\s*([A-Z]{2})", address)
    if match:
        return match.group(1).strip()
    return None


def _fetch_from_brasilapi(cnpj_clean: str) -> Optional[Dict[str, Any]]:
    """Attempts to fetch official CNPJ data from BrasilAPI."""
    try:
        url = f"https://brasilapi.com.br/api/cnpj/v1/{cnpj_clean}"
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=6) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                socios = [s.get("nome_socio") for s in data.get("qsa", []) if s.get("nome_socio")]
                
                # Format opening date
                abertura_raw = data.get("data_inicio_atividade", "")
                abertura_formatted = abertura_raw
                if abertura_raw and "-" in abertura_raw:
                    parts = abertura_raw.split("-")
                    if len(parts) == 3:
                        abertura_formatted = f"{parts[2]}/{parts[1]}/{parts[0]}"

                regime = "Normal"
                if data.get("opcao_pelo_mei"):
                    regime = "MEI"
                elif data.get("opcao_pelo_simples"):
                    regime = "Simples Nacional"

                return {
                    "source": "BrasilAPI",
                    "cnpj": cnpj_clean,
                    "cnpj_formatted": f"{cnpj_clean[:2]}.{cnpj_clean[2:5]}.{cnpj_clean[5:8]}/{cnpj_clean[8:12]}-{cnpj_clean[12:]}",
                    "razao_social": data.get("razao_social") or data.get("nome_fantasia") or "",
                    "nome_fantasia": data.get("nome_fantasia") or data.get("razao_social") or "",
                    "situacao_cadastral": (data.get("descricao_situacao_cadastral") or "ATIVA").upper(),
                    "data_inicio_atividade": abertura_formatted,
                    "porte": data.get("porte") or "Microempresa (ME)",
                    "regime": regime,
                    "socios": socios,
                    "socios_str": ", ".join(socios) if socios else "Não informado / Individual",
                    "cnae_fiscal_descricao": data.get("cnae_fiscal_descricao") or "",
                    "capital_social": float(data.get("capital_social") or 0.0),
                    "municipio": data.get("municipio") or "",
                    "uf": data.get("uf") or "",
                    "logradouro": f"{data.get('logradouro', '')}, {data.get('numero', '')}".strip(", "),
                    "bairro": data.get("bairro") or "",
                    "cep": data.get("cep") or "",
                }
    except Exception:
        pass
    return None


def _fetch_from_receitaws(cnpj_clean: str) -> Optional[Dict[str, Any]]:
    """Fallback fetcher using ReceitaWS."""
    try:
        url = f"https://receitaws.com.br/v1/cnpj/{cnpj_clean}"
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=6) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                if data.get("status") == "ERROR":
                    return None
                socios = [s.get("nome") for s in data.get("qsa", []) if s.get("nome")]
                
                regime = "Normal"
                if data.get("simples", {}).get("optante"):
                    regime = "Simples Nacional"
                if data.get("simei", {}).get("optante"):
                    regime = "MEI"

                capital_val = 0.0
                try:
                    capital_val = float(str(data.get("capital_social", 0)).replace(".", "").replace(",", "."))
                except Exception:
                    pass

                return {
                    "source": "ReceitaWS",
                    "cnpj": cnpj_clean,
                    "cnpj_formatted": data.get("cnpj") or f"{cnpj_clean[:2]}.{cnpj_clean[2:5]}.{cnpj_clean[5:8]}/{cnpj_clean[8:12]}-{cnpj_clean[12:]}",
                    "razao_social": data.get("nome") or data.get("fantasia") or "",
                    "nome_fantasia": data.get("fantasia") or data.get("nome") or "",
                    "situacao_cadastral": (data.get("situacao") or "ATIVA").upper(),
                    "data_inicio_atividade": data.get("abertura") or "",
                    "porte": data.get("porte") or "Microempresa (ME)",
                    "regime": regime,
                    "socios": socios,
                    "socios_str": ", ".join(socios) if socios else "Não informado / Individual",
                    "cnae_fiscal_descricao": (data.get("atividade_principal", [{}])[0].get("text") or ""),
                    "capital_social": capital_val,
                    "municipio": data.get("municipio") or "",
                    "uf": data.get("uf") or "",
                    "logradouro": f"{data.get('logradouro', '')}, {data.get('numero', '')}".strip(", "),
                    "bairro": data.get("bairro") or "",
                    "cep": data.get("cep") or "",
                }
    except Exception:
        pass
    return None


def fetch_cnpj_details(cnpj_raw: str) -> Optional[Dict[str, Any]]:
    """Fetches full legal profile for a 14-digit CNPJ using multiple public API mirrors."""
    clean = re.sub(r"\D", "", cnpj_raw)
    if len(clean) != 14:
        return None
    # 1. Try BrasilAPI primary
    data = _fetch_from_brasilapi(clean)
    if data:
        return data
    # 2. Try ReceitaWS fallback
    return _fetch_from_receitaws(clean)


def search_cnpj_candidates(name: str, city: Optional[str] = None) -> List[str]:
    """
    Discovers potential 14-digit CNPJs from public search engines.
    Combines DuckDuckGo and Bing for maximum coverage.
    """
    clean_name = _clean_company_name(name)
    if not clean_name:
        return []

    # Strip company type suffixes to broaden search
    core_name = re.sub(r"\b(ltda|me|epp|eireli|s/a|sa|eletrica|advocacia|comercio|servicos)\b", "", clean_name, flags=re.IGNORECASE).strip()

    # Strip marketing subtitles commonly found on Google Maps titles (e.g. "ABL SOLAR | Orçamento...")
    primary_name = re.split(r"[\–\—\|\:\•\·]", name)[0].strip()
    primary_clean = _clean_company_name(primary_name)

    queries = []
    if primary_clean and primary_clean != clean_name:
        if city:
            queries.append(f"{primary_clean} {city} cnpj")
        queries.append(f"{primary_clean} cnpj")

    if city:
        queries.append(f"{clean_name} {city} cnpj")
        if core_name and core_name != clean_name:
            queries.append(f"{core_name} {city} cnpj")
    queries.append(f"{clean_name} cnpj")

    candidates: List[str] = []
    headers = {"User-Agent": USER_AGENT}

    # 1. Search DuckDuckGo Lite (POST request, robust and bot-proof)
    for q in queries:
        try:
            url = "https://lite.duckduckgo.com/lite/"
            post_data = urllib.parse.urlencode({"q": q}).encode("utf-8")
            req = urllib.request.Request(url, data=post_data, headers=headers)
            with urllib.request.urlopen(req, timeout=5) as res:
                html = res.read().decode("utf-8", errors="ignore")

            # Extract formatted XX.XXX.XXX/XXXX-XX
            for m in re.findall(r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b", html):
                clean = re.sub(r"\D", "", m)
                if len(clean) == 14 and clean not in candidates:
                    candidates.append(clean)

            # Extract 14 digit continuous from URLs or text
            for m in re.findall(r"(?:cnpj|empresa)[^\d]{1,10}(\d{14})", html, flags=re.IGNORECASE):
                if m not in candidates:
                    candidates.append(m)

            if candidates:
                break
        except Exception:
            pass

    # 2. Fallback to Bing if no candidates found
    if not candidates:
        for q in queries:
            try:
                url = f"https://www.bing.com/search?q={urllib.parse.quote(q)}"
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=5) as res:
                    html = res.read().decode("utf-8", errors="ignore")

                for m in re.findall(r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b", html):
                    clean = re.sub(r"\D", "", m)
                    if len(clean) == 14 and clean not in candidates:
                        candidates.append(clean)

                for m in re.findall(r"(?:cnpj|empresa)[^\d]{1,10}(\d{14})", html, flags=re.IGNORECASE):
                    if m not in candidates:
                        candidates.append(m)

                if candidates:
                    break
            except Exception:
                pass

    return candidates


def _normalize_text(text: str) -> str:
    """Strips accents, lowercase, and removes excess non-alphanumeric chars."""
    if not text:
        return ""
    norm = unicodedata.normalize("NFKD", str(text)).encode("ASCII", "ignore").decode("utf-8").lower()
    return re.sub(r"[^a-z0-9\s]", " ", norm).strip()


def _is_candidate_relevant(details: Dict[str, Any], lead_name: str, city: Optional[str]) -> bool:
    """Verifies if candidate CNPJ record corresponds to the queried lead."""
    razao = _normalize_text(details.get("razao_social") or "")
    fantasia = _normalize_text(details.get("nome_fantasia") or "")
    muni = _normalize_text(details.get("municipio") or "")
    
    # Primary lead brand (before dividers) and full lead name
    primary = re.split(r"[\–\—\|\:\•\·]", lead_name)[0].strip()
    primary_norm = _normalize_text(primary)
    lead_norm = _normalize_text(lead_name)

    # 1. Check primary brand name tokens (e.g. "ABL", "Ehdros", "Arausolar")
    primary_tokens = [t for t in re.split(r"\s+", primary_norm) if len(t) >= 3 and t not in ["solar", "energia", "servicos", "engenharia", "brasil"]]
    if any(t in razao or t in fantasia for t in primary_tokens):
        return True

    # 2. General lead tokens
    tokens = [t for t in re.split(r"\s+", lead_norm) if len(t) >= 4 and t not in ["solar", "energia", "servicos", "engenharia", "brasil"]]
    if any(t in razao or t in fantasia for t in tokens):
        return True

    # 3. Match by normalized municipality if at least one token matches
    city_norm = _normalize_text(city) if city else ""
    if city_norm and city_norm in muni:
        all_tokens = [t for t in re.split(r"\s+", primary_norm) if len(t) >= 3]
        if any(t in razao or t in fantasia for t in all_tokens):
            return True

    return False


def enrich_lead_cnpj(lead_id: int) -> Dict[str, Any]:
    """
    Core function: Takes a lead_id, finds their CNPJ, verifies official status,
    extracts company owners/partners, and updates the database record.
    """
    lead = database.get_lead_by_id(lead_id)
    if not lead:
        return {"success": False, "error": "Lead não encontrado."}

    lead_name = lead.get("name", "")
    address = lead.get("address", "")
    city = _extract_city_from_address(address)

    # If city not in address, check campaign city
    if not city and lead.get("campaign_id"):
        campaign = database.get_campaign_by_id(lead["campaign_id"])
        if campaign and campaign.get("city"):
            raw_city = campaign["city"]
            city = raw_city.split("-")[0].strip() if "-" in raw_city else raw_city.strip()

    # 1. Search for CNPJ candidates
    candidates = search_cnpj_candidates(lead_name, city=city)

    # 2. Validate and enrich each candidate
    for candidate in candidates:
        details = fetch_cnpj_details(candidate)
        if details:
            # Check relevance to prevent false attributions
            if not _is_candidate_relevant(details, lead_name, city):
                continue

            # Save in database
            database.update_lead_cnpj(lead_id, details)
            
            # Log action
            status_cad = details.get("situacao_cadastral", "ATIVA")
            log_type = "SUCCESS" if status_cad == "ATIVA" else "WARNING"
            status_desc = "ATIVA" if status_cad == "ATIVA" else f"INATIVA ({status_cad})"
            database.add_log(
                f"CNPJ do Lead #{lead_id} ({lead_name}) identificado: {details.get('cnpj_formatted')} - Status: {status_desc}.",
                log_type
            )

            return {
                "success": True,
                "lead_id": lead_id,
                "lead_name": lead_name,
                "data": details,
            }

    # If no candidate was found or verified
    not_found_data = {
        "cnpj": "Não localizado",
        "cnpj_formatted": "Não localizado",
        "situacao_cadastral": "NÃO LOCALIZADO",
        "razao_social": "",
        "porte": "Não identificado",
        "socios_str": "Proprietário não identificado",
        "data_inicio_atividade": "",
        "cnae_fiscal_descricao": "",
        "capital_social": 0.0,
        "regime": "Não identificado",
    }
    database.update_lead_cnpj(lead_id, not_found_data)
    database.add_log(f"Busca de CNPJ para o Lead #{lead_id} ({lead_name}) concluída: Registro público não localizado.", "INFO")

    return {
        "success": False,
        "lead_id": lead_id,
        "lead_name": lead_name,
        "error": "CNPJ não localizado nos registros públicos da Receita Federal.",
        "data": not_found_data,
    }

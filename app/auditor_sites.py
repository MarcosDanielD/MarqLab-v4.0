"""
Website Auditor and Technical Qualification Module.
Inspects website performance, mobile viewport presence, SSL certificates,
HTTP status codes, and legacy frameworks to identify sales opportunities.
"""

import time
import re
from typing import Dict, Any, Tuple
import requests
from bs4 import BeautifulSoup


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
}


def audit_website(url: str) -> Dict[str, Any]:
    """
    Performs quick, non-intrusive audit of a target website.
    Returns diagnostic status, detected flaws, and qualification summary.
    """
    if not url or not url.strip():
        return {
            "status": "Prioridade Crítica: Sem Site",
            "detail": "Empresa sem nenhum website cadastrado no Google",
            "is_broken": True,
            "has_ssl": False,
            "is_mobile_responsive": False,
            "response_time": 0.0,
            "http_status": 0,
            "opportunity_reasons": ["Sem presença web própria", "Perda direta de cliques do Google Maps para concorrentes"]
        }

    raw_url = url.strip()
    if not raw_url.startswith("http://") and not raw_url.startswith("https://"):
        target_url = "http://" + raw_url
    else:
        target_url = raw_url

    opportunity_reasons = []
    is_broken = False
    has_ssl = target_url.startswith("https://")
    is_mobile_responsive = True
    response_time = 0.0
    http_status = 200

    start_time = time.time()
    try:
        # First attempt with short timeout (5s)
        response = requests.get(
            target_url,
            headers=HEADERS,
            timeout=5.0,
            verify=False,  # Don't crash on self-signed/expired corporate/broken SSL
            allow_redirects=True
        )
        response_time = round(time.time() - start_time, 2)
        http_status = response.status_code

        # Check final URL for SSL
        if response.url.startswith("https://"):
            has_ssl = True
        else:
            has_ssl = False
            opportunity_reasons.append("Não possui SSL seguro (HTTP desprotegido)")

        # Check HTTP status
        if response.status_code >= 400:
            is_broken = True
            opportunity_reasons.append(f"Site fora do ar ou com erro (Status HTTP {response.status_code})")

        # Parse HTML
        soup = BeautifulSoup(response.text[:200000], "html.parser")

        # 1. Check Mobile Viewport
        viewport_meta = soup.find("meta", attrs={"name": re.compile(r"viewport", re.I)})
        if not viewport_meta:
            is_mobile_responsive = False
            opportunity_reasons.append("Layout não responsivo (sem meta viewport para celulares)")

        # 2. Check Load Time
        if response_time > 3.5:
            opportunity_reasons.append(f"Carregamento muito lento ({response_time}s para abrir)")

        # 3. Check outdated HTML constructs (frames, table layouts)
        if soup.find("frameset") or soup.find("frame"):
            opportunity_reasons.append("Estrutura obsoleta com frames")
        
        tables = soup.find_all("table")
        if len(tables) > 8 and not soup.find("main") and not soup.find("section"):
            opportunity_reasons.append("Visual antigo estruturado em tabelas HTML")

        # 4. Check copyright year in footer if very old
        footer_text = soup.get_text()
        old_year_match = re.search(r"©\s*(200\d|201[0-8])", footer_text)
        if old_year_match:
            opportunity_reasons.append(f"Última atualização aparente em {old_year_match.group(1)} (site abandonado)")

    except requests.exceptions.SSLError:
        response_time = round(time.time() - start_time, 2)
        is_broken = True
        has_ssl = False
        opportunity_reasons.append("Certificado SSL expirado ou inválido (Aviso de site perigoso)")
    except requests.exceptions.Timeout:
        response_time = 5.0
        is_broken = True
        opportunity_reasons.append("Tempo limite esgotado (> 5s) - Servidor instável ou fora do ar")
    except requests.exceptions.ConnectionError:
        response_time = round(time.time() - start_time, 2)
        is_broken = True
        opportunity_reasons.append("Falha de conexão com o servidor (Domínio inativo ou DNS incorreto)")
    except Exception as e:
        response_time = round(time.time() - start_time, 2)
        is_broken = True
        opportunity_reasons.append(f"Erro ao acessar site: {str(e)[:40]}")

    # Determine classification
    if is_broken or len(opportunity_reasons) > 0:
        status = "Oportunidade: Modernização de Site"
        detail = " | ".join(opportunity_reasons) if opportunity_reasons else "Necessita de modernização comercial"
    else:
        status = "Site Ativo (Baixa Prioridade)"
        detail = f"Site online ({response_time}s), responsivo e com SSL"

    return {
        "status": status,
        "detail": detail,
        "is_broken": is_broken,
        "has_ssl": has_ssl,
        "is_mobile_responsive": is_mobile_responsive,
        "response_time": response_time,
        "http_status": http_status,
        "opportunity_reasons": opportunity_reasons,
    }

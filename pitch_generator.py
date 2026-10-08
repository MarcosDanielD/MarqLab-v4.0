"""
Pitch Generator and Lead Scoring Module for Growth Hacking B2B.
Generates tailored Cold Call scripts, objection handling, and 1-Click WhatsApp messages,
plus computes a comprehensive digital maturity score (0-100).
"""

import re
import math
import urllib.parse
import urllib.request
from typing import Dict, Any, Tuple, Optional

# Coordenadas da base do usuário: R. Lótus, 450 - Campina da Barra, Araucária - PR, 83709-500
USER_BASE_LAT = -25.61742
USER_BASE_LON = -49.36540
USER_BASE_ADDRESS = "R. Lótus, 450 - Campina da Barra, Araucária - PR"


def calculate_distance_km(lat: float, lon: float, base_lat: float = USER_BASE_LAT, base_lon: float = USER_BASE_LON) -> float:
    """Calcula a distância em quilômetros via fórmula de Haversine."""
    R = 6371.0  # Raio da Terra em km
    dlat = math.radians(lat - base_lat)
    dlon = math.radians(lon - base_lon)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(base_lat)) * math.cos(math.radians(lat)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return round(R * c, 1)


def extract_coords_from_url(maps_url: str) -> Tuple[Optional[float], Optional[float]]:
    """Extrai latitude e longitude de URLs do Google Maps."""
    if not maps_url:
        return None, None
    m1 = re.search(r"@(-?\d+\.\d+),(-?\d+\.\d+)", maps_url)
    if m1:
        try:
            return float(m1.group(1)), float(m1.group(2))
        except Exception:
            pass
    m2 = re.search(r"!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)", maps_url)
    if m2:
        try:
            return float(m2.group(1)), float(m2.group(2))
        except Exception:
            pass
    return None, None


def estimate_distance_from_address(address: str, maps_url: str = "") -> float:
    """Calcula ou estima a distância em km a partir das coordenadas do Maps ou do endereço."""
    lat, lon = extract_coords_from_url(maps_url)
    if lat is not None and lon is not None:
        return calculate_distance_km(lat, lon)

    # Estimativa de proximidade por cidade/bairro em relação a Campina da Barra, Araucária
    addr_lower = (address or "").lower()
    if "campina da barra" in addr_lower or "lótus" in addr_lower or "lotus" in addr_lower:
        return 0.5
    elif "araucária" in addr_lower or "araucaria" in addr_lower:
        return 4.2
    elif "fazenda rio grande" in addr_lower:
        return 14.5
    elif "campo largo" in addr_lower:
        return 22.0
    elif "curitiba" in addr_lower:
        return 19.8
    elif "são josé dos pinhais" in addr_lower or "sao jose" in addr_lower:
        return 27.5
    elif "pinhais" in addr_lower or "colombo" in addr_lower:
        return 31.0
    return 5.0



def calculate_lead_score(
    qualification_status: str,
    rating: float,
    reviews_count: int,
    phone: str,
    website: str,
    audit_data: Dict[str, Any]
) -> Tuple[int, str]:
    """
    Computes Lead Opportunity Score (0-100) and Temperature badge.
    High reviews + High rating + Broken/Missing site = Ultra Hot Lead.
    """
    score = 0

    # 1. Base status score
    if "Sem Site" in qualification_status:
        score += 50
    elif "Modernização" in qualification_status:
        score += 40
        if not audit_data.get("is_mobile_responsive", True):
            score += 10
        if not audit_data.get("has_ssl", True):
            score += 5
        if audit_data.get("is_broken", False):
            score += 10
    else:
        score += 15

    # 2. Local Market Authority & Traffic (Reviews)
    if reviews_count >= 100:
        score += 25
    elif reviews_count >= 50:
        score += 20
    elif reviews_count >= 20:
        score += 15
    elif reviews_count >= 5:
        score += 10

    # 3. Customer Satisfaction / Reputation (Rating)
    if rating >= 4.7:
        score += 15
    elif rating >= 4.3:
        score += 10
    elif rating >= 3.8:
        score += 5

    # 4. Actionability (Valid phone/WhatsApp)
    if phone and len(re.sub(r"\D", "", phone)) >= 10:
        score += 10

    # Cap score between 10 and 100
    final_score = max(15, min(100, score))

    if final_score >= 80:
        temperature = "Alta Prioridade"
    elif final_score >= 60:
        temperature = "Média Prioridade"
    else:
        temperature = "Prioridade Normal"

    return final_score, temperature


def detect_phone_type(raw_phone: str) -> str:
    """
    Detects if Brazilian phone number is a mobile/WhatsApp (9 digits starting with 9)
    or a landline/fixo (8 digits starting with 2, 3, 4, 5).
    Returns 'whatsapp' or 'landline' or 'none'.
    """
    if not raw_phone:
        return "none"
    digits = re.sub(r"\D", "", raw_phone)
    if digits.startswith("0"):
        digits = digits[1:]
    if digits.startswith("55"):
        digits = digits[2:]

    # Brazilian DDD + Number
    if len(digits) >= 10:
        local_num = digits[2:]
        if len(local_num) == 9 and local_num.startswith("9"):
            return "whatsapp"
        elif len(local_num) == 8 and local_num[0] in ["2", "3", "4", "5"]:
            return "landline"
        elif len(local_num) == 9:
            return "whatsapp"
    elif len(digits) == 9 and digits.startswith("9"):
        return "whatsapp"
    elif len(digits) == 8:
        return "landline"

    return "unknown"


def clean_phone_number(raw_phone: str) -> str:
    """Extracts numeric digits and formats for Brazilian WhatsApp (DDI 55 + DDD + Number)."""
    if not raw_phone:
        return ""
    digits = re.sub(r"\D", "", raw_phone)
    # Remove leading zero from DDD if present (e.g., 011 -> 11)
    if digits.startswith("0") and len(digits) in [11, 12]:
        digits = digits[1:]
    # If 10 or 11 digits, add 55 (Brazil DDI)
    if len(digits) in [10, 11]:
        return f"55{digits}"
    if len(digits) in [12, 13] and digits.startswith("55"):
        return digits
    return digits


def resolve_google_ad_url(url: str) -> str:
    """Extracts or follows Google /aclk or redirect links to obtain the real company website URL."""
    if not url:
        return ""
    url = str(url).strip()
    if "/aclk" in url or "google.com/url" in url or "adurl=" in url:
        # 1. Direct query parameter extraction (zero network latency)
        m = re.search(r"[?&](?:adurl|q)=([^&]+)", url)
        if m:
            extracted = urllib.parse.unquote(m.group(1)).strip()
            if extracted.startswith("http://") or extracted.startswith("https://"):
                return extracted
            elif extracted.startswith("www."):
                return f"https://{extracted}"

        # 2. Handle root relative paths
        if url.startswith("/"):
            url = f"https://www.google.com{url}"

        # 3. Follow HTTP 302 redirect if necessary
        try:
            class NoRedirect(urllib.request.HTTPRedirectHandler):
                def redirect_request(self, req, fp, code, msg, headers, newurl):
                    self.target_url = newurl
                    return None
            handler = NoRedirect()
            opener = urllib.request.build_opener(handler)
            opener.addheaders = [("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")]
            try:
                opener.open(url, timeout=4)
            except Exception:
                if hasattr(handler, "target_url") and handler.target_url:
                    return handler.target_url
        except Exception:
            pass
    return url


def clean_site_display(url: str) -> str:
    """Returns a short, clean domain name without query tracking parameters for scripts and PDF."""
    if not url:
        return ""
    url = str(url).strip()
    if "wa.me" in url or "whatsapp.com" in url:
        return "link do WhatsApp"

    # Extract target url if it's a tracking redirect
    m = re.search(r"[?&](?:adurl|q)=([^&]+)", url)
    if m:
        extracted = urllib.parse.unquote(m.group(1)).strip()
        if extracted:
            url = extracted

    # Remove protocol (http/https) and leading www.
    u = re.sub(r"^https?://", "", url, flags=re.I)
    u = re.sub(r"^www\.", "", u, flags=re.I)

    # Remove query string (?...) and anchor (#...)
    u = re.sub(r"[?#].*$", "", u)
    u = u.rstrip("/")

    if u.startswith("google.com/aclk") or "/aclk" in u:
        return "site no Google"

    # If long path, isolate base domain
    if "/" in u:
        domain = u.split("/")[0]
        if len(domain) > 3:
            u = domain

    # Strict length boundary for clean print
    if len(u) > 32:
        u = u[:29] + "..."
    return u or "site"



def generate_scripts(lead_data: Dict[str, Any], niche: str = "sua área", city: str = "") -> Dict[str, str]:
    """
    Generates high-conversion Cold Call and 3-Step WhatsApp outreach scripts
    specifically pitching a Landing Page / Redesign project for R$ 1.000,00.
    """
    name = lead_data.get("name", "Empresa")
    rating = float(lead_data.get("rating") or 0.0)
    reviews = int(lead_data.get("reviews_count") or 0)
    phone = lead_data.get("phone", "")
    clean_phone = clean_phone_number(phone)
    phone_type = detect_phone_type(phone)
    website = lead_data.get("website", "")
    display_site = clean_site_display(website)
    qual_status = lead_data.get("qualification_status", "")
    qual_detail = lead_data.get("qualification_detail", "")

    # Contextual hook based on review volume
    if reviews >= 50:
        reputation_hook = f"parabenizar pelo volume de {reviews} avaliações e nota {rating:.1f} no Google Maps em {city or 'sua região'}"
    elif reviews >= 10:
        reputation_hook = f"parabenizar pela reputação sólida de {rating:.1f} estrelas com {reviews} clientes no Google"
    else:
        reputation_hook = f"parabenizar pelo trabalho de referência como {niche} em {city or 'nossa região'}"

    # Pain point hook
    if "Sem Site" in qual_status:
        pain_hook = (
            "notei que quando os clientes pesquisam pela sua empresa no Google, "
            "vocês ainda não possuem um Website ou Landing Page oficial cadastrado. "
            "Hoje, a maioria das pessoas que pesquisam no Maps preferem clicar no link antes de ligar e "
            "muitas acabam buscando o concorrente que já tem uma página direta."
        )
        wp_pain = (
            "Notei que o perfil de vocês tem ótimo destaque nas buscas do Google, mas não tem um site oficial cadastrado. "
            "Muitos clientes em potencial acabam desistindo por não acharem uma página rápida com WhatsApp direto."
        )
    else:
        site_mention = f"o site atual de vocês ({display_site})" if display_site else "o site cadastrado de vocês"
        pain_hook = (
            f"ao analisar a presença digital de vocês, vi que {site_mention} está apresentando "
            f"algumas limitações ({qual_detail or 'falta de adaptação para celular ou instabilidade'}). "
            "No smartphone, isso faz o visitante esperar ou desistir do contato."
        )
        wp_pain = (
            f"Fui consultar {site_mention} e notei que ele não está responsivo para celulares "
            f"ou está com carregamento lento, o que acaba perdendo oportunidades que chegam pelo Google Maps."
        )

    # Cold Call Structured Telemarketing Script
    cold_call_script = f"""ROTEIRO DE PROSPECCAO - {name.upper()}
Nicho: {niche.title()} | Regiao: {city.title()}
Proposta: Landing Page de Alta Conversao - R$ 1.000,00

1. [QUEBRA DE GELO E ABORDAGEM]
"Ola, tudo bem? Meu nome e [Seu Nome], falo com o responsavel pelo atendimento ou comercial da {name}?"
(Aguarde confirmacao)
"O motivo do meu contato e que eu estava analisando as principais empresas de {niche} aqui de {city or 'sua cidade'} e fiz questao de ligar para {reputation_hook}."

2. [DIAGNOSTICO E OPORTUNIDADE]
"Porem, notei um ponto importante: {pain_hook}"

3. [SOLUCAO E PROPOSTA COMERCIAL]
"Nos desenvolvemos Landing Pages profissionais prontas em ate 72 horas, totalmente adaptadas para celular, com botao de WhatsApp direto e focadas em converter quem pesquisa no Google em clientes pagantes.
O investimento e um valor unico de R$ 1.000,00, sem mensalidades recorrentes."

4. [PASSO SEGUINTE / AGENDAMENTO]
"Eu montei uma previa de como ficaria a estrutura ideal para a {name}. Posso te enviar em 2 minutos no seu WhatsApp agora ou podemos marcar uma conversa rapida de 10 minutos para eu te apresentar?"

-----------------------------------------------------
TRATAMENTO DE OBJECOES:
• Objeção: "Já temos Instagram, não precisamos de site."
  -> Resposta: "O Instagram é ótimo para conteúdo, mas quando alguém está com urgência no Google Maps, quer clicar e falar no WhatsApp em 5 segundos. O site converte o cliente que já está pronto para comprar hoje."

• Objeção: "Não temos interesse ou verba agora."
  -> Resposta: "Entendo perfeitamente. Por isso trabalhamos com valor fixo de R$ 1.000,00, onde um único cliente a mais que você fechar no mês já cobre todo o investimento."

• Objeção: "Manda por e-mail."
  -> Resposta: "Com certeza. Para facilitar seu dia a dia, posso enviar direto no seu WhatsApp com 3 pontos práticos que identifiquei?"
"""

    # 1. WhatsApp Passo 1 (Abordagem Inicial - Diagnóstico)
    whatsapp_text = (
        f"Olá, tudo bem? Aqui é da equipe da Marq Lab.\n\n"
        f"Estava analisando as principais empresas de {niche} em {city or 'sua região'} e encontrei o perfil da *{name}* no Google Maps com ótima reputação ({rating:.1f} estrelas).\n\n"
        f"{wp_pain}\n\n"
        f"Desenvolvemos Landing Pages modernas, rápidas e com botão de WhatsApp integrado por taxa única de R$ 1.000,00 (sem mensalidades).\n\n"
        f"Preparei uma prévia de como ficaria a página da {name}. Posso te enviar aqui para você avaliar sem compromisso?"
    )

    # 2. WhatsApp Passo 2 (Follow-up D+2 - Exemplo de case/conversão)
    whatsapp_followup_1 = (
        f"Olá, tudo bem? Passando rapidamente só para dar um retorno sobre a mensagem anterior.\n\n"
        f"Recentemente reformulamos a presença web de outra empresa do mesmo segmento e eles aumentaram em mais de 40% os chamados recebidos no WhatsApp vindos do Google.\n\n"
        f"Como o investimento na {name} é apenas R$ 1.000,00 pago uma única vez, um único cliente novo já cobre todo o projeto.\n\n"
        f"Gostaria de ver o protótipo rápido que estruturei para vocês?"
    )

    # 3. WhatsApp Passo 3 (Follow-up D+5 - Quebra de Contato com Escassez)
    whatsapp_followup_2 = (
        f"Olá! Imagino que a rotina esteja corrida por aí na {name}.\n\n"
        f"Estou fechando o cronograma de entregas de Landing Pages desta semana da Marq Lab e temos apenas 2 vagas com o valor promocional de R$ 1.000,00.\n\n"
        f"Caso ainda faça sentido modernizar a captação de clientes de vocês este mês, me avise por aqui para garantirmos a sua vaga!"
    )

    # Resumo da Proposta Comercial em Texto
    proposal_text = (
        f"📋 *PROPOSTA COMERCIAL - MARQ LAB*\n"
        f"*Cliente:* {name}\n"
        f"*Projeto:* Landing Page Corporativa de Alta Conversão\n"
        f"*Escopo:*\n"
        f"• Design Moderno e 100% Responsivo para Celular\n"
        f"• Botão de WhatsApp Flutuante com Mensagem Prévia\n"
        f"• Certificado de Segurança SSL Incluso (HTTPS)\n"
        f"• Otimização para Busca Local no Google Maps\n"
        f"• Prazo de Entrega: até 5 dias úteis\n\n"
        f"*Investimento:* R$ 1.000,00 (Valor Único)\n"
        f"*Condição:* 50% de entrada (R$ 500) + 50% na aprovação final (R$ 500)\n\n"
        f"Fico à disposição para iniciarmos o projeto hoje mesmo!"
    )

    encoded_whatsapp_url = ""
    encoded_followup_1_url = ""
    encoded_followup_2_url = ""
    if clean_phone:
        encoded_whatsapp_url = f"https://wa.me/{clean_phone}?text={urllib.parse.quote(whatsapp_text)}"
        encoded_followup_1_url = f"https://wa.me/{clean_phone}?text={urllib.parse.quote(whatsapp_followup_1)}"
        encoded_followup_2_url = f"https://wa.me/{clean_phone}?text={urllib.parse.quote(whatsapp_followup_2)}"

    return {
        "cold_call_script": cold_call_script,
        "whatsapp_script": whatsapp_text,
        "whatsapp_followup_1": whatsapp_followup_1,
        "whatsapp_followup_2": whatsapp_followup_2,
        "whatsapp_url": encoded_whatsapp_url,
        "followup_1_url": encoded_followup_1_url,
        "followup_2_url": encoded_followup_2_url,
        "proposal_text": proposal_text,
        "phone_type": phone_type,
    }


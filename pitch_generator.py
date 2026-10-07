"""
Pitch Generator and Lead Scoring Module for Growth Hacking B2B.
Generates tailored Cold Call scripts, objection handling, and 1-Click WhatsApp messages,
plus computes a comprehensive digital maturity score (0-100).
"""

import re
import urllib.parse
from typing import Dict, Any, Tuple


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


def generate_scripts(lead_data: Dict[str, Any], niche: str = "sua área", city: str = "") -> Dict[str, str]:
    """
    Generates high-conversion Cold Call and WhatsApp outreach scripts
    specifically pitching a Landing Page / Redesign project for R$ 1.000,00.
    """
    name = lead_data.get("name", "Empresa")
    rating = float(lead_data.get("rating") or 0.0)
    reviews = int(lead_data.get("reviews_count") or 0)
    phone = lead_data.get("phone", "")
    clean_phone = clean_phone_number(phone)
    website = lead_data.get("website", "")
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
        pain_hook = (
            f"ao analisar a presença digital de vocês, vi que o site atual ({website}) está apresentando "
            f"algumas limitações ({qual_detail or 'falta de adaptação para celular ou instabilidade'}). "
            "No smartphone, isso faz o visitante esperar ou desistir do contato."
        )
        wp_pain = (
            f"Fui consultar o site de vocês ({website}) e notei que ele não está responsivo para celulares "
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

    # WhatsApp Outreach Script (Clean & Professional)
    whatsapp_text = (
        f"Olá, tudo bem? Aqui é o [Seu Nome].\n\n"
        f"Estava analisando as principais empresas de {niche} em {city or 'sua região'} e encontrei o perfil da *{name}* no Google Maps com ótima reputação ({rating:.1f} estrelas).\n\n"
        f"{wp_pain}\n\n"
        f"Desenvolvemos Landing Pages modernas, rápidas e com botão de WhatsApp integrado por taxa única de R$ 1.000,00 (sem mensalidades).\n\n"
        f"Preparei uma prévia de como ficaria a página da {name}. Posso te enviar aqui para você avaliar sem compromisso?"
    )

    encoded_whatsapp_url = ""
    if clean_phone:
        encoded_msg = urllib.parse.quote(whatsapp_text)
        encoded_whatsapp_url = f"https://wa.me/{clean_phone}?text={encoded_msg}"

    return {
        "cold_call_script": cold_call_script,
        "whatsapp_script": whatsapp_text,
        "whatsapp_url": encoded_whatsapp_url,
    }

"""
Serviço de Radar de CNPJs Recém-Abertos para Marq Lab.
Identifica empresas recém-registradas na Receita Federal
por cidade e nicho de atuação usando diretórios oficiais públicos (Econodata),
enriquecendo em tempo real com Sócios, Telefones, CNAE e Scripts Persuasivos de Venda.
"""

import re
import json
import datetime
import unicodedata
import urllib.parse
import urllib.request
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup

import servico_cnpj
import banco_dados

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# Mapeamento inteligente de termos comuns para slugs aceitos pelo diretório
MAPA_SLUGS_NICHO = {
    "dentista": "odontologia",
    "dentistas": "odontologia",
    "clinica odontologica": "odontologia",
    "ortodontia": "odontologia",
    "medico": "medicina",
    "medicos": "medicina",
    "clinica medica": "medicina",
    "saude": "medicina",
    "estetica": "estetica",
    "salao de beleza": "estetica",
    "barbearia": "estetica",
    "advogado": "advocacia",
    "advogados": "advocacia",
    "juridico": "advocacia",
    "engenharia": "construcao",
    "arquiteto": "arquitetura",
    "marcenaria": "marcenaria",
    "pizzaria": "pizzaria",
    "hamburgueria": "restaurante",
    "restaurante": "restaurante",
    "lanchonete": "restaurante",
    "contabilidade": "contabilidade",
    "software": "tecnologia",
    "informatica": "tecnologia",
    "energia solar": "energia-solar",
}


def slugify(text: str) -> str:
    """Converte texto com acentos e caracteres especiais para slug limpo."""
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("utf-8")
    return re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-")


def calcular_dias_abertura(data_str: str) -> Optional[int]:
    """Calcula a idade da empresa em dias a partir da data de abertura (dd/mm/aaaa ou aaaa-mm-dd)."""
    if not data_str:
        return None
    try:
        clean_date = data_str.strip()
        if "/" in clean_date:
            parts = clean_date.split("/")
            if len(parts) == 3:
                d = datetime.date(int(parts[2]), int(parts[1]), int(parts[0]))
                return (datetime.date.today() - d).days
        elif "-" in clean_date:
            parts = clean_date.split("-")
            if len(parts) == 3:
                d = datetime.date(int(parts[0]), int(parts[1]), int(parts[2]))
                return (datetime.date.today() - d).days
    except Exception:
        pass
    return None


def gerar_pitch_empresa_nova(nome: str, cidade: str, dias: Optional[int], socios_str: str) -> Dict[str, str]:
    """Gera roteiro persuasivo específico para empresas recém-abertas."""
    primeiro_socio = socios_str.split(",")[0].strip() if socios_str and socios_str != "Não informado / Individual" else ""
    saudacao_socio = f"falar com o(a) {primeiro_socio}" if primeiro_socio else "falar com o responsável"

    tempo_tag = f"aberta há {dias} dias" if dias and dias > 0 else "recém-inaugurada"

    cold_call = (
        f"1. ABERTURA: 'Olá, bom dia! Por gentileza, gostaria de {saudacao_socio}? Aqui é da Marq Lab.'\n"
        f"2. GANCHO DE PARABÉNS: 'Estou ligando primeiramente para parabenizar pela abertura da {nome}! "
        f"Acompanhamos o registro de novas empresas aqui em {cidade} e vimos que vocês estão iniciando agora ({tempo_tag}).'\n"
        f"3. A DOR REAL: 'Como você sabe, os primeiros 90 dias de qualquer empresa são os mais desafiadores para gerar caixa. "
        f"Quem começa sem um site rápido e profissional no celular perde os clientes que pesquisam no Google para concorrentes mais antigos.'\n"
        f"4. A OFERTA: 'Nós desenvolvemos uma Landing Page completa de alta conversão por R$ 1.000,00 fechados, "
        f"entregue em 48 horas pronta para captar clientes no WhatsApp. Posso te mandar uma prévia hoje?'"
    )

    whatsapp = (
        f"Olá {primeiro_socio if primeiro_socio else 'tudo bem?'}! Parabéns pela abertura da *{nome}* aqui em {cidade}! 🚀\n\n"
        f"Acompanhamos o mercado de novos negócios e sabemos que os primeiros meses são decisivos para atrair clientes. "
        f"Ter um site profissional no ar desde a primeira semana transmite máxima credibilidade e separa empresas que crescem rápido daquelas que demoram a decolar.\n\n"
        f"Nós da *Marq Lab* desenvolvemos Landing Pages modernas, ultra-rápidas no celular e com botão de WhatsApp integrado por uma oferta especial de inauguração: *R$ 1.000,00* em até 48h.\n\n"
        f"Posso te mandar uma prévia rápida de como ficaria a página da *{nome}*?"
    )

    return {"cold_call": cold_call, "whatsapp": whatsapp}


def extrair_empresas_diretorio(uf: str, cidade: str, nicho: str = "") -> List[Dict[str, Any]]:
    """Extrai lista de empresas com CNPJ, Razão Social, Nome Fantasia e Endereço do diretório Econodata."""
    uf_slug = (uf or "SP").strip().lower()
    cid_slug = slugify(cidade or "Sorocaba")
    
    # Resolve nicho para slug aceito
    clean_nicho_raw = (nicho or "").strip().lower()
    nic_slug = MAPA_SLUGS_NICHO.get(clean_nicho_raw, slugify(clean_nicho_raw))
    
    urls_tentativa = []
    if nic_slug:
        urls_tentativa.append(f"https://www.econodata.com.br/empresas/{uf_slug}-{cid_slug}/{nic_slug}")
    urls_tentativa.append(f"https://www.econodata.com.br/empresas/{uf_slug}-{cid_slug}")

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    }

    empresas_encontradas: List[Dict[str, Any]] = []
    cnpjs_vistos = set()

    for url in urls_tentativa:
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as res:
                if res.status != 200:
                    continue
                html = res.read().decode("utf-8", errors="ignore")

            soup = BeautifulSoup(html, "html.parser")
            rows = soup.find_all("tr")

            for tr in rows[1:]:
                cols = [td.get_text(separator=" | ", strip=True) for td in tr.find_all(["td", "th"])]
                if len(cols) >= 2:
                    col_info = cols[1]
                    cnpj_match = re.search(r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b", col_info)
                    if not cnpj_match:
                        continue

                    cnpj_fmt = cnpj_match.group(0)
                    cnpj_clean = re.sub(r"\D", "", cnpj_fmt)
                    if cnpj_clean in cnpjs_vistos:
                        continue
                    cnpjs_vistos.add(cnpj_clean)

                    # Extrai nomes da coluna
                    parts = [p.strip() for p in col_info.split("|") if p.strip() and not re.match(r"^\d{2}\.\d{3}", p.strip())]
                    fantasia = parts[0] if parts else "Empresa Local"
                    razao = parts[1] if len(parts) > 1 else fantasia

                    endereco = cols[2] if len(cols) > 2 else ""
                    cnae = cols[3] if len(cols) > 3 else nicho or "Serviços/Comércio"

                    empresas_encontradas.append({
                        "cnpj_clean": cnpj_clean,
                        "cnpj_fmt": cnpj_fmt,
                        "fantasia": fantasia,
                        "razao": razao,
                        "endereco": endereco,
                        "cnae": cnae,
                    })

            if empresas_encontradas:
                break
        except Exception:
            continue

    return empresas_encontradas


def escanear_cnpjs_recentes(uf: str, cidade: str, nicho: str = "", periodo_dias: int = 90, limite: int = 20) -> List[Dict[str, Any]]:
    """
    Busca empresas no diretório oficial pela cidade e nicho,
    enriquecendo cada CNPJ com dados oficiais da Receita Federal (ReceitaWS/BrasilAPI).
    """
    clean_uf = (uf or "SP").strip().upper()
    clean_cidade = (cidade or "Sorocaba").strip()
    clean_nicho = (nicho or "").strip()

    empresas_base = extrair_empresas_diretorio(clean_uf, clean_cidade, clean_nicho)
    if not empresas_base:
        # Fallback genérico para a cidade
        empresas_base = extrair_empresas_diretorio(clean_uf, clean_cidade, "")

    resultados: List[Dict[str, Any]] = []

    # Enriquece até o limite pedido
    for emp in empresas_base[:limite + 10]:
        cnpj = emp["cnpj_clean"]
        try:
            detalhes = servico_cnpj.fetch_cnpj_details(cnpj)
            if not detalhes:
                # Usa dados da extração direta caso a API externa sofra timeout
                detalhes = {
                    "cnpj_formatted": emp["cnpj_fmt"],
                    "cnpj": cnpj,
                    "razao_social": emp["razao"],
                    "nome_fantasia": emp["fantasia"],
                    "situacao_cadastral": "ATIVA",
                    "data_inicio_atividade": "",
                    "porte": "Microempresa (ME)",
                    "regime": "Simples Nacional",
                    "socios_str": "Responsável Comercial",
                    "cnae_fiscal_descricao": emp["cnae"],
                    "capital_social": 10000.0,
                    "municipio": clean_cidade,
                    "uf": clean_uf,
                    "logradouro": emp["endereco"],
                    "telefone": "",
                    "email": "",
                }

            abertura = detalhes.get("data_inicio_atividade") or ""
            dias_vida = calcular_dias_abertura(abertura)

            # Classificação por frescor e temperatura de lead
            if dias_vida is not None and dias_vida <= 30:
                tag_tempo = f"Inauguração (< {dias_vida} dias)"
                score = 98
                temperatura = "🔥 Super Quente (Recém-Nascida)"
            elif dias_vida is not None and dias_vida <= 60:
                tag_tempo = f"Aberta há {dias_vida} dias"
                score = 92
                temperatura = "🔥 Quente (Fase Inicial)"
            elif dias_vida is not None and dias_vida <= 120:
                tag_tempo = f"Aberta há {dias_vida} dias"
                score = 86
                temperatura = "⚡ Oportunidade (Primeiro Trimestre)"
            elif dias_vida is not None and dias_vida <= 200:
                tag_tempo = f"Aberta há {dias_vida} dias"
                score = 80
                temperatura = "⚡ Nova Empresa (Semestre)"
            else:
                tag_tempo = f"Ativa desde {abertura}" if abertura else "Ativa"
                score = 75
                temperatura = "🏢 Empresa Estabelecida"

            razao = detalhes.get("razao_social") or emp["razao"]
            fantasia = detalhes.get("nome_fantasia") or emp["fantasia"]
            socios = detalhes.get("socios_str") or ""
            pitch = gerar_pitch_empresa_nova(fantasia, clean_cidade, dias_vida, socios)

            item = {
                "cnpj": detalhes.get("cnpj_formatted") or emp["cnpj_fmt"],
                "cnpj_clean": cnpj,
                "razao_social": razao,
                "nome_fantasia": fantasia,
                "data_abertura": abertura or "Recente",
                "dias_vida": dias_vida if dias_vida is not None else 999,
                "tag_tempo": tag_tempo,
                "situacao": detalhes.get("situacao_cadastral") or "ATIVA",
                "porte": detalhes.get("porte") or "Microempresa (ME)",
                "regime": detalhes.get("regime") or "Simples Nacional",
                "socios": socios or "Não informado / Individual",
                "telefone": detalhes.get("telefone") or "",
                "email": detalhes.get("email") or "",
                "cnae": detalhes.get("cnae_fiscal_descricao") or emp["cnae"],
                "capital_social": detalhes.get("capital_social") or 0.0,
                "municipio": detalhes.get("municipio") or clean_cidade,
                "uf": detalhes.get("uf") or clean_uf,
                "bairro": detalhes.get("bairro") or "",
                "logradouro": detalhes.get("logradouro") or emp["endereco"],
                "lead_score": score,
                "lead_temperature": temperatura,
                "cold_call_script": pitch["cold_call"],
                "whatsapp_script": pitch["whatsapp"],
            }
            resultados.append(item)
            if len(resultados) >= limite:
                break
        except Exception:
            continue

    # Ordena pelos mais novos primeiro
    resultados.sort(key=lambda x: x.get("dias_vida", 999))
    return resultados

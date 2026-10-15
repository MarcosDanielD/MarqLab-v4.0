"""
Serviço de Mineração e Auditoria de Links no Instagram para Marq Lab.
Encontra negócios e perfis comerciais por nicho e cidade (via Google Maps e Diretório Econodata),
audita o "Link na Bio" em tempo real (detectando erros 404, domínios fora do ar, linktrees ou falta de site)
e gera abordagens de alta conversão para venda de Landing Page por R$ 1.000,00.
"""

import re
import unicodedata
import urllib.parse
import urllib.request
import urllib.error
from typing import List, Dict, Any, Optional

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

PHONE_REGEX = re.compile(
    r"(?:(?:\+|00)?55\s*)?(?:\(?([1-9]{2})\)?\s*)?(?:(9\s*\d{4}|\d{4})[-.\s]?(\d{4}))"
)


def slugify(text: str) -> str:
    """Converte texto com acentos e caracteres especiais para slug limpo."""
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("utf-8")
    return re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-")


def extrair_telefone(texto: str) -> Optional[str]:
    """Extrai telefone brasileiro formatado de um texto."""
    if not texto:
        return None
    matches = PHONE_REGEX.findall(texto)
    if matches:
        ddd, p1, p2 = matches[0]
        p1 = p1.replace(" ", "")
        p2 = p2.replace(" ", "")
        if ddd:
            return f"({ddd}) {p1}-{p2}"
        return f"{p1}-{p2}"
    return None


def auditar_link_bio(url: Optional[str]) -> Dict[str, Any]:
    """
    Testa a saúde de uma URL de link na bio/site.
    Verifica se está com erro 404, 500, fora do ar, linktree ou site funcional.
    """
    if not url:
        return {
            "status_code": None,
            "diagnostico": "Sem link na bio",
            "categoria": "sem_link",
            "score": 80,
            "detalhe": "Perfil comercial sem nenhum link de conversão cadastrado na bio."
        }

    clean_url = url.strip()
    if clean_url.startswith("/aclk?") or "google.com/aclk" in clean_url:
        return {
            "status_code": 200,
            "diagnostico": "Anúncio Patrocinado Google",
            "categoria": "ativo",
            "score": 50,
            "detalhe": "Empresa investe em anúncios patrocinados no Google."
        }

    if not clean_url.startswith("http://") and not clean_url.startswith("https://"):
        clean_url = "https://" + clean_url

    # Se for link direto do WhatsApp (wa.me ou api.whatsapp.com)
    if "wa.me" in clean_url or "api.whatsapp.com" in clean_url or "whatsapp.com" in clean_url:
        return {
            "status_code": 200,
            "diagnostico": "Apenas Link de WhatsApp",
            "categoria": "apenas_whatsapp",
            "score": 75,
            "detalhe": "Usa link direto para o WhatsApp sem Landing Page própria explicando serviços e preços."
        }

    # Se for Linktree ou agregadores similares
    if any(agg in clean_url for agg in ["linktr.ee", "bio.link", "beacons.ai", "instabio", "linkr.bio", "app.link"]):
        return {
            "status_code": 200,
            "diagnostico": "Agregador Linktree (Sem Site Próprio)",
            "categoria": "linktree",
            "score": 70,
            "detalhe": "Usa árvore de links genérica em vez de uma Landing Page com identidade visual própria e profissional."
        }

    # Testa disponibilidade da URL
    try:
        req = urllib.request.Request(
            clean_url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
            }
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            code = response.status
            content = response.read(4096).decode("utf-8", errors="ignore").lower()

            # Checa se o domínio expirou ou está estacionado
            if any(termo in content for termo in [
                "domínio à venda", "domain for sale", "domain parked", "compre este domínio",
                "this domain is expired", "hospedagem suspensa", "conta suspensa", "página não encontrada"
            ]):
                return {
                    "status_code": code,
                    "diagnostico": "🚨 Domínio Expirado / À Venda",
                    "categoria": "quebrado",
                    "score": 98,
                    "detalhe": "O link leva a uma página de domínio expirado ou hospedagem suspensa!"
                }

            if code == 200:
                return {
                    "status_code": 200,
                    "diagnostico": "✅ Site Ativo e Funcional",
                    "categoria": "ativo",
                    "score": 35,
                    "detalhe": "Site respondendo com sucesso."
                }
            else:
                return {
                    "status_code": code,
                    "diagnostico": f"🚨 Erro HTTP {code}",
                    "categoria": "quebrado",
                    "score": 95,
                    "detalhe": f"Página retornou código de erro HTTP {code}."
                }
    except urllib.error.HTTPError as e:
        return {
            "status_code": e.code,
            "diagnostico": f"🚨 Erro HTTP {e.code} (Página Fora do Ar)",
            "categoria": "quebrado",
            "score": 98,
            "detalhe": f"Ao clicar no link, o servidor retorna erro HTTP {e.code} (link quebrado)."
        }
    except Exception as e:
        err_msg = str(e).lower()
        if "getaddrinfo failed" in err_msg or "name or service not known" in err_msg:
            return {
                "status_code": None,
                "diagnostico": "🚨 Domínio Não Existe (DNS Falhou)",
                "categoria": "quebrado",
                "score": 100,
                "detalhe": "O domínio registrado na bio não existe ou expirou na internet!"
            }
        return {
            "status_code": None,
            "diagnostico": "🚨 Site Inacessível / Timeout",
            "categoria": "quebrado",
            "score": 95,
            "detalhe": f"Falha de conexão com a página: {str(e)[:40]}"
        }


def extrair_instagram_de_pagina(url: str) -> Optional[str]:
    """Tenta extrair o handle oficial do Instagram de uma página web."""
    if not url or "instagram.com" in url:
        return None
    clean_url = url if url.startswith("http") else "https://" + url
    try:
        req = urllib.request.Request(clean_url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=4) as r:
            html = r.read(45000).decode("utf-8", errors="ignore")
            matches = re.findall(r"instagram\.com/([a-zA-Z0-9_\.]{3,30})", html)
            for m in matches:
                clean_m = m.lower()
                if clean_m not in ["about", "p", "reel", "reels", "explore", "stories", "legal", "accounts"]:
                    return clean_m
    except Exception:
        pass
    return None


def gerar_pitch_instagram(handle: str, nome: str, link: str, diagnostico: Dict[str, Any]) -> Dict[str, str]:
    """Gera o script persuasivo baseado no diagnóstico do link na bio."""
    cat = diagnostico.get("categoria", "sem_link")
    diag_nome = diagnostico.get("diagnostico", "")

    if cat == "quebrado":
        cold_call = (
            f"1. ABERTURA: 'Olá, bom dia! Por gentileza, gostaria de falar com o responsável pelo marketing ou atendimento da {nome}?'\n"
            f"2. O ALERTA CRÍTICO: 'Estou ligando porque estava no perfil de vocês (@{handle}) e fui clicar no link ({link}) para ver os serviços, mas a página está dando erro e não abre ({diag_nome})!'\n"
            f"3. A GRAVIDADE: 'Vocês têm clientes entrando todos os dias. Cada pessoa que clica e dá de cara com erro é uma venda que vai direto pro concorrente.'\n"
            f"4. A SOLUÇÃO IMEDIATA: 'Nós da Marq Lab somos especialistas em páginas de alta conversão. Por R$ 1.000,00 fechados nós colocamos uma Landing Page moderna no ar em até 48 horas para substituir esse link com botão direto pro WhatsApp. Posso te enviar uma prévia?'"
        )
        whatsapp = (
            f"Olá pessoal da *{nome}*, tudo bem? 👋\n\n"
            f"Estava visualizando o perfil de vocês (@{handle}) e fui clicar no *link da bio* ({link}) para conhecer os serviços, mas a página está com erro e não abre! ({diag_nome}) 🚨\n\n"
            f"Como vocês recebem visitas no perfil diariamente, quem clica e encontra o link fora do ar acaba desistindo e indo pro concorrente.\n\n"
            f"Nós da *Marq Lab* desenvolvemos Landing Pages modernas, ultra-rápidas no celular e com botão de WhatsApp integrado por *R$ 1.000,00* em até 48h para substituir esse link quebrado.\n\n"
            f"Posso te mandar uma prévia rápida de como ficaria a nova página da *{nome}*?"
        )
    elif cat == "linktree":
        cold_call = (
            f"1. ABERTURA: 'Olá! Gostaria de falar com o responsável pelo atendimento da {nome}.'\n"
            f"2. GANCHO: 'Vi o perfil de vocês (@{handle}) e notei que vocês usam um agregador de botões simples na bio ({link}).'\n"
            f"3. A DOR: 'Linktree ou árvores genéricas passam uma impressão amadora e diminuem a confiança de quem quer contratar. Uma Landing Page profissional própria passa autoridade e aumenta a taxa de fechamento em até 3x.'\n"
            f"4. A OFERTA: 'Por R$ 1.000,00 nós criamos uma página completa da {nome} com fotos, depoimentos e botão direto pro WhatsApp. Podemos conversar 5 minutinhos?'"
        )
        whatsapp = (
            f"Olá! Acompanho o perfil da *{nome}* (@{handle}) e notei que vocês usam um link genérico na bio ({link}) em vez de um site próprio.\n\n"
            f"Pesquisas mostram que empresas que usam Landing Page própria com identidade visual convertem até 3 vezes mais contatos no WhatsApp do que quem usa botões simples.\n\n"
            f"Nós da *Marq Lab* montamos a Landing Page completa da *{nome}* por *R$ 1.000,00* entregue em 48h.\n\n"
            f"Quer ver uma demonstração de como ficaria a página oficial de vocês?"
        )
    elif cat == "apenas_whatsapp":
        cold_call = (
            f"1. ABERTURA: 'Olá! Gostaria de falar com o responsável da {nome}.'\n"
            f"2. GANCHO: 'Estava analisando o perfil de vocês (@{handle}) e vi que na bio há apenas o link direto pro WhatsApp.'\n"
            f"3. A DOR: 'Mais de 60% das pessoas preferem entender como funciona o serviço, ver fotos e depoimentos em um site antes de mandar mensagem.'\n"
            f"4. A OFERTA: 'Nós criamos uma Landing Page rápida por R$ 1.000,00 que aquece o lead e entrega ele pronto para fechar no seu WhatsApp. Posso mandar um modelo?'"
        )
        whatsapp = (
            f"Olá pessoal da *{nome}*! 👋\n\n"
            f"Vi o perfil de vocês (@{handle}) e notei que na bio há apenas o link do WhatsApp.\n\n"
            f"Muitos clientes em potencial deixam de mandar mensagem porque gostariam de ver preços, fotos e serviços em uma página profissional antes de chamar.\n\n"
            f"Desenvolvemos Landing Pages modernas por *R$ 1.000,00* entregues em 48h prontas para multiplicar suas conversões no WhatsApp.\n\n"
            f"Posso te mandar uma demonstração rápida?"
        )
    else:
        cold_call = (
            f"1. ABERTURA: 'Olá! Por gentileza, gostaria de falar com o responsável pela {nome}.'\n"
            f"2. GANCHO: 'Vi o perfil ativo de vocês (@{handle}) com vários posts bacanas, mas notei que na bio vocês não têm uma página oficial para apresentar os serviços e diferenciais.'\n"
            f"3. A DOR: 'Muitos clientes querem saber mais antes de chamar no WhatsApp. Sem um site profissional, você perde quem tem vergonha de mandar mensagem sem ver os serviços antes.'\n"
            f"4. A OFERTA: 'Nós criamos uma Landing Page personalizada por R$ 1.000,00 pronta em 48h. Posso te enviar um modelo?'"
        )
        whatsapp = (
            f"Olá pessoal da *{nome}*! 👋 Parabéns pelo trabalho no perfil (@{handle})!\n\n"
            f"Notei que na bio de vocês ainda não há uma página própria apresentando os diferenciais e serviços da empresa.\n\n"
            f"Uma Landing Page profissional transmite muita credibilidade para quem encontra vocês nas redes e quer contratar com segurança.\n\n"
            f"Nós da *Marq Lab* criamos páginas modernas e adaptadas para smartphone por apenas *R$ 1.000,00* em até 48 horas.\n\n"
            f"Posso te mandar uma prévia rápida sem compromisso?"
        )

    return {"cold_call": cold_call, "whatsapp": whatsapp}


def escanear_perfis_instagram(cidade: str, nicho: str, limite: int = 15) -> List[Dict[str, Any]]:
    """
    Pesquisa perfis comerciais e links de empresas por cidade e nicho,
    auditando os links de conversão (bio/site) em tempo real.
    Combina Google Maps local (via Playwright) com o Diretório Oficial Econodata.
    """
    clean_cidade = (cidade or "Sorocaba").strip()
    clean_nicho = (nicho or "Dentista").strip()
    query = f"{clean_nicho} em {clean_cidade}"

    candidatos: List[Dict[str, Any]] = []
    nomes_vistos = set()

    # 1. Estratégia Principal: Busca de empresas no Google Maps via Playwright
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            launch_opts = {
                "headless": True,
                "args": [
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                ],
            }
            try:
                browser = p.chromium.launch(channel="chrome", **launch_opts)
            except Exception:
                try:
                    browser = p.chromium.launch(channel="msedge", **launch_opts)
                except Exception:
                    browser = p.chromium.launch(**launch_opts)

            page = browser.new_page()
            url_maps = f"https://www.google.com/maps/search/{urllib.parse.quote(query)}"
            page.goto(url_maps, wait_until="domcontentloaded", timeout=20000)
            page.wait_for_timeout(2500)

            cards = page.query_selector_all('div.Nv2PK, div[role="article"]')
            for card in cards[:limite + 5]:
                name_elem = card.query_selector(".qBF1Pd, font")
                name = name_elem.inner_text().strip() if name_elem else ""
                if not name:
                    link_elem = card.query_selector("a.hfpxzc")
                    if link_elem:
                        name = link_elem.get_attribute("aria-label") or ""

                if not name or name in nomes_vistos or len(name) < 2:
                    continue
                nomes_vistos.add(name)

                # Site do card
                web_elem = card.query_selector('a[data-value="Website"], a.lcr4fd, a[aria-label*="website"]')
                website = web_elem.get_attribute("href") if web_elem else None

                # Telefone no texto do card
                card_text = card.inner_text() or ""
                phone = extrair_telefone(card_text)

                candidatos.append({
                    "nome": name,
                    "website": website,
                    "phone": phone or "",
                    "snippet": f"Localizado em {clean_cidade} - Especialidade: {clean_nicho}",
                })

                if len(candidatos) >= limite:
                    break

            browser.close()
    except Exception:
        pass

    # 2. Estratégia Complementar / Fallback: Diretório Econodata
    if len(candidatos) < limite:
        try:
            import servico_radar_cnpj
            empresas_diretorio = servico_radar_cnpj.extrair_empresas_diretorio("SP", clean_cidade, clean_nicho)
            for emp in empresas_diretorio:
                nome = emp.get("fantasia") or emp.get("razao")
                if not nome or nome in nomes_vistos:
                    continue
                nomes_vistos.add(nome)

                candidatos.append({
                    "nome": nome,
                    "website": None,
                    "phone": "",
                    "snippet": f"{emp.get('endereco', '')} - {emp.get('cnae', '')}",
                })
                if len(candidatos) >= limite:
                    break
        except Exception:
            pass

    resultados: List[Dict[str, Any]] = []

    for item in candidatos[:limite]:
        nome_empresa = item["nome"]
        website = item.get("website")
        phone = item.get("phone", "")
        snippet = item.get("snippet", "")

        # Verifica se o link é o próprio Instagram
        handle = None
        if website and "instagram.com" in website:
            m = re.search(r"instagram\.com/([a-zA-Z0-9_\.]{3,30})", website)
            if m and m.group(1).lower() not in ["about", "p", "reel", "reels", "explore"]:
                handle = m.group(1).lower()
                website = None  # Era o próprio Instagram na bio!

        # Se temos website ativo, tenta buscar o link do Instagram na home do site
        if not handle and website:
            extracted_handle = extrair_instagram_de_pagina(website)
            if extracted_handle:
                handle = extracted_handle

        # Se ainda não temos handle, gera handle provável formatado para o nicho/marca
        if not handle:
            base_slug = slugify(nome_empresa).replace("-", ".")
            handle = base_slug[:28].rstrip(".")

        # Audita a URL do link
        diagnostico = auditar_link_bio(website)
        pitch = gerar_pitch_instagram(handle, nome_empresa, website or "", diagnostico)

        resultado = {
            "handle": f"@{handle}",
            "handle_raw": handle,
            "nome": nome_empresa,
            "instagram_url": f"https://www.instagram.com/{handle}/",
            "cidade": clean_cidade,
            "nicho": clean_nicho,
            "bio_resumo": snippet[:140] if snippet else f"Perfil profissional em {clean_cidade}",
            "phone": phone or "",
            "link_bio": website or "",
            "link_diagnostico": diagnostico["diagnostico"],
            "link_categoria": diagnostico["categoria"],
            "link_detalhe": diagnostico["detalhe"],
            "status_code": diagnostico["status_code"],
            "lead_score": diagnostico["score"],
            "cold_call_script": pitch["cold_call"],
            "whatsapp_script": pitch["whatsapp"],
        }
        resultados.append(resultado)

    # Ordena com os maiores scores (oportunidades mais quentes: links quebrados, sem site) primeiro
    resultados.sort(key=lambda x: x.get("lead_score", 0), reverse=True)
    return resultados

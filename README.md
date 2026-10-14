# 🚀 MARQ LAB // B2B Growth Engine & Gestão de Vendas
> Plataforma unificada multiusuário para prospecção ativa de leads no Google Maps, auditoria técnica web, consulta automática de CNPJ (ReceitaWS/BrasilAPI), geração de propostas e CRM comercial em tempo real.

---

## 📁 Estrutura de Pastas e Arquivos

O projeto está organizado segundo o padrão modular em português:

```text
RPA Captação de Clientes/
├── app/                        # Núcleo da Aplicação Web
│   ├── templates/              # Páginas HTML (login, dashboard, proposta)
│   ├── static/                 # CSS customizado, JavaScript e screenshots em cache
│   ├── app.py                  # Servidor Flask, rotas REST e streaming SSE
│   ├── banco_dados.py          # Conexão SQLite (WAL), queries, migrações e histórico
│   ├── minerador.py            # Robô Playwright Stealth para busca no Google Maps
│   ├── auditor_sites.py        # Auditor técnico de velocidade, SSL e responsividade
│   ├── gerador_propostas.py    # Algoritmo de Lead Scoring e copywriter persuasivo
│   ├── servico_cnpj.py         # Consulta de CNPJ, Razão Social, CNAE e Sócios
│   ├── servico_prints.py       # Captura automatizada de screenshots dos sites
│   ├── autenticacao.py         # Criptografia de senhas, sessões e permissões SDR/Admin
│   ├── wsgi.py                 # Ponto de entrada WSGI interno
│   └── __init__.py             # Inicializador de pacote Python
├── deploy/                     # Configurações para Produção em VPS Linux
│   ├── nginx.conf              # Reverse proxy Nginx com cache e proxy SSE
│   ├── marqlab.service         # Serviço Systemd para inicialização automática
│   └── atualizar.sh            # Script rápido de git pull + restart
├── docs/                       # Documentação
│   └── deploy_vps_guia.md      # Manual passo a passo para Hospedagem VPS
├── .github/workflows/          # Automação CI/CD
│   └── deploy.yml              # Deploy contínuo no servidor via Git Push
├── iniciar_sistema.bat         # Atalho de execução rápida no Windows
├── wsgi.py                     # Entrypoint raiz compatível com Gunicorn / Waitress
├── Procfile                    # Comando de deploy para plataformas Cloud
├── nexus_leads.db              # Banco de dados SQLite de produção (modo WAL)
├── requirements.txt            # Dependências Python do ecossistema
└── README.md                   # Esta documentação
```

---

## 🎯 Principais Funcionalidades

### 1. 🔍 Robô de Prospecção Stealth (`app/minerador.py`)
- Varredura de nicho e localização geográfica no Google Maps.
- Detecção e higienização automática de telefones (Fixos, Celulares e WhatsApp).
- Filtragem de leads sem presença digital ou com sites legados/obsoletos.

### 2. 🏛️ Consulta Inteligente de CNPJ (`app/servico_cnpj.py`)
- Busca automática de dados oficiais da empresa via **BrasilAPI / ReceitaWS**:
  * Razão Social e Nome Fantasia
  * Situação Cadastral (Ativa / Inapta)
  * Capital Social e Porte da Empresa
  * Data de Abertura e CNAE Principal
  * Quadro de Sócios e Administradores (QSA) para contato direto com tomadores de decisão.

### 3. ⚡ Auditoria Técnica de Presença Web (`app/auditor_sites.py`)
- Verificação de ausência de `<meta name="viewport">` (layouts que não cabem no celular).
- Detecção de certificado de segurança SSL ausente ou expirado (HTTP inseguro).
- Medição de tempo de resposta e erros de servidor (404, 500, etc.).

### 4. 👥 Gestão Multiusuário e Sincronização em Tempo Real (`app/autenticacao.py` + SSE)
- Autenticação individual por login e senha criptografada (**scrypt**).
- Gestão de permissões: **SDR** (focado no funil de atendimento) e **ADMIN** (gestão global e auditoria).
- Sincronização em tempo real entre todos os operadores conectados via **Server-Sent Events (SSE)**.
- Indicador de presença e operadores online em tempo real.

### 5. 📸 Visualizador de Prints dos Sites (`app/servico_prints.py`)
- Robô Playwright em background para registrar prints instantâneos das páginas dos leads.
- Cache inteligente local para navegação ultra-rápida no CRM.

---

## ⚡ Como Iniciar o Sistema Localmente

### Pelo Atalho Rápido (Windows)
Dê um duplo clique no arquivo:
```cmd
iniciar_sistema.bat
```
O script ativará o ambiente virtual `.venv`, verificará dependências e abrirá `http://127.0.0.1:5000` no seu navegador padrão.

### Pelo Terminal
```powershell
# Ativar o ambiente virtual
.\.venv\Scripts\activate

# Iniciar o servidor
python wsgi.py
```

Acesse no navegador: **http://127.0.0.1:5000**

---

## 🌐 Hospedagem em Servidor VPS (Nuvem)

Para colocar o sistema online e acessível de qualquer lugar 24/7 com domínio próprio e HTTPS:
- Consulte o guia completo e detalhado em [deploy_vps_guia.md](file:///c:/Users/est.marcosdrm/OneDrive%20-%20Votorantim/Área de Trabalho/RPA Captação de Clientes/docs/deploy_vps_guia.md).
- Os arquivos prontos para Nginx e Systemd estão na pasta [deploy/](file:///c:/Users/est.marcosdrm/OneDrive%20-%20Votorantim/Área de Trabalho/RPA Captação de Clientes/deploy).

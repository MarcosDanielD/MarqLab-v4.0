# 🚀 Guia de Deploy em Produção — Marq Lab (`marqlab.com.br`)

Este guia detalha o passo a passo completo para colocar o **Marq Lab** no ar em um servidor VPS na nuvem com domínio próprio (`marqlab.com.br`), conexão segura HTTPS (SSL grátis), banco de dados centralizado em tempo real e acesso multiusuário concorrente para Marcos e Jamilly.

---

## 1. Escolha da VPS (Servidor na Nuvem)

O Playwright (robô que extrai dados do Google Maps e tira prints dos sites) requer uma VPS com no mínimo **2 GB de RAM** (recomendado: 2 vCPU / 4 GB RAM para velocidade máxima).

### Provedores Recomendados (Custo-Benefício):
| Provedor | Plano Recomendado | Custo Estimado | Sistema Operacional |
| :--- | :--- | :--- | :--- |
| **Hetzner Cloud** (Excelente) | CPX21 (3 vCPU, 4GB RAM) ou CX22 (2 vCPU, 4GB RAM) | ~€ 4 a € 7 / mês | Ubuntu 24.04 LTS |
| **Hostinger VPS** | KVM 2 (2 vCPU, 8GB RAM) | ~R$ 39 / mês | Ubuntu 24.04 LTS |
| **DigitalOcean** | Basic Droplet (2 vCPU, 2GB ou 4GB RAM) | ~$ 12 a $ 18 / mês | Ubuntu 24.04 LTS |

---

## 2. Configuração do Domínio (`marqlab.com.br`)

No painel onde você registrou o domínio (ex: Registro.br, Cloudflare ou Hostinger):

1. Vá na aba **Zona DNS**.
2. Adicione os seguintes registros do tipo **A**:
   - **Tipo A**: `@` (ou deixe em branco / `marqlab.com.br`) $\rightarrow$ Apontando para o **IPv4 da sua VPS** (Ex: `123.45.67.89`).
   - **Tipo A**: `www` $\rightarrow$ Apontando para o **IPv4 da sua VPS** (Ex: `123.45.67.89`).
3. *(Opcional, se usar Cloudflare)*: No primeiro momento, deixe a nuvem na cor cinza (*DNS Only*) até emitir o certificado SSL pelo Certbot.

---

## 3. Preparação do Servidor Ubuntu (Via Terminal SSH)

Conecte-se à sua VPS pelo PowerShell ou terminal:
```bash
ssh root@SEU_IP_VPS
```

Atualize os pacotes do sistema:
```bash
apt update && apt upgrade -y
```

Instale os pacotes básicos (Python, Git, Nginx, Certbot e bibliotecas do sistema):
```bash
apt install -y python3 python3-pip python3-venv git nginx certbot python3-certbot-nginx
```

---

## 4. Clonar o Projeto e Configurar o Ambiente Python

Crie a pasta da aplicação no servidor:
```bash
mkdir -p /var/www/marqlab
cd /var/www/marqlab
```

Envie seus arquivos para a pasta ou clone via Git:
```bash
# Exemplo se usar repositório Git:
git clone https://github.com/SEU_USUARIO/marqlab.git .
```

Crie o ambiente virtual Python e instale as dependências:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 4.1 Instalar o Chromium do Playwright e suas dependências de sistema
Para o robô de mineração e captura de prints funcionar no Linux sem interface gráfica:
```bash
playwright install chromium
playwright install-deps chromium
```

---

## 5. Permissões de Acesso e Banco SQLite WAL

Como o SQLite roda com o modo `WAL` (*Write-Ahead Logging*), o servidor web precisa de permissão de escrita na pasta do projeto e no arquivo `nexus_leads.db`:

```bash
chown -R www-data:www-data /var/www/marqlab
chmod -R 775 /var/www/marqlab
```

---

## 6. Configurar o Serviço Automático (Systemd Daemon)

Copie o arquivo de serviço [marqlab.service](file:///c%3A/Users/est.marcosdrm/OneDrive%20-%20Votorantim/%C3%81rea%20de%20Trabalho/RPA%20Capta%C3%A7%C3%A3o%20de%20Clientes/deploy/marqlab.service) para a pasta de serviços do Linux:

```bash
cp /var/www/marqlab/deploy/marqlab.service /etc/systemd/system/marqlab.service
```

Recarregue o systemd, habilite para iniciar no boot e inicie o serviço:
```bash
systemctl daemon-reload
systemctl enable marqlab
systemctl start marqlab
```

Verifique se a aplicação está rodando normalmente:
```bash
systemctl status marqlab
```

---

## 7. Configurar o Nginx e Certificado SSL Grátis (HTTPS)

Copie a configuração do Nginx:
```bash
cp /var/www/marqlab/deploy/nginx.conf /etc/nginx/sites-available/marqlab.conf
ln -s /etc/nginx/sites-available/marqlab.conf /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
```

Teste a sintaxe do Nginx:
```bash
nginx -t
```

Emita o certificado SSL oficial gratuito (Let's Encrypt):
```bash
certbot --nginx -d marqlab.com.br -d www.marqlab.com.br
```

Reinicie o Nginx:
```bash
systemctl restart nginx
```

---

## 8. Backup Automático Diário do Banco de Dados

Para garantir que os leads, notas e reuniões estejam sempre seguros, crie uma rotina de backup diário:

Abra o crontab do root:
```bash
crontab -e
```

Adicione a linha abaixo para gerar uma cópia do banco toda madrugada às 03:00:
```cron
0 3 * * * cp /var/www/marqlab/nexus_leads.db /var/backups/nexus_leads_$(date +\%Y\%m\%d).db
```

---

## 9. Como Acessar e Usar no Dia a Dia

1. Abra o navegador em: **`https://marqlab.com.br`**
2. Se for o primeiro acesso, o sistema exibirá a tela de ativação de senha para Marcos e Jamilly.
3. Após login, cada usuário tem sua própria sessão persistente de 7 dias com permissões automáticas:
   - **Marcos (Gestor/Admin):** visualiza todos os leads, pode reatribuir operadores, cadastrar novos membros na equipe e limpar a base de dados.
   - **Jamilly (SDR):** visualiza todos os leads da prospecção, assume leads com 1 clique ("Assumir Lead"), agenda reuniões e adiciona notas em tempo real.
4. Toda alteração feita por qualquer pessoa atualiza instantaneamente a tela de todos os outros conectados via **Server-Sent Events (SSE)**, sem necessidade de atualizar a página!

---

## 10. Como Atualizar o Sistema após subir alterações no GitHub

### Opção A: Atualização 100% Automática (GitHub Actions)
Já deixamos configurado o arquivo [.github/workflows/deploy.yml](file:///.github/workflows/deploy.yml).
Toda vez que você der `git push` no seu computador:
1. O GitHub detecta a alteração na branch principal.
2. Conecta sozinho na sua VPS via SSH.
3. Roda `git pull`, atualiza dependências e reinicia o serviço.
4. Em menos de 20 segundos o `marqlab.com.br` já está com a versão nova no ar!

> **Como ativar:** No seu repositório no GitHub, vá em **Settings** > **Secrets and variables** > **Actions** e adicione as secrets:
> - `VPS_HOST`: O IP da sua VPS.
> - `VPS_SSH_KEY`: Sua chave privada SSH (ou senha).

### Opção B: Atualização Manual em 1 Linha (Sem GitHub Actions)
Se preferir não configurar chaves no GitHub, sempre que subir alterações pelo computador, basta rodar na VPS:
```bash
/var/www/marqlab/deploy/atualizar.sh
```
Ou manualmente:
```bash
cd /var/www/marqlab && git pull && systemctl restart marqlab
```

> [!NOTE]
> **O banco de dados nunca é perdido!** O arquivo `nexus_leads.db` e as fotos de print estão configurados no `.gitignore`. Quando você puxa alterações de código, os leads, notas e reuniões reais da VPS continuam intactos e preservados.

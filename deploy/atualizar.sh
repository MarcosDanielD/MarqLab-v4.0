#!/bin/bash
# Script de Atualização Rápida do Marq Lab no Servidor
# Uso: ./atualizar.sh

set -e
echo ">>> Puxando últimas alterações do GitHub..."
cd /var/www/marqlab
git pull

echo ">>> Atualizando dependências Python se houver novidades..."
source .venv/bin/activate
pip install -r requirements.txt --quiet

echo ">>> Reiniciando serviço Marq Lab..."
sudo systemctl restart marqlab

echo ">>> Sucesso! Marq Lab atualizado e rodando."
sudo systemctl status marqlab --no-pager

#!/usr/bin/env bash
# Laboratório 04 — Ubuntu 24.04 LTS
# Gerado automaticamente em 2026-10-19 13:58 a partir de catalogo/ e dos pedidos aprovados.
# Não edite à mão. Rodar com sudo na máquina-modelo, antes de capturar a imagem no FOG.
set -uo pipefail
[ "$(id -u)" -eq 0 ] || { echo 'Rode com sudo.'; exit 1; }
falhas=()
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y libreoffice libreoffice-l10n-pt-br gimp inkscape git python3 python3-pip python3-venv idle3 || falhas+=(apt)

if [ ${#falhas[@]} -gt 0 ]; then echo "Falharam: ${falhas[*]}"; exit 1; fi
echo 'Concluído.'

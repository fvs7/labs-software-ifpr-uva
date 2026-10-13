#!/usr/bin/env bash
# Cria os rótulos usados pelo fluxo de pedidos. Rode uma vez, depois de criar o repositório:
#   ./ferramentas/criar-rotulos.sh dono/repositorio
set -euo pipefail
REPO="${1:?uso: $0 dono/repositorio}"

criar() { gh label create "$1" --repo "$REPO" --color "$2" --description "$3" --force; }

criar pedido                     16302a "Pedido de instalação de programa"
criar status/novo                d9960f "Recebido, aguardando análise"
criar status/em-analise          d9960f "TI analisando licença, disco e segurança"
criar status/aguardando-licenca  d9960f "Depende de licença ou conta"
criar status/aprovado            8fcfa5 "Aprovado, entra na próxima imagem"
criar status/agendado            8fcfa5 "Data de instalação definida"
criar status/instalado           23854a "Instalado no laboratório"
criar status/validado            23854a "Professor confirmou que funciona"
criar status/recusado            9aaaa5 "Não aprovado (motivo no comentário)"
criar status/expirado            9aaaa5 "Removido ao fim do período pedido"

for lab in lab1 lab2 lab3 lab4; do
  criar "lab/$lab" c5d6e0 "Pedido para o $lab"
done

for arq in "$(dirname "$0")"/../catalogo/*.yml; do
  id=$(basename "$arq" .yml); [[ $id == _* ]] && continue
  criar "sw/$id" ededed "Programa do catálogo: $id"
done
echo "Rótulos criados em $REPO."

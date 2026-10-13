# Software nos laboratórios — IFPR União da Vitória

Pedidos de instalação de programas nos 4 laboratórios do campus, com painel público
mostrando o que está instalado, o que foi pedido e quanto disco ainda cabe em cada máquina.

**Painel:** `https://fvs7.github.io/labs-software-ifpr-uva/` · **Fazer um pedido:** aba *Issues → New issue*

---

## Para professores

1. Abra o painel e procure o programa. Se já estiver instalado, não precisa pedir.
   Se outro professor já pediu, deixe um 👍 no pedido dele — isso conta como apoio.
2. Clique em **Pedir um programa** e preencha o formulário (uns 5 minutos).
   Você precisa de uma conta gratuita no GitHub.
3. Em poucos segundos aparece um comentário automático no pedido dizendo se o programa
   já é conhecido, se roda no sistema do laboratório e se o prazo é suficiente.
4. Acompanhe pela etiqueta de situação:

   | Situação | O que significa |
   |---|---|
   | Recebido / Em análise | A TI está avaliando licença, espaço e segurança |
   | Aguardando licença | Falta a licença ou a conta para os alunos |
   | Aprovado / Agendado | Entra na próxima atualização da imagem do laboratório |
   | Instalado | Já está nas máquinas — teste antes da aula |
   | Validado | Você confirmou que funciona |
   | Não aprovado | O motivo está no comentário do pedido |

**Prazo mínimo: 15 dias antes da aula.** Os programas entram junto com a regravação da
imagem do laboratório, não são instalados máquina a máquina.

---

## Para a TI

### Como as peças se encaixam

```
Formulário (issue)  ──►  Triagem automática  ──►  comentário + rótulos lab/* e sw/*
                                │
       você muda o rótulo status/*  (novo → em-analise → aprovado → instalado)
                                │
Atualizar painel (Action) ──►  site no GitHub Pages  (data.json)
                          └──►  gerado/labN.ps1 | labN.sh  (scripts de instalação)
```

| Arquivo | Para que serve |
|---|---|
| `labs.yml` | Os 4 laboratórios: sistema, nº de máquinas, disco, espaço reservado, prazo mínimo, fim do semestre |
| `catalogo/*.yml` | Um arquivo por programa: tamanho medido, comando de instalação, dependências, onde já está instalado |
| `.github/ISSUE_TEMPLATE/pedido-software.yml` | O formulário do professor |
| `ferramentas/build.py` | Lê pedidos + catálogo, calcula o disco, gera o painel e os scripts |
| `gerado/` | Scripts de instalação por laboratório — **não editar à mão** |
| `site/` | O painel (HTML/CSS/JS puro, sem build) |

### Instalação (uma vez)

1. O repositório é **público** (GitHub Pages gratuito). Por isso o campo "Seu nome" do
   formulário é opcional e o painel não mostra quem pediu (`mostrar_solicitante: false`).
   Se um dia migrar para uma organização com GitHub Education/Campus, dá para torná-lo privado.
2. *Settings → Pages → Source:* **GitHub Actions**.
3. *Settings → Actions → General → Workflow permissions:* **Read and write**.
4. Crie os rótulos: `./ferramentas/criar-rotulos.sh dono/repositorio`
5. (já feito) URLs do painel apontam para `fvs7.github.io/labs-software-ifpr-uva`.
6. Ajuste `labs.yml` (os valores marcados `CONFERIR`): disco real, qual laboratório é o Linux,
   espaço que sistema e perfis ocupam hoje (`Get-PSDrive C` / `df -h /` na máquina-modelo).
7. Confira `instalado_em` no catálogo, para o painel começar mostrando a realidade.
8. *Actions → Atualizar painel → Run workflow*.

### Rotina de triagem

- Pedido novo chega com `status/novo` e o comentário automático. Leia os pontos de atenção.
- Programa fora do catálogo: instale na máquina-modelo, meça, crie `catalogo/<id>.yml`
  (copie `_modelo.yml`) e ponha o rótulo `sw/<id>` no pedido. A partir daí o tamanho deixa de
  ser estimativa e o programa entra no script do laboratório.
- Troque o rótulo `status/*` conforme o andamento. O painel se atualiza sozinho.
- Recusou? Comente o motivo e use `status/recusado` (ou feche a issue).

### Atualizar a imagem de um laboratório

1. Baixe `gerado/labN.ps1` (ou `.sh`) — ele contém tudo que está **instalado ou aprovado**.
2. Rode como Administrador / `sudo` na máquina-modelo. Programas sem instalação automática
   aparecem listados no fim, para fazer à mão.
3. Capture a imagem no FOG e distribua.
4. Mude os pedidos de `status/aprovado` para `status/instalado`, e acrescente o lab em
   `instalado_em` no catálogo de cada programa.

### Como a previsão de disco é calculada

Por máquina, para cada laboratório:

```
previsto = sistema + atualizações + perfis        (labs.yml → reservado_gb)
         + programas instalados + aprovados + em análise
         (cada programa conta uma vez; dependências compartilhadas, como o Java, também)
livre    = disco − previsto − margem de segurança
```

Amarelo a partir de 75 % do disco, vermelho a partir de 90 % (`labs.yml → alerta_disco`).
Programas fora do catálogo usam o tamanho que o professor informou, ou 1 GB, marcados com `~`.

### Testar localmente, sem GitHub

```bash
pip install pyyaml
python3 testes/gerar_exemplos.py
python3 ferramentas/build.py --issues testes/issues-exemplo.json --saida _site
python3 -m http.server -d _site 8000     # abrir http://localhost:8000
```

### Pedidos com prazo

Pedidos marcados "Só este semestre" mostram a data de fim do semestre (`labs.yml → semestre.fim`).
Na virada, revise-os e use `status/expirado` nos que podem sair da imagem.

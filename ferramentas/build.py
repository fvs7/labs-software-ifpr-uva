#!/usr/bin/env python3
"""
Monta o painel e os scripts de instalação a partir de:
  - labs.yml            (laboratórios e disco)
  - catalogo/*.yml      (programas conhecidos, tamanho e comando de instalação)
  - issues do GitHub    (pedidos feitos pelo formulário)

Uso:
  build.py --issues issues.json --saida _site      # painel + scripts
  build.py --triagem issue.json                     # comentário automático de um pedido

O JSON de issues é o que sai de:
  gh issue list --label pedido --state all --limit 1000 \
     --json number,title,body,labels,state,createdAt,updatedAt,url,reactionGroups
"""
import argparse
import datetime as dt
import json
import re
import shutil
import sys
import unicodedata
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parent.parent

# Rótulo da pergunta no formulário -> chave interna.
# Se mudar o texto de uma pergunta em pedido-software.yml, mude aqui também.
CAMPOS = {
    "Seu nome": "nome",
    "Curso": "curso",
    "Disciplina": "disciplina",
    "Turma e número de alunos": "turma",
    "Laboratórios": "laboratorios",
    "Programa": "programa",
    "Site oficial ou link de download": "site",
    "Versão": "versao",
    "Extensões, plugins ou bibliotecas": "complementos",
    "Licença": "licenca",
    "Se precisa de licença ou conta, como funciona?": "licenca_detalhes",
    "Tamanho aproximado instalado (se souber)": "tamanho_estimado",
    "Precisa de internet?": "internet",
    "Os alunos precisam de permissão de administrador?": "admin",
    "Requisito de hardware": "hardware",
    "Os arquivos dos alunos precisam ficar salvos entre uma aula e outra?": "persistencia",
    "Data da primeira aula que usa o programa": "primeira_aula",
    "Por quanto tempo?": "periodo",
    "Como saberemos que está funcionando?": "teste_aceite",
    "Aceita uma alternativa livre, se houver?": "alternativa",
    "Observações": "observacoes",
}

# Rótulo status/* -> (código, texto para o professor, grupo de disco)
STATUS = {
    "novo":               ("Recebido", "pendente"),
    "em-analise":         ("Em análise", "pendente"),
    "aguardando-licenca": ("Aguardando licença", "pendente"),
    "aprovado":           ("Aprovado", "aprovado"),
    "agendado":           ("Agendado", "aprovado"),
    "instalado":          ("Instalado", "instalado"),
    "validado":           ("Validado pelo professor", "instalado"),
    "recusado":           ("Não aprovado", None),
    "expirado":           ("Removido ao fim do período", None),
}
ORDEM_STATUS = list(STATUS)
PESO_GRUPO = {"pendente": 1, "aprovado": 2, "instalado": 3}
TAMANHO_PADRAO_MB = 1024  # quando o programa não está no catálogo e ninguém informou


# ---------------------------------------------------------------- utilitários

def normalizar(txt: str) -> str:
    txt = unicodedata.normalize("NFKD", txt or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", txt.lower())


def ler_yaml(caminho: Path):
    with open(caminho, encoding="utf-8") as f:
        return yaml.safe_load(f)


def carregar_labs():
    cfg = ler_yaml(RAIZ / "labs.yml")
    for lab in cfg["laboratorios"]:
        lab["_chave"] = normalizar(lab["nome"])
    return cfg


def carregar_catalogo():
    cat = {}
    for arq in sorted((RAIZ / "catalogo").glob("*.yml")):
        if arq.name.startswith("_"):
            continue
        item = ler_yaml(arq)
        if not item or "id" not in item:
            print(f"aviso: {arq.name} sem id, ignorado", file=sys.stderr)
            continue
        item.setdefault("depende", [])
        item.setdefault("instalado_em", [])
        item.setdefault("aliases", [])
        item.setdefault("so", ["windows", "linux"])
        item["_chaves"] = {normalizar(x) for x in [item["id"], item["nome"], *item["aliases"]]}
        cat[item["id"]] = item
    return cat


def ler_formulario(corpo: str) -> dict:
    """Converte o corpo de uma issue de formulário ('### Pergunta\\n\\nresposta')."""
    campos, atual, buf = {}, None, []

    def fechar():
        if atual in CAMPOS:
            valor = "\n".join(buf).strip()
            if valor in ("_No response_", "None"):
                valor = ""
            campos[CAMPOS[atual]] = valor

    for linha in (corpo or "").splitlines():
        m = re.match(r"^###\s+(.+?)\s*$", linha)
        if m:
            fechar()
            atual, buf = m.group(1), []
        else:
            buf.append(linha)
    fechar()
    return campos


def tamanho_em_mb(texto: str):
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(gb|g|mb|m)?", (texto or "").lower())
    if not m:
        return None
    n = float(m.group(1).replace(",", "."))
    return round(n * 1024) if (m.group(2) or "gb").startswith("g") else round(n)


def casar_catalogo(programa: str, rotulos, catalogo):
    for r in rotulos:
        if r.startswith("sw/") and r[3:] in catalogo:
            return r[3:]
    chave = normalizar(programa)
    if not chave:
        return None
    for item in catalogo.values():
        if chave in item["_chaves"]:
            return item["id"]
    for item in catalogo.values():  # casamento parcial: "packet tracer 8.2" -> packet-tracer
        if any(len(k) >= 4 and k in chave for k in item["_chaves"]):
            return item["id"]
    return None


def data(texto):
    try:
        return dt.date.fromisoformat((texto or "").strip()[:10])
    except ValueError:
        return None


# ---------------------------------------------------------------- pedidos

def montar_pedido(issue, cfg, catalogo, hoje):
    rotulos = [l["name"] for l in issue.get("labels", [])]
    f = ler_formulario(issue.get("body", ""))

    status = next((r[7:] for r in rotulos if r.startswith("status/") and r[7:] in STATUS), "novo")
    if issue.get("state", "").upper() == "CLOSED" and status in ("novo", "em-analise", "aguardando-licenca"):
        status = "recusado"  # fechada sem passar por aprovação

    labs_por_chave = {l["_chave"]: l for l in cfg["laboratorios"]}
    labs = [labs_por_chave[normalizar(x)]["id"]
            for x in re.split(r",\s*", f.get("laboratorios", "")) if normalizar(x) in labs_por_chave]

    programa = f.get("programa") or re.sub(r"^\[Pedido\]\s*", "", issue.get("title", ""))
    sw = casar_catalogo(programa, rotulos, catalogo)
    item = catalogo.get(sw)
    primeira = data(f.get("primeira_aula"))
    criado = data(issue.get("createdAt"))

    alertas = []
    if item:
        for lab_id in labs:
            lab = next(l for l in cfg["laboratorios"] if l["id"] == lab_id)
            if lab["so"] not in item["so"]:
                alertas.append(f"{item['nome']} não roda em {lab['so_descricao']} ({lab['nome']}).")
            if lab_id in item["instalado_em"] and STATUS[status][1] == "pendente":
                alertas.append(f"Já está instalado no {lab['nome']}.")
        if item.get("observacoes") and STATUS[status][1] == "pendente":
            alertas.append(item["observacoes"])
    else:
        alertas.append("Programa fora do catálogo — a TI precisa medir o tamanho e o método de instalação.")

    if primeira and criado and STATUS[status][1] == "pendente":
        dias = (primeira - criado).days
        if dias < cfg["prazo_minimo_dias"]:
            alertas.append(f"Pedido feito {max(dias, 0)} dias antes da aula; o prazo mínimo é {cfg['prazo_minimo_dias']}.")
    if f.get("primeira_aula") and not primeira:
        alertas.append("Data da primeira aula em formato inválido (use AAAA-MM-DD).")
    if "ainda não temos" in f.get("licenca", "").lower():
        alertas.append("Programa pago sem licença — não pode ser instalado até a licença existir.")
    if f.get("admin", "").startswith("Sim"):
        alertas.append("Pede permissão de administrador para alunos — avaliar alternativa.")

    expira = None
    if f.get("periodo", "").startswith("Só este") and cfg.get("semestre"):
        expira = str(cfg["semestre"]["fim"])

    apoios = sum(g.get("users", {}).get("totalCount", 0) for g in issue.get("reactionGroups", [])
                 if g.get("content") == "THUMBS_UP")

    tamanho = item["tamanho_mb"] if item else (tamanho_em_mb(f.get("tamanho_estimado")) or TAMANHO_PADRAO_MB)

    return {
        "numero": issue["number"],
        "url": issue.get("url", ""),
        "programa": item["nome"] if item else programa.strip(),
        "programa_digitado": programa.strip(),
        "sw": sw,
        "labs": labs,
        "status": status,
        "status_texto": STATUS[status][0],
        "grupo": STATUS[status][1],
        "solicitante": f.get("nome", "") if cfg.get("mostrar_solicitante") else "",
        "curso": f.get("curso", ""),
        "disciplina": f.get("disciplina", ""),
        "turma": f.get("turma", ""),
        "primeira_aula": str(primeira) if primeira else "",
        "periodo": f.get("periodo", ""),
        "expira": expira,
        "licenca": f.get("licenca", ""),
        "internet": f.get("internet", ""),
        "complementos": [x.strip("-• ").strip() for x in f.get("complementos", "").splitlines() if x.strip()],
        "tamanho_mb": tamanho,
        "tamanho_estimado": item is None,
        "apoios": apoios,
        "criado": str(criado) if criado else "",
        "alertas": alertas,
    }


# ---------------------------------------------------------------- disco

def expandir_dependencias(ids, catalogo):
    vistos, ordem = set(), []

    def visita(i):
        if i in vistos or i not in catalogo:
            return
        vistos.add(i)
        for d in catalogo[i]["depende"]:
            visita(d)
        ordem.append(i)

    for i in ids:
        visita(i)
    return ordem


def situacao_lab(lab, catalogo, pedidos, cfg):
    """Estado de cada programa no lab: instalado > aprovado > pendente (o maior vence)."""
    estado = {}   # chave -> dict

    def registrar(chave, nome, grupo, tamanho_mb, sw=None, pedidos_ids=(), estimado=False):
        atual = estado.get(chave)
        if atual and PESO_GRUPO[atual["grupo"]] >= PESO_GRUPO[grupo]:
            atual["pedidos"].extend(p for p in pedidos_ids if p not in atual["pedidos"])
            return
        estado[chave] = {"chave": chave, "sw": sw, "nome": nome, "grupo": grupo,
                         "tamanho_mb": tamanho_mb, "estimado": estimado,
                         "pedidos": list(pedidos_ids) + (atual["pedidos"] if atual else []),
                         "dependencia": False}

    for item in catalogo.values():
        if lab["id"] in item["instalado_em"]:
            registrar(item["id"], item["nome"], "instalado", item["tamanho_mb"], item["id"])

    for p in pedidos:
        if lab["id"] not in p["labs"] or not p["grupo"]:
            continue
        if p["sw"]:
            for dep in expandir_dependencias([p["sw"]], catalogo):
                it = catalogo[dep]
                registrar(dep, it["nome"], p["grupo"], it["tamanho_mb"], dep,
                          [p["numero"]] if dep == p["sw"] else [])
                if dep != p["sw"]:
                    estado[dep]["dependencia"] = estado[dep]["dependencia"] or not estado[dep]["pedidos"]
        else:
            registrar("livre:" + normalizar(p["programa"]), p["programa"], p["grupo"],
                      p["tamanho_mb"], None, [p["numero"]], estimado=True)

    reservado_mb = {k: v * 1024 for k, v in lab["reservado_gb"].items()}
    total_mb = lab["disco_gb"] * 1024
    margem_mb = round(total_mb * lab.get("margem_seguranca", 0))
    soma = {g: sum(e["tamanho_mb"] for e in estado.values() if e["grupo"] == g) for g in PESO_GRUPO}
    usado_confirmado = sum(reservado_mb.values()) + soma["instalado"] + soma["aprovado"]
    previsto = usado_confirmado + soma["pendente"]

    def nivel(fracao):
        if fracao >= cfg["alerta_disco"]["critico"]:
            return "critico"
        if fracao >= cfg["alerta_disco"]["atencao"]:
            return "atencao"
        return "ok"

    programas = sorted(estado.values(), key=lambda e: (-PESO_GRUPO[e["grupo"]], -e["tamanho_mb"]))
    return {
        "disco": {
            "total_mb": total_mb,
            "reservado_mb": reservado_mb,
            "margem_mb": margem_mb,
            "instalado_mb": soma["instalado"],
            "aprovado_mb": soma["aprovado"],
            "pendente_mb": soma["pendente"],
            "previsto_mb": previsto,
            "livre_mb": total_mb - margem_mb - previsto,
            "fracao_confirmada": round(usado_confirmado / total_mb, 4),
            "fracao_prevista": round(previsto / total_mb, 4),
            "nivel": nivel(previsto / total_mb),
            "nivel_com_margem": nivel((previsto + margem_mb) / total_mb),
        },
        "programas": programas,
    }


# ---------------------------------------------------------------- scripts de instalação

def script_windows(lab, ids, catalogo, gerado_em):
    winget, choco, manual = [], [], []
    for i in ids:
        inst = catalogo[i].get("instalacao", {}).get("windows", {})
        if "winget" in inst:
            winget.append((inst["winget"], catalogo[i]["nome"]))
        elif "choco" in inst:
            choco.append((inst["choco"], catalogo[i]["nome"]))
        else:
            manual.append((catalogo[i]["nome"], inst.get("manual", "sem instrução no catálogo")))
    linhas = [
        f"# {lab['nome']} — {lab['so_descricao']}",
        f"# Gerado automaticamente em {gerado_em} a partir de catalogo/ e dos pedidos aprovados.",
        "# Não edite à mão: altere o catálogo ou o status do pedido e deixe o GitHub Actions gerar de novo.",
        "# Rodar como Administrador na máquina-modelo, antes de capturar a imagem no FOG.",
        "",
        "$ErrorActionPreference = 'Continue'",
        "$log = \"$env:ProgramData\\ifpr-labs\\instalacao-$(Get-Date -Format yyyyMMdd-HHmm).log\"",
        "New-Item -ItemType Directory -Force -Path (Split-Path $log) | Out-Null",
        "$falhas = @()",
        "",
        "$winget = @(",
        *[f"    @{{ Id = '{w}'; Nome = '{n}' }}" for w, n in winget],
        ")",
        "foreach ($p in $winget) {",
        "    Write-Host \"==> $($p.Nome)\" -ForegroundColor Cyan",
        "    winget install --id $p.Id --exact --silent --scope machine `",
        "        --accept-package-agreements --accept-source-agreements --disable-interactivity *>> $log",
        "    # 0 = instalado; -1978335189 = já estava instalado e atualizado",
        "    if ($LASTEXITCODE -ne 0 -and $LASTEXITCODE -ne -1978335189) { $falhas += $p.Nome }",
        "}",
    ]
    if choco:
        linhas += ["", "# Chocolatey"] + [
            f"choco install {c} -y --no-progress *>> $log; if ($LASTEXITCODE -ne 0) {{ $falhas += '{n}' }}"
            for c, n in choco]
    if manual:
        linhas += ["", "# Instalação manual (não automatizável):"] + [f"#   - {n}: {m}" for n, m in manual]
        linhas += ["Write-Host 'Pendentes de instalação manual:' -ForegroundColor Yellow"] + [
            f"Write-Host '  - {n}'" for n, _ in manual]
    linhas += [
        "",
        "if ($falhas) { Write-Host \"Falharam: $($falhas -join ', ') — veja $log\" -ForegroundColor Red; exit 1 }",
        "Write-Host \"Concluído. Log: $log\" -ForegroundColor Green",
    ]
    return "\r\n".join(linhas) + "\r\n"


def script_linux(lab, ids, catalogo, gerado_em):
    apt, flatpak, snap, manual = [], [], [], []
    for i in ids:
        inst = catalogo[i].get("instalacao", {}).get("linux", {})
        nome = catalogo[i]["nome"]
        if "apt" in inst:
            apt += inst["apt"].split()
        elif "flatpak" in inst:
            flatpak.append(inst["flatpak"])
        elif "snap" in inst:
            snap.append(inst["snap"])
        else:
            manual.append((nome, inst.get("manual", "sem instrução no catálogo")))
    linhas = [
        "#!/usr/bin/env bash",
        f"# {lab['nome']} — {lab['so_descricao']}",
        f"# Gerado automaticamente em {gerado_em} a partir de catalogo/ e dos pedidos aprovados.",
        "# Não edite à mão. Rodar com sudo na máquina-modelo, antes de capturar a imagem no FOG.",
        "set -uo pipefail",
        "[ \"$(id -u)\" -eq 0 ] || { echo 'Rode com sudo.'; exit 1; }",
        "falhas=()",
        "export DEBIAN_FRONTEND=noninteractive",
        "apt-get update",
    ]
    if apt:
        linhas.append(f"apt-get install -y {' '.join(dict.fromkeys(apt))} || falhas+=(apt)")
    if flatpak:
        linhas += [
            "command -v flatpak >/dev/null || apt-get install -y flatpak",
            "flatpak remote-add --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo",
        ] + [f"flatpak install -y --system --noninteractive flathub {f} || falhas+=({f})" for f in flatpak]
    if snap:
        linhas += [f"snap install {s} || falhas+=({s.split()[0]})" for s in snap]
    if manual:
        linhas += ["", "# Instalação manual (não automatizável):"] + [f"#   - {n}: {m}" for n, m in manual]
        linhas += ["echo 'Pendentes de instalação manual:'"] + [f"echo '  - {n}'" for n, _ in manual]
    linhas += [
        "",
        "if [ ${#falhas[@]} -gt 0 ]; then echo \"Falharam: ${falhas[*]}\"; exit 1; fi",
        "echo 'Concluído.'",
    ]
    return "\n".join(linhas) + "\n"


# ---------------------------------------------------------------- triagem (comentário automático)

def triagem(issue, cfg, catalogo):
    hoje = dt.date.today()
    p = montar_pedido(issue, cfg, catalogo, hoje)
    labs = {l["id"]: l for l in cfg["laboratorios"]}
    linhas = [f"Olá! Recebemos o pedido de **{p['programa']}**. Este é o resumo automático; "
              "a equipe de TI analisa em seguida.", ""]
    if p["sw"]:
        it = catalogo[p["sw"]]
        linhas.append(f"- Programa reconhecido no catálogo: `{it['id']}` — {it['tamanho_mb']} MB por máquina.")
        deps = [catalogo[d]["nome"] for d in expandir_dependencias([p["sw"]], catalogo) if d != p["sw"]]
        if deps:
            linhas.append(f"- Depende de: {', '.join(deps)} (instalados junto).")
    linhas.append(f"- Laboratórios: {', '.join(labs[l]['nome'] for l in p['labs']) or 'nenhum reconhecido'}.")
    if p["primeira_aula"]:
        linhas.append(f"- Primeira aula: {p['primeira_aula']}.")
    if p["expira"]:
        linhas.append(f"- Período: só este semestre — entra em revisão em {p['expira']}.")
    if p["alertas"]:
        linhas += ["", "**Pontos de atenção**", ""] + [f"- {a}" for a in p["alertas"]]
    linhas += ["", "Acompanhe o andamento pelos rótulos `status/` desta página ou no painel."]
    rotulos = [f"lab/{l}" for l in p["labs"]]
    if p["sw"]:
        rotulos.append(f"sw/{p['sw']}")
    return {"comentario": "\n".join(linhas), "rotulos": rotulos}


# ---------------------------------------------------------------- principal

def construir(issues, saida: Path, gerado_dir: Path, repo: str):
    cfg = carregar_labs()
    catalogo = carregar_catalogo()
    hoje = dt.date.today()
    agora = dt.datetime.now(dt.timezone(dt.timedelta(hours=-3))).strftime("%Y-%m-%d %H:%M")

    pedidos = [montar_pedido(i, cfg, catalogo, hoje) for i in issues
               if any(l["name"] == "pedido" for l in i.get("labels", []))]
    pedidos.sort(key=lambda p: (ORDEM_STATUS.index(p["status"]), p["primeira_aula"] or "9999", p["numero"]))

    gerado_dir.mkdir(parents=True, exist_ok=True)
    labs_saida = []
    for lab in cfg["laboratorios"]:
        sit = situacao_lab(lab, catalogo, pedidos, cfg)
        ids = expandir_dependencias(
            [e["sw"] for e in sit["programas"] if e["sw"] and e["grupo"] in ("instalado", "aprovado")], catalogo)
        ids = [i for i in ids if lab["so"] in catalogo[i]["so"]]
        if lab["so"] == "windows":
            nome_script, conteudo = f"{lab['id']}.ps1", script_windows(lab, ids, catalogo, agora)
        else:
            nome_script, conteudo = f"{lab['id']}.sh", script_linux(lab, ids, catalogo, agora)
        (gerado_dir / nome_script).write_text(conteudo, encoding="utf-8")
        labs_saida.append({
            "id": lab["id"], "nome": lab["nome"], "so": lab["so"], "so_descricao": lab["so_descricao"],
            "maquinas": lab["maquinas"], "disco_gb": lab["disco_gb"], "imagem_fog": lab.get("imagem_fog", ""),
            "script": f"scripts/{nome_script}", **sit,
        })

    dados = {
        "gerado_em": agora,
        "campus": cfg["campus"],
        "repo": repo,
        "prazo_minimo_dias": cfg["prazo_minimo_dias"],
        "alerta_disco": cfg["alerta_disco"],
        "semestre": {k: str(v) for k, v in (cfg.get("semestre") or {}).items()},
        "status": [{"codigo": k, "texto": v[0], "grupo": v[1]} for k, v in STATUS.items()],
        "laboratorios": labs_saida,
        "pedidos": pedidos,
        "catalogo": [{k: v for k, v in it.items() if not k.startswith("_")} for it in catalogo.values()],
    }

    if saida:
        if saida.exists():
            shutil.rmtree(saida)
        shutil.copytree(RAIZ / "site", saida)
        shutil.copytree(gerado_dir, saida / "scripts")
        (saida / "data.json").write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
    return dados


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--issues", type=Path, help="JSON com a lista de issues (gh issue list --json ...)")
    ap.add_argument("--saida", type=Path, help="pasta do site gerado")
    ap.add_argument("--gerado", type=Path, default=RAIZ / "gerado", help="pasta dos scripts por laboratório")
    ap.add_argument("--repo", default="", help="owner/repo, para os links do painel")
    ap.add_argument("--triagem", type=Path, help="JSON de uma issue (gh issue view --json ...)")
    a = ap.parse_args()

    if a.triagem:
        issue = json.loads(a.triagem.read_text(encoding="utf-8"))
        print(json.dumps(triagem(issue, carregar_labs(), carregar_catalogo()), ensure_ascii=False))
        return

    issues = json.loads(a.issues.read_text(encoding="utf-8")) if a.issues else []
    dados = construir(issues, a.saida, a.gerado, a.repo)
    for lab in dados["laboratorios"]:
        d = lab["disco"]
        print(f"{lab['nome']:16} previsto {d['fracao_prevista']:6.1%}  livre {d['livre_mb']/1024:6.1f} GB  [{d['nivel']}]")
    print(f"{len(dados['pedidos'])} pedidos processados.")


if __name__ == "__main__":
    main()

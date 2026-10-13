"use strict";

const GB = 1024;
const fmtGB = (mb) => (mb / GB).toLocaleString("pt-BR", { maximumFractionDigits: mb < 10 * GB ? 1 : 0 }) + " GB";
const fmtTam = (mb) => (mb >= GB ? fmtGB(mb) : `${mb} MB`);
const fmtData = (iso) => (iso ? new Date(iso + "T12:00:00").toLocaleDateString("pt-BR", { day: "2-digit", month: "short" }) : "");
const pct = (parte, total) => `${Math.max(0, (parte / total) * 100)}%`;
const el = (tag, attrs = {}, ...filhos) => {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v == null || v === false) continue;
    if (k === "class") n.className = v; else if (k === "text") n.textContent = v; else n.setAttribute(k, v);
  }
  for (const f of filhos.flat()) if (f != null) n.append(f);
  return n;
};
const norm = (s) => (s || "").normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase();

const GRUPO_TEXTO = { instalado: "Instalado", aprovado: "Aprovado, a instalar", pendente: "Em análise" };

let dados;

async function iniciar() {
  try {
    const r = await fetch("data.json", { cache: "no-store" });
    if (!r.ok) throw new Error(r.status);
    dados = await r.json();
  } catch (e) {
    document.getElementById("labs").replaceChildren(
      el("p", { class: "vazio", text: "Não foi possível carregar os dados do painel. Atualize a página em alguns minutos." }));
    return;
  }

  const repo = dados.repo;
  const urlPedido = repo ? `https://github.com/${repo}/issues/new?template=pedido-software.yml` : "#";
  document.getElementById("link-pedir").href = urlPedido;
  document.getElementById("link-repo").href = repo ? `https://github.com/${repo}` : "#";
  document.getElementById("gerado-em").textContent = dados.gerado_em;
  document.getElementById("campus").textContent = dados.campus;
  document.getElementById("prazo").textContent = dados.prazo_minimo_dias;

  desenharLabs();
  prepararFiltros();
  desenharPedidos();
  prepararBusca(urlPedido);
}

// ---------------------------------------------------------------- laboratórios

function desenharLabs() {
  const tpl = document.getElementById("tpl-lab");
  const alvo = document.getElementById("labs");
  alvo.replaceChildren();

  for (const lab of dados.laboratorios) {
    const n = tpl.content.cloneNode(true);
    const art = n.querySelector(".lab");
    const d = lab.disco;
    art.dataset.nivel = d.nivel_com_margem;

    n.querySelector(".lab-nome").textContent = lab.nome;
    n.querySelector(".lab-info").textContent = `${lab.so_descricao}, ${lab.maquinas} máquinas`;

    const livre = n.querySelector(".disco-livre");
    livre.textContent = fmtGB(Math.max(d.livre_mb, 0));
    livre.append(el("small", { text: "livres por máquina" }));
    n.querySelector(".disco-total").textContent = `de ${lab.disco_gb} GB`;

    // barra: sistema | programas (instalado, aprovado, pendente) | livre | margem
    const barra = n.querySelector(".barra");
    const reservado = Object.values(d.reservado_mb).reduce((a, b) => a + b, 0);
    const seg = (cls, mb, titulo) => el("div", { class: `seg seg-${cls}`, style: `flex: 0 0 ${pct(mb, d.total_mb)}`, title: titulo });
    barra.append(seg("sistema", reservado, `Sistema, atualizações e perfis: ${fmtGB(reservado)}`));
    for (const grupo of ["instalado", "aprovado", "pendente"]) {
      for (const p of lab.programas.filter((x) => x.grupo === grupo)) {
        barra.append(seg(grupo, p.tamanho_mb, `${p.nome} — ${fmtTam(p.tamanho_mb)} (${GRUPO_TEXTO[grupo].toLowerCase()})`));
      }
    }
    barra.append(el("div", { class: "seg seg-livre", title: `Livre: ${fmtGB(Math.max(d.livre_mb, 0))}` }));
    barra.append(seg("margem", d.margem_mb, `Margem de segurança: ${fmtGB(d.margem_mb)}`));
    for (const [chave, cls] of [["atencao", ""], ["critico", " critico"]]) {
      const f = dados.alerta_disco[chave];
      barra.append(el("span", { class: "marca" + cls, style: `left: ${f * 100}%`, "aria-hidden": "true" }));
    }
    const programasMb = d.instalado_mb + d.aprovado_mb + d.pendente_mb;
    barra.setAttribute("aria-label",
      `${lab.nome}: sistema ${fmtGB(reservado)}, programas instalados ${fmtGB(d.instalado_mb)}, ` +
      `aprovados ${fmtGB(d.aprovado_mb)}, em análise ${fmtGB(d.pendente_mb)}, livres ${fmtGB(Math.max(d.livre_mb, 0))} de ${lab.disco_gb} GB.`);

    const aviso = n.querySelector(".disco-aviso");
    const usoPrev = Math.round(d.fracao_prevista * 100);
    aviso.textContent = {
      ok: `${usoPrev}% previsto, contando os pedidos em análise. Programas somam ${fmtGB(programasMb)}.`,
      atencao: `${usoPrev}% previsto. Novos programas grandes precisam liberar espaço antes.`,
      critico: `${usoPrev}% previsto. Sem espaço para novos programas sem remover algum.`,
    }[d.nivel_com_margem];

    const lista = n.querySelector(".lista-programas");
    const qtd = lab.programas.length;
    n.querySelector("summary").textContent = `${qtd} ${qtd === 1 ? "programa" : "programas"} neste laboratório`;
    for (const p of lab.programas) {
      lista.append(el("li", {},
        el("span", { class: `amostra s-${p.grupo}`, title: GRUPO_TEXTO[p.grupo] }),
        el("span", {}, p.nome, p.dependencia ? el("span", { class: "dep", text: "  (necessário para outro programa)" }) : null),
        el("span", { class: "tam", text: (p.estimado ? "~" : "") + fmtTam(p.tamanho_mb) })));
    }

    const script = n.querySelector(".lab-script");
    script.href = lab.script;
    script.textContent = `Script de instalação (${lab.so === "windows" ? "PowerShell" : "Bash"})`;

    alvo.append(n);
  }
}

// ---------------------------------------------------------------- pedidos

function prepararFiltros() {
  const sel = document.getElementById("filtro-lab");
  for (const lab of dados.laboratorios) sel.append(el("option", { value: lab.id, text: lab.nome }));
  sel.addEventListener("change", desenharPedidos);
  document.getElementById("filtro-status").addEventListener("change", desenharPedidos);
}

function desenharPedidos() {
  const labFiltro = document.getElementById("filtro-lab").value;
  const stFiltro = document.getElementById("filtro-status").value;
  const nomeLab = Object.fromEntries(dados.laboratorios.map((l) => [l.id, l.nome]));
  const alvo = document.getElementById("pedidos");

  const lista = dados.pedidos.filter((p) => {
    if (labFiltro && !p.labs.includes(labFiltro)) return false;
    if (stFiltro === "abertos") return p.grupo === "pendente" || p.grupo === "aprovado";
    if (stFiltro === "instalado") return p.grupo === "instalado";
    if (stFiltro === "fechados") return !p.grupo;
    return true;
  });

  if (!lista.length) {
    alvo.replaceChildren(el("li", { class: "vazio", text: "Nenhum pedido com esse filtro." }));
    return;
  }

  alvo.replaceChildren(...lista.map((p) => {
    const labs = p.labs.map((l) => nomeLab[l]).join(", ") || "laboratório não informado";
    const meta = [p.disciplina, p.curso].filter(Boolean).join(", ");
    const datas = [
      p.primeira_aula && `Primeira aula em ${fmtData(p.primeira_aula)}`,
      p.expira && `só até ${fmtData(p.expira)}`,
    ].filter(Boolean).join(", ");
    const mostrarAlertas = p.grupo === "pendente" && p.alertas.length;
    return el("li", { class: "pedido" },
      el("div", { class: "pedido-titulo" },
        el("a", { href: p.url, text: p.programa }), " ", el("span", { class: "num", text: `#${p.numero}` })),
      el("div", { class: "pedido-meta", text: `${labs}${tamanhoTexto(p)}` }),
      el("div", { class: "pedido-meta", text: [meta, datas].filter(Boolean).join(". ") + (p.solicitante ? `. Pedido por ${p.solicitante}` : "") }),
      mostrarAlertas ? el("ul", { class: "pedido-alertas" }, p.alertas.map((a) => el("li", { text: a }))) : null,
      el("div", { class: "situacao" },
        el("span", { class: `pill g-${p.grupo || "fechado"}`, text: p.status_texto }),
        p.apoios ? el("span", { class: "apoios", text: `${p.apoios} ${p.apoios === 1 ? "professor também precisa" : "professores também precisam"}` }) : null));
  }));
}

function tamanhoTexto(p) {
  return `, ${p.tamanho_estimado ? "cerca de " : ""}${fmtTam(p.tamanho_mb)} por máquina`;
}

// ---------------------------------------------------------------- busca

function prepararBusca(urlPedido) {
  const campo = document.getElementById("campo-busca");
  const saida = document.getElementById("resultado-busca");
  const nomeLab = Object.fromEntries(dados.laboratorios.map((l) => [l.id, l.nome.replace("Laboratório ", "Lab ")]));

  // onde cada programa do catálogo está, por grupo
  const situacao = {};
  for (const lab of dados.laboratorios) {
    for (const p of lab.programas) {
      const chave = p.sw || p.chave;
      (situacao[chave] ??= { instalado: [], aprovado: [], pendente: [] })[p.grupo].push(lab.id);
    }
  }
  const itens = [
    ...dados.catalogo.map((c) => ({ chave: c.id, nome: c.nome, descricao: c.descricao, termos: norm([c.id, c.nome, ...(c.aliases || [])].join(" ")), so: c.so })),
    ...dados.pedidos.filter((p) => !p.sw && p.grupo).map((p) => ({ chave: "livre:" + norm(p.programa).replace(/[^a-z0-9]/g, ""), nome: p.programa, termos: norm(p.programa), pedido: p })),
  ];

  campo.addEventListener("input", () => {
    const q = norm(campo.value.trim());
    if (q.length < 2) { saida.replaceChildren(); return; }
    const achados = itens.filter((i) => i.termos.includes(q)).slice(0, 6);
    if (!achados.length) {
      saida.replaceChildren(el("li", {},
        "Nenhum laboratório tem esse programa e ninguém pediu ainda. ",
        el("a", { href: urlPedido, text: "Fazer o pedido" })));
      return;
    }
    saida.replaceChildren(...achados.map((i) => {
      const s = situacao[i.chave];
      const partes = [];
      if (s?.instalado.length) partes.push(`instalado no ${s.instalado.map((l) => nomeLab[l]).join(", ")}`);
      if (s?.aprovado.length) partes.push(`aprovado para o ${s.aprovado.map((l) => nomeLab[l]).join(", ")}`);
      if (s?.pendente.length) partes.push(`pedido em análise para o ${s.pendente.map((l) => nomeLab[l]).join(", ")}`);
      const onde = partes.length ? partes.join("; ") : "ainda não está em nenhum laboratório, pode pedir";
      const pedidoAberto = dados.pedidos.find((p) => (p.sw === i.chave || p === i.pedido) && p.grupo === "pendente");
      return el("li", {},
        el("span", { class: "nome", text: i.nome }), el("span", { class: "onde", text: ` — ${onde}.` }),
        pedidoAberto ? el("span", {}, " ", el("a", { href: pedidoAberto.url, text: "Apoiar o pedido existente" })) : null);
    }));
  });
}

iniciar();

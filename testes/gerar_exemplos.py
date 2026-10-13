#!/usr/bin/env python3
"""Gera testes/issues-exemplo.json: pedidos fictícios no mesmo formato do `gh issue list`,
para testar o painel localmente sem GitHub:

  python3 testes/gerar_exemplos.py
  python3 ferramentas/build.py --issues testes/issues-exemplo.json --saida _site
  python3 -m http.server -d _site 8000
"""
import json
from pathlib import Path

PERGUNTAS = [
    ("nome", "Seu nome"), ("curso", "Curso"), ("disciplina", "Disciplina"),
    ("turma", "Turma e número de alunos"), ("labs", "Laboratórios"), ("programa", "Programa"),
    ("site", "Site oficial ou link de download"), ("versao", "Versão"),
    ("complementos", "Extensões, plugins ou bibliotecas"), ("licenca", "Licença"),
    ("licenca_detalhes", "Se precisa de licença ou conta, como funciona?"),
    ("tamanho", "Tamanho aproximado instalado (se souber)"), ("internet", "Precisa de internet?"),
    ("admin", "Os alunos precisam de permissão de administrador?"), ("hardware", "Requisito de hardware"),
    ("persistencia", "Os arquivos dos alunos precisam ficar salvos entre uma aula e outra?"),
    ("aula", "Data da primeira aula que usa o programa"), ("periodo", "Por quanto tempo?"),
    ("teste", "Como saberemos que está funcionando?"),
    ("alternativa", "Aceita uma alternativa livre, se houver?"), ("obs", "Observações"),
]

PADRAO = {"site": "https://exemplo.org", "licenca": "Livre / código aberto", "internet": "Não",
          "admin": "Não", "persistencia": "Sim, na pasta do aluno", "periodo": "Permanente",
          "teste": "Abrir o programa e criar um arquivo novo.", "alternativa": "Sim"}

EXEMPLOS = [
    dict(n=1, status="instalado", criado="2026-08-04", nome="Ana Lima", curso="Técnico em Informática",
         disciplina="Redes de Computadores I", turma="INFO2 — 34 alunos", labs="Laboratório 02",
         programa="Cisco Packet Tracer", licenca="Gratuito", internet="Sim, para login ou ativação",
         aula="2026-08-20"),
    dict(n=2, status="aprovado", criado="2026-09-15", nome="Carlos Pereira", curso="Técnico em Informática",
         disciplina="Programação Orientada a Objetos", turma="INFO3 — 30 alunos",
         labs="Laboratório 02, Laboratório 03", programa="NetBeans", aula="2026-10-20"),
    dict(n=3, status="agendado", criado="2026-09-22", nome="Paula Reis", curso="Licenciatura em Matemática",
         disciplina="Geometria Analítica", turma="MAT1 — 28 alunos", labs="Laboratório 04",
         programa="GeoGebra", aula="2026-10-27", periodo="Só este semestre"),
    dict(n=4, status="em-analise", criado="2026-10-06", nome="Rafael Costa", curso="Técnico em Informática",
         disciplina="Sistemas Embarcados", turma="INFO3 — 30 alunos", labs="Laboratório 01",
         programa="Arduino IDE", complementos="ESP32 (Espressif)\nBiblioteca DHT sensor",
         internet="Sim, o programa funciona online", hardware="Porta USB livre para a placa",
         aula="2026-10-21", admin="Sim"),
    dict(n=5, status="novo", criado="2026-10-11", nome="Juliana Alves", curso="Técnico em Informática",
         disciplina="Computação Gráfica", turma="INFO4 — 25 alunos", labs="Laboratório 03",
         programa="Blender 4.2", hardware="Placa de vídeo com OpenGL 4.3", aula="2026-11-10", apoios=3),
    dict(n=6, status="aguardando-licenca", criado="2026-09-30", nome="Marcos Dias",
         curso="Técnico em Edificações", disciplina="Desenho Técnico Assistido", turma="EDI2 — 32 alunos",
         labs="Laboratório 01, Laboratório 03", programa="AutoCAD 2026",
         licenca="Licença educacional gratuita",
         licenca_detalhes="Cada aluno cria conta educacional Autodesk.", tamanho="12 GB",
         internet="Sim, para login ou ativação", aula="2026-11-03"),
    dict(n=7, status="novo", criado="2026-10-12", nome="Fernanda Rocha", curso="Técnico em Informática",
         disciplina="Banco de Dados", turma="INFO2 — 34 alunos", labs="Laboratório 01, Laboratório 04",
         programa="MySQL Workbench", aula="2026-10-19"),
    dict(n=8, status="recusado", criado="2026-09-01", nome="Pedro Santos", curso="Técnico em Informática",
         disciplina="Projeto Integrador", turma="INFO4 — 25 alunos", labs="Laboratório 02",
         programa="Photoshop", licenca="Pago — ainda não temos licença", tamanho="5 GB",
         aula="2026-09-10", alternativa="Não, precisa ser este"),
]


def corpo(e):
    d = {**PADRAO, **e}
    return "\n\n".join(f"### {rotulo}\n\n{d.get(k) or '_No response_'}" for k, rotulo in PERGUNTAS)


issues = [{
    "number": e["n"],
    "title": f"[Pedido] {e['programa']}",
    "body": corpo(e),
    "labels": [{"name": "pedido"}, {"name": f"status/{e['status']}"}],
    "state": "CLOSED" if e["status"] in ("recusado",) else "OPEN",
    "createdAt": e["criado"] + "T12:00:00Z",
    "url": f"https://github.com/OWNER/REPO/issues/{e['n']}",
    "reactionGroups": [{"content": "THUMBS_UP", "users": {"totalCount": e.get("apoios", 0)}}],
} for e in EXEMPLOS]

destino = Path(__file__).with_name("issues-exemplo.json")
destino.write_text(json.dumps(issues, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"{len(issues)} pedidos fictícios em {destino}")

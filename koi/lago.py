"""Coloca o koi num lago e escreve a legenda no README do perfil.

Roda no workflow logo depois do git-koi, com o snapshot que ele coletou
($RUNNER_TEMP/koi-snapshot.json). Lê só o snapshot público; não acessa a rede.

    python koi/lago.py <snapshot.json> <koi.gif> <comportamento> <README.md>
"""
import json
import math
import re
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

from PIL import Image, ImageDraw

LADO = 320
COMPORTAMENTO = {
    "deep rest": "descansa no fundo (60 dias ou mais sem contribuições)",
    "rest": "descansa (14 dias ou mais sem contribuições)",
    "surface feeding": "come na superfície (primeira contribuição da semana)",
    "dart": "dá arrancadas (semana entre as mais ativas do ano, ou marco de contribuições)",
    "cruise": "nada tranquilo (um dia comum)",
}
FASES = [(500, "filhote: as cores ainda estão claras"),
         (1_500, "jovem: cores plenas, corpo ainda crescendo"),
         (12_750, "adulto em formação"),
         (10**12, "adulto")]


def fundo(frame_idx: int, total: int) -> Image.Image:
    """Água: gradiente do raso ao fundo, com ondulação que anda junto da animação."""
    import numpy as np
    fase = 2 * math.pi * frame_idx / total
    y, x = np.mgrid[0:LADO, 0:LADO].astype(float)
    t = y / LADO
    onda = np.sin(x / 19 + fase) * np.sin(y / 27 - fase) * 7
    rgb = np.stack([150 - 95 * t + onda, 205 - 105 * t + onda, 220 - 70 * t + onda], axis=-1)
    im = Image.fromarray(np.clip(rgb, 0, 255).astype("uint8"), "RGB")
    d = ImageDraw.Draw(im)
    for i in range(6):  # reflexos de luz
        cx = (i * 43 + frame_idx * 2) % LADO
        cy = 24 + (i * 37) % 250
        d.ellipse([cx, cy, cx + 13, cy + 2], fill=(205, 235, 240))
    return im


def lago(koi_gif: Path, saida: Path) -> None:
    koi = Image.open(koi_gif)
    n = koi.n_frames
    duracao = koi.info.get("duration", 70)
    fundos = [fundo(i, n) for i in range(0, n, 1)]
    quadros = []
    for i in range(n):
        koi.seek(i)
        f = fundos[i].copy()
        camada = koi.convert("RGBA").resize((LADO, LADO), Image.NEAREST)
        f.paste(camada, (0, 0), camada)
        quadros.append(f.convert("P", palette=Image.ADAPTIVE, colors=64))
    quadros[0].save(saida, save_all=True, append_images=quadros[1:], duration=duracao,
                    loop=0, optimize=True, disposal=2)


def medidas(snap: dict) -> dict:
    repos = [r for r in snap["repositories"] if r["visibility"] == "public" and not r["is_fork"]
             and r.get("primary_language")]
    linguas = Counter(r["primary_language"] for r in repos)
    dias = {date.fromisoformat(d["date"]): d["contribution_count"]
            for d in snap["contribution_history"]["days"]}
    total = sum(dias.values())
    ultimo = max(dias)
    semanas = {}
    for dia, n in dias.items():
        seg = dia - timedelta(days=dia.weekday())
        semanas[seg] = semanas.get(seg, 0) + (1 if n > 0 else 0)
    seg_atual = ultimo - timedelta(days=ultimo.weekday())
    seq = 0
    s = seg_atual
    if semanas.get(s, 0) == 0:  # semana em curso ainda sem atividade não quebra a sequência
        s -= timedelta(days=7)
    while semanas.get(s, 0) > 0:
        seq += 1
        s -= timedelta(days=7)
    ultimos7 = sum(n for d, n in dias.items() if d > ultimo - timedelta(days=7))
    fase = next(txt for limite, txt in FASES if total < limite)
    # maior sequência de semanas ativas, dias ativos no último ano e o melhor dia
    maior, corrida = 0, 0
    for seg in sorted(semanas):
        corrida = corrida + 1 if semanas[seg] > 0 else 0
        maior = max(maior, corrida)
    ano = {d: n for d, n in dias.items() if d > ultimo - timedelta(days=365)}
    ativos_ano = sum(1 for n in ano.values() if n > 0)
    melhor_dia = max(dias, key=lambda d: dias[d])
    # barrinha das últimas 12 semanas, uma letra por semana (contribuições na semana)
    blocos = " ▁▂▃▄▅▆▇█"
    ult12 = []
    s = seg_atual - timedelta(days=7 * 12)  # 12 semanas fechadas, sem a semana em curso
    for _ in range(12):
        ult12.append(sum(n for d, n in dias.items() if s <= d < s + timedelta(days=7)))
        s += timedelta(days=7)
    topo = max(ult12) or 1
    barra = "".join(blocos[min(8, round(v / topo * 8))] for v in ult12)
    return {"linguas": linguas, "n_repos": len(repos), "cores": snap["language_colors"],
            "total": total, "seq": seq, "ultimos7": ultimos7, "fase": fase, "dia": ultimo,
            "maior": maior, "ativos_ano": ativos_ano, "melhor_dia": melhor_dia,
            "melhor_n": dias[melhor_dia], "barra": barra}


def legenda(m: dict, comportamento: str) -> str:
    """Bloco do README em tabela de duas colunas: imagem à esquerda, dados à direita.

    Tabela em vez de imagem flutuante (align="left"): no GitHub o float deixa os
    marcadores da lista encostados na imagem. A tabela mantém a coluna de texto
    separada, com espaçamento fixo, em qualquer largura de tela.
    """
    def selo(l: str, n: int) -> str:
        rotulo = l.replace(" ", "%20").replace("-", "--")
        cor = m["cores"].get(l, "#888888").lstrip("#")
        s = "s" if n > 1 else ""
        return (f'<img src="https://img.shields.io/badge/{rotulo}-{n}%20repo{s}-{cor}" '
                f'alt="{l}">')

    chips = " ".join(selo(l, n) for l, n in m["linguas"].most_common())
    total = f"{m['total']:,}".replace(",", ".")
    plural = "s" if m["seq"] != 1 else ""
    recorde = m["melhor_dia"].strftime("%d/%m/%Y")
    return (
        "<!-- KOI:INICIO (gerado todo dia pelo workflow koi.yml; não editar à mão) -->\n"
        "<table><tr>\n"
        '<td width="320" valign="top"><img src="koi/lago.gif" width="300" '
        'alt="Koi gerado a partir da atividade pública no GitHub"></td>\n'
        '<td valign="top">\n\n'
        "**Atividade no GitHub.** A imagem é gerada todos os dias a partir dos dados públicos: as cores vêm das linguagens e o tamanho, do volume de contribuições.\n\n"
        f"**Linguagens** em {m['n_repos']} repositórios públicos:<br/>\n{chips}\n\n"
        f"**Contribuições:** {total} no total<br/>\n"
        f"**Constância:** {m['seq']} semana{plural} consecutiva{plural} com atividade; "
        f"{m['ativos_ano']} dias ativos no último ano<br/>\n"
        f"**Recorde diário:** {m['melhor_n']} contribuições ({recorde})\n\n"
        f"**Últimas 12 semanas:** <code>{m['barra']}</code>\n\n"
        '<sub>Gerado com <a href="https://github.com/yalongwastaken/git-koi">git-koi</a>; '
        f"dados até {m['dia'].strftime('%d/%m/%Y')}.</sub>\n\n"
        "</td>\n"
        "</tr></table>\n"
        "<!-- KOI:FIM -->"
    )


def main() -> int:
    snap_path, gif_path, comportamento, readme_path = sys.argv[1:5]
    snap = json.loads(Path(snap_path).read_text())
    gif = Path(gif_path)
    lago(gif, gif.with_name("lago.gif"))
    bloco = legenda(medidas(snap), comportamento)
    readme = Path(readme_path)
    t = readme.read_text()
    padrao = re.compile(r"<!-- KOI:INICIO.*?<!-- KOI:FIM -->", re.S)
    antigo = '<img src="koi/koi.gif" width="256" alt="Koi desenhado a partir da minha atividade no GitHub">'
    if padrao.search(t):
        t = padrao.sub(lambda _: bloco, t)
    elif antigo in t:
        t = t.replace(antigo, bloco)
    else:
        sys.exit("README sem marcador do koi")
    readme.write_text(t)
    print("lago e legenda atualizados:", comportamento)
    return 0


if __name__ == "__main__":
    sys.exit(main())

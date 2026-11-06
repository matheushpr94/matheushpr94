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

LADO = 256
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
        cy = 20 + (i * 31) % 190
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
    return {"linguas": linguas, "n_repos": len(repos), "cores": snap["language_colors"],
            "total": total, "seq": seq, "ultimos7": ultimos7, "fase": fase, "dia": ultimo}


def legenda(m: dict, comportamento: str) -> str:
    chips = " · ".join(
        f"![{l}](https://img.shields.io/badge/{l.replace(' ', '%20').replace('-', '--')}-{n}%20repo{'s' if n > 1 else ''}-{m['cores'].get(l, '#888888').lstrip('#')})"
        for l, n in m["linguas"].most_common())
    nada = COMPORTAMENTO.get(comportamento, comportamento)
    total = f"{m['total']:,}".replace(",", ".")
    plural = "s" if m["seq"] != 1 else ""
    return (
        "<!-- KOI:INICIO (gerado todo dia pelo workflow koi.yml; não editar à mão) -->\n"
        '<img src="koi/lago.gif" width="256" align="left" '
        'alt="Koi num lago, desenhado a partir da minha atividade pública no GitHub">\n\n'
        "**Meu koi** é redesenhado todo dia a partir da minha atividade pública no GitHub.\n\n"
        f"- **Cores:** as linguagens dos meus {m['n_repos']} repositórios públicos {chips}\n"
        f"- **Tamanho:** {total} contribuições desde que criei a conta ({m['fase']})\n"
        f"- **Marcas no corpo:** {m['seq']} semana{plural} seguida{plural} com atividade\n"
        f"- **Hoje ele {nada}:** {m['ultimos7']} contribuições nos últimos 7 dias\n\n"
        '<sub>Feito com <a href="https://github.com/yalongwastaken/git-koi">git-koi</a>; '
        f"dados até {m['dia'].strftime('%d/%m/%Y')}.</sub>\n"
        '<br clear="left"/>\n'
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

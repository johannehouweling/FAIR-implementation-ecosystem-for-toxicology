"""Figure 2: the FAIR principles that the FAIR-enabling resources of the timeline enable, by origin, as an SVG and a
PDF (120 mm wide, Arial), with the counts its legend quotes as LaTeX macros (fig2_fers.tex).

A resource counts under each principle that one of its FSR types enables in the FIP ontology.

    uv run --group figures python figures/fig2_fers.py
"""
from pathlib import Path

import matplotlib
from matplotlib import font_manager
from matplotlib.colors import to_rgb
from matplotlib.figure import Figure
from matplotlib.patches import PathPatch, Rectangle
from matplotlib.path import Path as Bezier

from fairtox import model

OUT = Path(__file__).with_suffix('.pdf')
COLOUR = {'Generic': '#eb6834', 'Life Sciences': '#1baf7a', 'Toxicology': '#6250d6'}   # as in the timeline
ORIGINS = list(COLOUR)                                         # top to bottom on the right

drawn = [r for r in model.normalise(model.load())['hasPart'] if model.in_figure(r)]
enabling = {p: [r for r in drawn if p in r.get('principles', [])] for p in model.PRINCIPLE_ORDER}
count = {p: {o: sum(r['origin'] == o for r in rs) for o in ORIGINS} for p, rs in enabling.items()}
label = {p: ', '.join(sorted(model.fsr_types()[t][0] for t, (_, own) in model.enables().items() if own == {p}))
         for p in count}
resources = {o: len({r['@id'] for rs in enabling.values() for r in rs if r['origin'] == o}) for o in ORIGINS}

font_manager.findfont('Arial', fallback_to_default=False)      # stops here when Arial is missing
matplotlib.rcParams.update({'font.family': 'Arial', 'font.size': 6, 'pdf.fonttype': 42, 'svg.fonttype': 'none',
                            'svg.hashsalt': OUT.stem})
W = 120 / 25.4 * 72                                            # width in pt; x is in pt, y in resources
U, GAP, GROUP_GAP, MIN_SLOT, PAD = 1.9, 2.2, 6.0, 4.6, 6.0     # pt per resource; gaps, smallest slot, margin
XB, XC, XL, XR, NW = 15, 21, 160, W - 58, 4                    # bracket, codes, left nodes, right nodes, node width

left, spans, y = [], [], 0.0
for i, (group, principles) in enumerate(model.PRINCIPLES.items()):
    y += GROUP_GAP - GAP if i else 0
    y0 = y
    for p in principles:
        total = sum(count[p].values())
        slot = max(total, MIN_SLOT)
        left.append((p, y + (slot - total) / 2, total))
        y += slot + GAP
    spans.append((group, y0, y - GAP))
H = y - GAP
bands = {o: sum(c[o] for c in count.values()) for o in ORIGINS}
right, y = {}, 0.0
for o in ORIGINS:
    right[o] = y
    y += bands[o] + (H - sum(bands.values())) / (len(ORIGINS) - 1)

fig = Figure(figsize=(W / 72, (H + 2 * PAD) * U / 72))
ax = fig.add_axes([0, 0, 1, 1])
ax.set_xlim(0, W)
ax.set_ylim(H + PAD, -PAD)
ax.axis('off')

# ribbons: the largest first, a generic one under another of its size; a white edge separates those that cross
at = dict(right)
for p, y0, _ in left:
    for o in ORIGINS:
        if v := count[p][o]:
            x0, x1, xm, b = XL + NW, XR, (XL + NW + XR) / 2, at[o]
            path = Bezier([(x0, y0), (xm, y0), (xm, b), (x1, b), (x1, b + v), (xm, b + v), (xm, y0 + v), (x0, y0 + v),
                           (x0, y0)], [Bezier.MOVETO, *[Bezier.CURVE4] * 3, Bezier.LINETO, *[Bezier.CURVE4] * 3,
                                       Bezier.CLOSEPOLY])
            z = -v - 0.5 * (o == 'Generic')
            ax.add_patch(PathPatch(path, fc='white', ec='white', lw=0.6, zorder=z))
            ax.add_patch(PathPatch(path, fc=[1 - 0.51 * (1 - c) for c in to_rgb(COLOUR[o])], ec='none', zorder=z))
            y0, at[o] = y0 + v, b + v

pairs = []
for p, y0, total in left:
    mid, ink = y0 + total / 2, '#222222' if total else '#a8a8a8'
    ax.add_patch(Rectangle((XL, y0), NW, total, fc='#333333', ec='none'))
    ax.text(XL - 3, mid, total, ha='right', va='center', color=ink)
    pairs.append((ax.text(XC, mid, p, ha='left', va='center', color=ink, fontweight='bold'),
                  ax.text(XL - 14, mid, label[p], ha='right', va='center', color=ink)))
for group, y0, y1 in spans:
    ax.plot([XB, XB], [y0, y1], color='#444444', lw=0.6, solid_capstyle='butt')
    ax.text(XB - 4, (y0 + y1) / 2, group, rotation=90, ha='right', va='center', fontsize=7, color='#333333')
for o in ORIGINS:                                              # the number is resources, the height their bands
    ax.add_patch(Rectangle((XR, right[o]), NW * 1.5, bands[o], fc=COLOUR[o], ec='none'))
    ax.text(XR + NW * 1.5 + 5, right[o] + bands[o] / 2, f'{o.capitalize()}\n{resources[o]}', ha='left', va='center',
            fontsize=7, color='#222222')
ax.text(XR + NW * 1.5 + 5, -PAD / 2, 'FER origin', ha='left', va='center', fontsize=7, fontweight='bold',
        color='#222222')

# every text inside the figure, no principle touching its label
box = lambda t: t.get_window_extent()
assert all(fig.bbox.contains(*box(t).min) and fig.bbox.contains(*box(t).max) for t in ax.texts)
assert all(box(code).x1 + 4 < box(text).x0 for code, text in pairs)

for suffix, date in ('.pdf', 'CreationDate'), ('.svg', 'Date'):   # no build time: the same data, the same files
    fig.savefig(OUT.with_suffix(suffix), metadata={date: None})
macros = {'Total': sum(resources.values()), 'Assignments': sum(bands.values()),
          **{o.replace(' ', ''): n for o, n in resources.items()}}
OUT.with_suffix('.tex').write_text(''.join(f'\\newcommand{{\\fers{k}}}{{{v}}}\n' for k, v in macros.items()))
print(OUT, macros)

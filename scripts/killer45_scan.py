# -*- coding: utf-8 -*-
"""杀手数独 45 法则全量扫描器（通用版 v1）
================================================
用法:
    python killer45-scan.py <题目.json> [最大区域组合数，默认6]

输入 JSON 格式（格子为 0 基坐标 [行,列]）:
    {"cages": [{"sum": 16, "cells": [[3,0],[3,1],[4,0],[4,1]]}, ...]}

输出:
    1. 终端文字报告
    2. <题目名>_45map.html —— 盘面高亮图：能用 45 法则的区域直接涂色，
       鼠标悬停/点击右侧关系条目，盘面上对应格子和区域跟着亮。

原理:
    枚举 27 个区域（9宫+9行+9列）的所有连通组合（1~6 个），对每个组合 U:
      加权方程 Σ_{c∈U} m(c)·x(c) = 45k，m(c)=覆盖 c 的区域个数。
    完全在 U 内且重数一致的笼子贡献已知常数，剩余格子进入方程:
      ① 直接锁定（1格）  ② 幽灵笼子（2~4格的和）
      ③ 化简关系式（与笼子方程互相代入后的少格关系）
      ④ 重叠格关系（行+宫等混合区域，重叠格系数2）
    注意: 幽灵笼子不是真笼子，格子间只在同行/列/宫时才互斥。
"""
import json
import sys
import os
from itertools import combinations
from collections import Counter

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# ---------------- 输入 ----------------
if len(sys.argv) < 2:
    print(__doc__)
    sys.exit(1)

path = sys.argv[1]
MAXK = int(sys.argv[2]) if len(sys.argv) > 2 else 6

with open(path, encoding="utf-8") as f:
    data = json.load(f)

cages = []
for i, c in enumerate(data["cages"], 1):
    cells = tuple(sorted(r * 9 + cc for r, cc in c["cells"]))  # 0 基 → 编号 r*9+c
    cages.append({"id": i, "sum": c["sum"], "cells": cells})

n_cells = len(set(cell for cg in cages for cell in cg["cells"]))
total = sum(cg["sum"] for cg in cages)
print(f"数据核对: {len(cages)} 个笼子, {n_cells} 格, 总和 {total}")
assert n_cells == 81 and total == 405, "核对失败：格子数应为81、总和应为405"

# ---------------- 基础结构 ----------------
def cell_name(cell):
    r, c = divmod(cell, 9)
    return f"{r + 1}行{c + 1}列"

def cells_str(cells):
    return "+".join(cell_name(c) for c in sorted(cells))

sum_count = Counter(cg["sum"] for cg in cages)
def cname(cg):
    base = f"和为{cg['sum']}的{len(cg['cells'])}格笼子"
    if sum_count[cg["sum"]] > 1:
        r, c = divmod(cg["cells"][0], 9)
        base += f"(首格{r + 1}行{c + 1}列)"
    return base

units = []  # (name, frozenset(cell ids))
for br in range(3):
    for bc in range(3):
        b = br * 3 + bc + 1
        cells = frozenset(r * 9 + c for r in range(br * 3, br * 3 + 3)
                          for c in range(bc * 3, bc * 3 + 3))
        units.append((f"第{b}宫", cells))
for r in range(9):
    units.append((f"第{r + 1}行", frozenset(r * 9 + c for c in range(9))))
for c in range(9):
    units.append((f"第{c + 1}列", frozenset(r * 9 + c for r in range(9))))

unit_cells = {i: sorted(cs) for i, (name, cs) in enumerate(units)}
unit_name = {i: name for i, (name, cs) in enumerate(units)}
cage_cells = {cg["id"]: set(cg["cells"]) for cg in cages}

# 区域邻接（连通性）：共享格子 / 宫边相邻 / 行·列序号差1
adj = {i: set() for i in range(27)}
for i in range(27):
    for j in range(i + 1, 27):
        ni, si = units[i]
        nj, sj = units[j]
        conn = bool(si & sj)
        if not conn and ni.endswith("宫") and nj.endswith("宫"):
            bi = int(ni[1:-1]) - 1
            bj = int(nj[1:-1]) - 1
            conn = abs(bi // 3 - bj // 3) + abs(bi % 3 - bj % 3) == 1
        if not conn and ni[-1] == nj[-1] and ni[-1] in "行列":
            conn = abs(int(ni[1:-1]) - int(nj[1:-1])) == 1
        if conn:
            adj[i].add(j)
            adj[j].add(i)

def connected_subset(sub):
    sub = set(sub)
    seen = {sub.__iter__().__next__()}
    stack = list(seen)
    while stack:
        u = stack.pop()
        for v in adj[u]:
            if v in sub and v not in seen:
                seen.add(v)
                stack.append(v)
    return len(seen) == len(sub)

def shares_unit(a, b):
    ra, ca = divmod(a, 9)
    rb, cb = divmod(b, 9)
    return ra == rb or ca == cb or (ra // 3 == rb // 3 and ca // 3 == cb // 3)

def valid_assignments(cells, V):
    """幽灵笼子所有合法赋值：和=V，同行/列/宫的格子互斥"""
    n = len(cells)
    res = []
    def bt(i, cur):
        if i == n:
            if sum(cur) == V:
                res.append(tuple(cur))
            return
        for d in range(1, 10):
            if all(cur[j] != d for j in range(i) if shares_unit(cells[j], cells[i])):
                cur.append(d)
                bt(i + 1, cur)
                cur.pop()
    bt(0, [])
    return res

def ghost_note(cells, V):
    cells = sorted(cells)
    asg = valid_assignments(cells, V)
    if not asg:
        return "!! 无任何合法赋值 —— 真矛盾，必有推导错误或可反向利用", False
    per = []
    for i, cell in enumerate(cells):
        ds = sorted(set(a[i] for a in asg))
        per.append(f"{cell_name(cell)}∈{''.join(map(str, ds))}")
    inter = set(asg[0])
    for a in asg[1:]:
        inter &= set(a)
    note = f"赋值{len(asg)}种: " + "  ".join(per)
    if inter:
        note += f"  必含{sorted(inter)}"
    return note, True

# ---------------- 扫描 ----------------
results_direct = {}   # frozenset -> (V, region_str, sub)
results_ghost = {}    # frozenset -> (V, region_str, sub)
results_weighted = {} # frozenset -> (V, region_str, sub, weights)
results_rel = {}      # frozenset(cell,sign) -> (W, region_str, src)

scanned = 0
for k in range(1, MAXK + 1):
    for sub in combinations(range(27), k):
        if k > 1 and not connected_subset(sub):
            continue
        scanned += 1
        U = set()
        for ui in sub:
            U |= set(unit_cells[ui])

        overlap = {}
        if len(U) < 9 * k:
            cnt = {}
            for ui in sub:
                for cell in unit_cells[ui]:
                    cnt[cell] = cnt.get(cell, 0) + 1
            overlap = {c: m for c, m in cnt.items() if m > 1}
        def m_of(cell):
            return overlap.get(cell, 1)
        disjoint = not overlap

        fully, crossing = [], []
        for cg in cages:
            inter = [c for c in cg["cells"] if c in U]
            if not inter:
                continue
            if len(inter) == len(cg["cells"]):
                fully.append(cg)
            else:
                crossing.append(cg)

        region_str = "+".join(unit_name[ui] for ui in sub)

        known = 0
        covered = set()
        for cg in fully:
            ms = {m_of(c) for c in cg["cells"]}
            if len(ms) == 1:
                known += ms.pop() * cg["sum"]
                covered |= set(cg["cells"])

        innies = sorted(c for c in U if c not in covered)
        if innies:
            weights = {m_of(c) for c in innies}
            V = 45 * k - known
            key = frozenset(innies)
            if weights == {1}:
                if len(innies) == 1:
                    results_direct.setdefault(key, (V, region_str, sub))
                elif len(innies) <= 4:
                    results_ghost.setdefault(key, (V, region_str, sub))
            elif len(innies) <= 3:
                results_weighted.setdefault(key, (V, region_str, sub, tuple(sorted(weights))))

        if disjoint and crossing:
            outies = sorted(c for cg in crossing for c in cg["cells"] if c not in U)
            t = sum(cg["sum"] for cg in crossing) + sum(cg["sum"] for cg in fully)
            if 1 <= len(outies) <= 4:
                key = frozenset(outies)
                if len(outies) == 1:
                    results_direct.setdefault(key, (t - 45 * k, region_str + "·外格", sub))
                else:
                    results_ghost.setdefault(key, (t - 45 * k, region_str + "·外格", sub))

        def add_rels(T, V):
            Ts = set(T)
            for cg in cages:
                cap = Ts & cage_cells[cg["id"]]
                if not cap:
                    continue
                A = sorted(Ts - cap)
                B = sorted(cage_cells[cg["id"]] - Ts)
                if not A or not B:
                    continue
                W = V - cg["sum"]      # ΣA − ΣB = W
                na, nb = len(A), len(B)
                if not ((na + nb <= 3) or (min(na, nb) == 1 and max(na, nb) <= 3)):
                    continue
                if nb < na:            # 小侧放负号位（孤立在左）
                    key = frozenset([(c, +1) for c in B] + [(c, -1) for c in A])
                    val = (-W, region_str, cname(cg), sub)
                else:
                    key = frozenset([(c, +1) for c in A] + [(c, -1) for c in B])
                    val = (W, region_str, cname(cg), sub)
                results_rel.setdefault(key, val)

        if innies and all(m_of(c) == 1 for c in innies):
            add_rels(innies, 45 * k - known)
        if disjoint and crossing:
            outies = sorted(c for cg in crossing for c in cg["cells"] if c not in U)
            if outies:
                t = sum(cg["sum"] for cg in crossing) + sum(cg["sum"] for cg in fully)
                add_rels(outies, t - 45 * k)

print(f"\n扫描完成: 共评估 {scanned} 个区域组合（1~{MAXK} 个区域，连通）\n")

# 关系式去重（正负号翻转视为同一条）
canon_rel = {}
for key, (W, region, src, sub) in sorted(results_rel.items()):
    k2 = frozenset((c, -s) for c, s in key)
    if sorted(k2) < sorted(key):
        key, W = k2, -W
    if key not in canon_rel:
        canon_rel[key] = (W, region, src, sub)

def fmt_eq(pos, neg, W):
    """Σpos − Σneg = W → 展示为 小侧 = 大侧 ± k"""
    if len(neg) <= len(pos):
        left, right, kk = neg, pos, -W
    else:
        left, right, kk = pos, neg, W
    l = "+".join(cell_name(c) for c in left)
    r = "+".join(cell_name(c) for c in right)
    if kk == 0:
        return f"{l} = {r}"
    sign = "+" if kk > 0 else "-"
    return f"{l} = {r} {sign} {abs(kk)}"

# ---------------- 终端报告 ----------------
print("=" * 60)
print("① 直接锁定（一格的值直接算出来）")
if results_direct:
    for key, (V, region, sub) in sorted(results_direct.items(), key=lambda x: x[1][0]):
        (cell,) = sorted(key)
        print(f"  [{region}]  {cell_name(cell)} = {V}")
else:
    print("  （无）")

print("\n" + "=" * 60)
print("② 幽灵笼子（2~4 格的和被锁定，套组合表）")
ghosts = sorted(results_ghost.items(), key=lambda x: (len(x[0]), x[1][0]))
for n, cap, label in ((2, 20, "2 格（最有用）"), (3, 12, "3 格"), (4, 8, "4 格")):
    group = [(k, v) for k, v in ghosts if len(k) == n]
    print(f"-- {label}（{len(group)} 条）--")
    if not group:
        print("  （无）")
    for key, (V, region, sub) in group[:cap]:
        note, _ = ghost_note(sorted(key), V)
        print(f"  [{region}]")
        print(f"    {cells_str(sorted(key))} = {V}")
        print(f"    {note}")
    if len(group) > cap:
        print(f"  ……另有 {len(group) - cap} 条略")

if results_weighted:
    print("\n" + "=" * 60)
    print("③ 重叠格关系（混合区域，重叠格系数为 2，进阶）")
    for key, (V, region, sub, ws) in sorted(results_weighted.items(), key=lambda x: len(x[0])):
        terms = "+".join(f"{m_of(c)}·{cell_name(c)}" for c in sorted(key))
        print(f"  [{region}]  {terms} = {V}")

print("\n" + "=" * 60)
print("④ 化简关系式（45 关系与笼子方程代入后的少格关系）")
rels_sorted = sorted(canon_rel.items(), key=lambda x: len(x[0]))
if rels_sorted:
    for key, (W, region, src, sub) in rels_sorted[:30]:
        pos = sorted(c for c, s in key if s > 0)
        neg = sorted(c for c, s in key if s < 0)
        print(f"  [{region} · {src}]  {fmt_eq(pos, neg, W)}")
    if len(rels_sorted) > 30:
        print(f"  ……另有 {len(rels_sorted) - 30} 条略")
else:
    print("  （无）")

# ---------------- 生成 HTML 盘面图 ----------------
CELL = 44
PAD = 26
BOARD = CELL * 9

def svg_xy(cell):
    r, c = divmod(cell, 9)
    return PAD + c * CELL, PAD + r * CELL

items = []
for key, (V, region, sub) in sorted(results_direct.items(), key=lambda x: x[1][0]):
    (cell,) = sorted(key)
    items.append({"type": "direct", "title": region, "expr": f"{cell_name(cell)} = {V}",
                  "note": "", "cells": [cell], "pos": [cell], "neg": [], "units": list(sub)})
for n, cls, cap in ((2, "g2", 999), (3, "g34", 12), (4, "g34", 8)):
    group = [(k, v) for k, v in ghosts if len(k) == n]
    for key, (V, region, sub) in group[:cap]:
        note, ok = ghost_note(sorted(key), V)
        items.append({"type": cls, "title": region,
                      "expr": f"{cells_str(sorted(key))} = {V}",
                      "note": note if ok else "!!矛盾，见文字报告",
                      "cells": sorted(key), "pos": sorted(key), "neg": [], "units": list(sub)})
for key, (W, region, src, sub) in rels_sorted[:30]:
    pos = sorted(c for c, s in key if s > 0)
    neg = sorted(c for c, s in key if s < 0)
    items.append({"type": "rel", "title": f"{region} · {src}", "expr": fmt_eq(pos, neg, W),
                  "note": f"来源: {src}", "cells": sorted(set(pos + neg)),
                  "pos": pos, "neg": neg, "units": list(sub)})

# HTML 模板
HTML_TMPL = """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<title>杀手数独 45 法则地图</title>
<style>
  body { font-family: "Microsoft YaHei", sans-serif; background: #fafafa; color: #212121; margin: 0; padding: 18px; }
  h1 { font-size: 20px; margin: 0 0 4px; }
  .sub { color: #666; font-size: 13px; margin-bottom: 14px; }
  .wrap { display: flex; gap: 20px; align-items: flex-start; flex-wrap: wrap; }
  .board-panel { background: #fff; border: 1px solid #e0e0e0; border-radius: 10px; padding: 12px; }
  .list-panel { background: #fff; border: 1px solid #e0e0e0; border-radius: 10px; padding: 12px; width: 430px; max-height: 640px; overflow-y: auto; }
  .group-h { font-size: 14px; font-weight: bold; margin: 10px 0 6px; padding: 4px 8px; background: #f5f5f5; border-radius: 6px; }
  .item { padding: 6px 8px; border-radius: 6px; cursor: pointer; border: 1px solid transparent; }
  .item:hover { background: #fff8e1; border-color: #ffd54f; }
  .item.pin { background: #fff3e0; border-color: #ff9800; }
  .item .t { font-size: 13px; font-weight: bold; }
  .item .e { font-size: 14px; margin: 2px 0; }
  .item .n { font-size: 12px; color: #777; }
  .chip { display: inline-block; width: 11px; height: 11px; border-radius: 3px; margin-right: 6px; vertical-align: -1px; }
  .legend { font-size: 12px; color: #555; margin-top: 10px; line-height: 1.9; }
  .legend .chip { margin-right: 4px; }
</style>
</head>
<body>
<h1>杀手数独 45 法则地图</h1>
<div class="sub">__SUMMARY__</div>
<div class="wrap">
  <div class="board-panel">__SVG__<div class="legend">
    <span class="chip" style="background:#ffd54f"></span>直接锁定　
    <span class="chip" style="background:#f48fb1"></span>幽灵笼子·2格　
    <span class="chip" style="background:#ce93d8"></span>幽灵笼子·3~4格<br>
    <span class="chip" style="background:#90caf9"></span>关系式·正项　
    <span class="chip" style="background:#ffab91"></span>关系式·负项　
    <span class="chip" style="background:rgba(255,213,79,.45)"></span>区域（宫/行/列）<br>
    鼠标悬停右侧条目临时高亮，点击固定 / 再点取消
  </div></div>
  <div class="list-panel" id="list"></div>
</div>
<script>
const RELS = __DATA__;
const CELL = 44, PAD = 26;
const COLORS = { direct:'#ffd54f', g2:'#f48fb1', g34:'#ce93d8' };
let pinned = -1;
function cellEl(id){ return document.getElementById('c'+id); }
function clearHl(){
  document.querySelectorAll('.uregion').forEach(e=>e.style.display='none');
  document.querySelectorAll('.ccell').forEach(e=>{e.setAttribute('fill','none');e.setAttribute('stroke','none');});
}
function hl(i){
  clearHl();
  const r = RELS[i];
  (r.units||[]).forEach(u=>{const e=document.getElementById('u'+u); if(e) e.style.display='block';});
  r.cells.forEach(c=>{
    const el = cellEl(c); if(!el) return;
    let col;
    if (r.type==='rel') col = r.pos.includes(c) ? '#90caf9' : '#ffab91';
    else col = COLORS[r.type];
    el.setAttribute('fill', col);
    el.setAttribute('stroke', '#e91e63');
    el.setAttribute('stroke-width', '2');
  });
}
function buildList(){
  const list = document.getElementById('list');
  const groups = [
    {key:'direct', name:'① 直接锁定（先落格）'},
    {key:'g2', name:'② 幽灵笼子 · 2 格（立刻删候选）'},
    {key:'g34', name:'② 幽灵笼子 · 3~4 格'},
    {key:'rel', name:'③ 化简关系式'}
  ];
  groups.forEach(g=>{
    const idxs = RELS.map((r,i)=>[r,i]).filter(([r])=>r.type===g.key).map(([,i])=>i);
    if(!idxs.length) return;
    const h = document.createElement('div'); h.className='group-h'; h.textContent=g.name+'（'+idxs.length+'）';
    list.appendChild(h);
    idxs.forEach(i=>{
      const r = RELS[i];
      const d = document.createElement('div'); d.className='item'; d.dataset.i=i;
      const chipColor = r.type==='direct'?'#ffd54f': r.type==='g2'?'#f48fb1': r.type==='g34'?'#ce93d8':'#90caf9';
      d.innerHTML = '<div class="t"><span class="chip" style="background:'+chipColor+'"></span>'+r.title+'</div>'
        + '<div class="e">'+r.expr+'</div>'
        + (r.note?'<div class="n">'+r.note+'</div>':'');
      d.addEventListener('mouseenter',()=>hl(i));
      d.addEventListener('mouseleave',()=>{ if(pinned>=0) hl(pinned); else clearHl(); });
      d.addEventListener('click',()=>{
        if(pinned===i){ pinned=-1; d.classList.remove('pin'); clearHl(); }
        else{
          document.querySelectorAll('.item.pin').forEach(e=>e.classList.remove('pin'));
          pinned=i; d.classList.add('pin'); hl(i);
        }
      });
      list.appendChild(d);
    });
  });
}
buildList();
</script>
</body>
</html>
"""

def build_svg():
    parts = []
    parts.append(f'<svg width="{BOARD + PAD * 2}" height="{BOARD + PAD * 2}" '
                 f'viewBox="0 0 {BOARD + PAD * 2} {BOARD + PAD * 2}" role="img" aria-label="杀手数独盘面">')
    parts.append(f'<rect x="{PAD}" y="{PAD}" width="{BOARD}" height="{BOARD}" fill="#ffffff"/>')
    # 区域高亮层
    for ui, (name, cs) in enumerate(units):
        r0 = min(c // 9 for c in cs); c0 = min(c % 9 for c in cs)
        h = len(set(c // 9 for c in cs)); w = len(set(c % 9 for c in cs))
        x, y = PAD + c0 * CELL, PAD + r0 * CELL
        parts.append(f'<rect id="u{ui}" class="uregion" x="{x}" y="{y}" width="{w * CELL}" height="{h * CELL}" '
                     f'fill="rgba(255,213,79,0.45)" stroke="#f9a825" stroke-width="2" style="display:none" pointer-events="none"/>')
    # 单元格高亮层
    for cell in range(81):
        x, y = svg_xy(cell)
        parts.append(f'<rect id="c{cell}" class="ccell" x="{x + 1}" y="{y + 1}" width="{CELL - 2}" height="{CELL - 2}" '
                     f'fill="none" stroke="none" style="pointer-events:none"/>')
    # 网格
    for i in range(10):
        w = 2.5 if i in (0, 3, 6, 9) else 1
        col = '#333333' if i in (0, 3, 6, 9) else '#bbbbbb'
        parts.append(f'<line x1="{PAD + i * CELL}" y1="{PAD}" x2="{PAD + i * CELL}" y2="{PAD + BOARD}" stroke="{col}" stroke-width="{w}"/>')
        parts.append(f'<line x1="{PAD}" y1="{PAD + i * CELL}" x2="{PAD + BOARD}" y2="{PAD + i * CELL}" stroke="{col}" stroke-width="{w}"/>')
    # 笼子虚线框 + 和值
    for cg in cages:
        d = []
        for cell in cg["cells"]:
            r, c = divmod(cell, 9)
            x, y = PAD + c * CELL, PAD + r * CELL
            if (cell - 9) not in cage_cells[cg["id"]]:
                d.append(f'M{x} {y} L{x + CELL} {y}')
            if (cell + 9) not in cage_cells[cg["id"]]:
                d.append(f'M{x} {y + CELL} L{x + CELL} {y + CELL}')
            if (cell - 1) not in cage_cells[cg["id"]]:
                d.append(f'M{x} {y} L{x} {y + CELL}')
            if (cell + 1) not in cage_cells[cg["id"]]:
                d.append(f'M{x + CELL} {y} L{x + CELL} {y + CELL}')
        parts.append(f'<path d="{" ".join(d)}" fill="none" stroke="#444444" stroke-width="1.6" stroke-dasharray="5 3"/>')
        first = min(cg["cells"], key=lambda c: (c // 9, c % 9))
        x, y = svg_xy(first)
        parts.append(f'<text x="{x + 4}" y="{y + 13}" font-size="12" font-weight="bold" fill="#c2185b">{cg["sum"]}</text>')
    parts.append('</svg>')
    return "\n".join(parts)

summary = f"{len(cages)} 个笼子 · 总和 {total} · 关系条目 {len(items)} 条"
svg = build_svg()
html = (HTML_TMPL
        .replace("__SUMMARY__", summary)
        .replace("__SVG__", svg)
        .replace("__DATA__", json.dumps(items, ensure_ascii=False)))

out_html = os.path.splitext(path)[0] + "_45map.html"
with open(out_html, "w", encoding="utf-8") as f:
    f.write(html)
print(f"\n盘面图已生成: {out_html}")

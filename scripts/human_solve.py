# -*- coding: utf-8 -*-
"""杀手数独 人类逻辑逐步求解器 v1
================================================
用法: python human-solve.py <题目.json>

只使用人类可复述的技巧，按优先级一步步推，每步记录【看哪 / 用啥招 / 得出啥】，
不许猜数。推到解完输出完整编号步骤单；若卡住，如实报告卡点。

招库（按优先级）:
  A. 隐性唯一（行/列/宫内某数字只有一个位置）
  B. 笼子技巧（笼内隐性唯一 / 笼子只剩一格用余数）
  C. 45关系式定值（关系式中只剩一个未知格）
  D. 幽灵笼子删候选（45法则得到的"几格之和"，砍候选）
  E. 笼子唯一组合删候选
  F. 显性数对删候选
  传播连锁: 每步之后自动做候选过滤，新定格的格子作为连锁步骤记录。
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

if len(sys.argv) < 2:
    print(__doc__); sys.exit(1)
path = sys.argv[1]
with open(path, encoding="utf-8") as f:
    data = json.load(f)

cages = []
for i, c in enumerate(data["cages"], 1):
    cells = tuple(sorted(r * 9 + cc for r, cc in c["cells"]))
    cages.append({"id": i, "sum": c["sum"], "cells": cells})

n_cells = len(set(x for cg in cages for x in cg["cells"]))
total = sum(cg["sum"] for cg in cages)
assert n_cells == 81 and total == 405, "数据核对失败"

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

cage_cells = {cg["id"]: set(cg["cells"]) for cg in cages}
cell_cage = {}
for cg in cages:
    for cell in cg["cells"]:
        cell_cage[cell] = cg["id"]

# 行/列/宫
units = []
for r in range(9):
    units.append((f"第{r + 1}行", [r * 9 + c for c in range(9)]))
for c in range(9):
    units.append((f"第{c + 1}列", [r * 9 + c for r in range(9)]))
for br in range(3):
    for bc in range(3):
        b = br * 3 + bc + 1
        units.append((f"第{b}宫", [r * 9 + c for r in range(br * 3, br * 3 + 3)
                                   for c in range(bc * 3, bc * 3 + 3)]))

def peers(cell):
    r, c = divmod(cell, 9)
    ps = set()
    for i in range(9):
        ps.add(r * 9 + i); ps.add(i * 9 + c)
    br, bc = r // 3 * 3, c // 3 * 3
    for rr in range(br, br + 3):
        for cc in range(bc, bc + 3):
            ps.add(rr * 9 + cc)
    ps.discard(cell)
    return ps

ALL_COMBOS = {n: [cb for cb in combinations(range(1, 10), n)] for n in range(1, 10)}

def shares_unit(a, b):
    ra, ca = divmod(a, 9)
    rb, cb = divmod(b, 9)
    return ra == rb or ca == cb or (ra // 3 == rb // 3 and ca // 3 == cb // 3)

# ---------------- 状态 ----------------
grid = {}
cands = {}
for cg in cages:
    n = len(cg["cells"])
    union = set(d for cb in ALL_COMBOS[n] if sum(cb) == cg["sum"] for d in cb)
    for cell in cg["cells"]:
        cands[cell] = set(union)

def has_matching(cells, combo):
    k = len(cells)
    used = set()
    def bt(i):
        if i == k:
            return True
        for d in combo:
            if d not in used and d in cands[cells[i]]:
                used.add(d)
                if bt(i + 1):
                    return True
                used.discard(d)
        return False
    return bt(0)

def cage_valid_combos(cg):
    n = len(cg["cells"])
    return [cb for cb in ALL_COMBOS[n] if sum(cb) == cg["sum"] and has_matching(cg["cells"], cb)]

steps = []          # (描述, 类型)  类型: place / chain / elim
def log(desc, typ):
    steps.append((desc, typ))

# ---------------- 传播（每步之后跑） ----------------
def propagate():
    """笼子组合过滤 + 已定值删 peers + 裸唯一自动定格。
    新定格的格子记录为连锁步骤。返回是否矛盾。"""
    while True:
        changed = False
        # 已定值删同行列宫
        for cell, v in list(grid.items()):
            for p in peers(cell):
                if p not in grid and v in cands[p]:
                    cands[p].discard(v)
                    if not cands[p]:
                        return False
                    changed = True
        # 笼子组合过滤
        for cg in cages:
            valid = cage_valid_combos(cg)
            if not valid:
                return False
            for cell in cg["cells"]:
                if cell in grid:
                    continue
                new = set(d for cb in valid for d in cb if d in cands[cell])
                if new != cands[cell]:
                    if not new:
                        return False
                    cands[cell] = new
                    changed = True
        # 裸唯一
        for cell in list(cands):
            if cell not in grid and len(cands[cell]) == 1:
                v = next(iter(cands[cell]))
                grid[cell] = v
                cands[cell] = {v}
                log(f"连锁 → {cell_name(cell)} = {v}", "chain")
                changed = True
        if not changed:
            return True

# ---------------- 45 关系库（预生成） ----------------
scan_units = []
for br in range(3):
    for bc in range(3):
        scan_units.append((f"第{br * 3 + bc + 1}宫",
                           frozenset(r * 9 + c for r in range(br * 3, br * 3 + 3)
                                     for c in range(bc * 3, bc * 3 + 3))))
for r in range(9):
    scan_units.append((f"第{r + 1}行", frozenset(r * 9 + c for c in range(9))))
for c in range(9):
    scan_units.append((f"第{c + 1}列", frozenset(r * 9 + c for r in range(9))))
unit_cells_map = {i: set(cs) for i, (n, cs) in enumerate(scan_units)}
unit_name_map = {i: n for i, (n, cs) in enumerate(scan_units)}

adj = {i: set() for i in range(27)}
for i in range(27):
    for j in range(i + 1, 27):
        ni, si = scan_units[i]
        nj, sj = scan_units[j]
        conn = bool(si & sj)
        if not conn and ni.endswith("宫") and nj.endswith("宫"):
            bi, bj = int(ni[1:-1]) - 1, int(nj[1:-1]) - 1
            conn = abs(bi // 3 - bj // 3) + abs(bi % 3 - bj % 3) == 1
        if not conn and ni[-1] == nj[-1] and ni[-1] in "行列":
            conn = abs(int(ni[1:-1]) - int(nj[1:-1])) == 1
        if conn:
            adj[i].add(j); adj[j].add(i)

def connected_subset(sub):
    sub = set(sub)
    seed = next(iter(sub))
    seen = {seed}; stack = [seed]
    while stack:
        u = stack.pop()
        for v in adj[u]:
            if v in sub and v not in seen:
                seen.add(v); stack.append(v)
    return len(seen) == len(sub)

REL_SINGLES = []   # (cell, V, region)
REL_GHOSTS = []    # (cells, V, region)
REL_EQS = {}       # frozenset(cell,sign) -> (W, region, src)

def add_rels(T, V, region):
    Ts = set(T)
    for cg in cages:
        cap = Ts & cage_cells[cg["id"]]
        if not cap:
            continue
        A = sorted(Ts - cap)
        B = sorted(cage_cells[cg["id"]] - Ts)
        if not A or not B:
            continue
        W = V - cg["sum"]
        na, nb = len(A), len(B)
        if not ((na + nb <= 3) or (min(na, nb) == 1 and max(na, nb) <= 3)):
            continue
        if nb < na:
            key = frozenset([(c, +1) for c in B] + [(c, -1) for c in A])
            val = (-W, region, cname(cg))
        else:
            key = frozenset([(c, +1) for c in A] + [(c, -1) for c in B])
            val = (W, region, cname(cg))
        REL_EQS.setdefault(key, val)

for k in range(1, 7):
    for sub in combinations(range(27), k):
        if k > 1 and not connected_subset(sub):
            continue
        U = set()
        for ui in sub:
            U |= unit_cells_map[ui]
        overlap = {}
        if len(U) < 9 * k:
            cnt = {}
            for ui in sub:
                for cell in unit_cells_map[ui]:
                    cnt[cell] = cnt.get(cell, 0) + 1
            overlap = {c: m for c, m in cnt.items() if m > 1}
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
        region = "+".join(unit_name_map[ui] for ui in sub)

        known, covered = 0, set()
        for cg in fully:
            ms = {overlap.get(c, 1) for c in cg["cells"]}
            if len(ms) == 1:
                known += ms.pop() * cg["sum"]
                covered |= set(cg["cells"])

        innies = sorted(c for c in U if c not in covered)
        if innies and all(overlap.get(c, 1) == 1 for c in innies):
            V = 45 * k - known
            if len(innies) == 1:
                REL_SINGLES.append((innies[0], V, region))
                add_rels(innies, V, region)
            elif 2 <= len(innies) <= 4:
                REL_GHOSTS.append((tuple(innies), V, region))
                add_rels(innies, V, region)
        if disjoint and crossing:
            outies = sorted(c for cg in crossing for c in cg["cells"] if c not in U)
            t = sum(cg["sum"] for cg in crossing) + sum(cg["sum"] for cg in fully)
            if 1 <= len(outies) <= 4:
                if len(outies) == 1:
                    REL_SINGLES.append((outies[0], t - 45 * k, region + "·外格"))
                else:
                    REL_GHOSTS.append((tuple(outies), t - 45 * k, region + "·外格"))
                add_rels(outies, t - 45 * k, region)

# 关系式去重（符号翻转视为同一条）
_eqs = {}
for key, (W, region, src) in sorted(REL_EQS.items()):
    k2 = frozenset((c, -s) for c, s in key)
    if sorted(k2) < sorted(key):
        key, W = k2, -W
    _eqs.setdefault(key, (W, region, src))
REL_EQS = _eqs
print(f"45关系库: 直接单格 {len(REL_SINGLES)} 条, 幽灵笼子 {len(REL_GHOSTS)} 条, 关系式 {len(REL_EQS)} 条\n")

def ghost_assignments(cells, V):
    """幽灵笼子合法赋值（按当前候选过滤，已定格子自动固定）"""
    n = len(cells)
    res = []
    def bt(i, cur):
        if i == n:
            if sum(cur) == V:
                res.append(tuple(cur))
            return
        for d in sorted(cands[cells[i]]):
            if all(cur[j] != d for j in range(i) if shares_unit(cells[j], cells[i])):
                cur.append(d); bt(i + 1, cur); cur.pop()
    bt(0, [])
    return res

def fmt_eq(pos, neg, W):
    if len(neg) <= len(pos):
        left, right, kk = neg, pos, -W
    else:
        left, right, kk = pos, neg, W
    l = "+".join(cell_name(c) for c in left)
    r = "+".join(cell_name(c) for c in right)
    if kk == 0:
        return f"{l} = {r}"
    return f"{l} = {r} {'+' if kk > 0 else '-'} {abs(kk)}"

# ---------------- 找下一步（按优先级） ----------------
def find_hidden_single():
    for name, cs in units:
        for d in range(1, 10):
            if any(grid.get(c) == d for c in cs):
                continue
            places = [c for c in cs if c not in grid and d in cands[c]]
            if len(places) == 1:
                return (places[0], d,
                        f"{name}里，数字{d}的候选只剩 {cell_name(places[0])} 这一个位置（隐性唯一）")
    return None

def find_cage_move():
    for cg in cages:
        unknown = [c for c in cg["cells"] if c not in grid]
        if not unknown:
            continue
        # 笼子只剩一格 → 余数
        if len(unknown) == 1:
            v = cg["sum"] - sum(grid[c] for c in cg["cells"] if c in grid)
            known_str = "+".join(str(grid[c]) for c in cg["cells"] if c in grid)
            if 1 <= v <= 9:
                return (unknown[0], v,
                        f"{cname(cg)}只剩 {cell_name(unknown[0])} 没填：{cg['sum']} − ({known_str}) = {v}")
        # 笼内隐性唯一（严谨版）：d 必须在【每一个】合法组合里都出现（d 必然进笼），
        # 且能放的位置只剩一格，才能落子。否则像"5 只在 {2,5} 组合里"这种情况会误落。
        valid = cage_valid_combos(cg)
        if not valid:
            continue
        for d in range(1, 10):
            if not all(d in set(cb) for cb in valid):
                continue
            places = [c for c in unknown if d in cands[c]]
            if len(places) == 1:
                return (places[0], d,
                        f"{cname(cg)}的每种合法组合都含数字{d}，而{d}只能放在 {cell_name(places[0])}（笼内隐性唯一）")
    return None

def find_rel_move():
    for key, (W, region, src) in REL_EQS.items():
        pos = [c for c, s in key if s > 0]
        neg = [c for c, s in key if s < 0]
        unk = [c for c in pos + neg if c not in grid]
        if len(unk) != 1:
            continue
        u = unk[0]
        if u in pos:
            v = W + sum(grid[c] for c in neg if c in grid) - sum(grid[c] for c in pos if c in grid and c != u)
        else:
            v = -W + sum(grid[c] for c in pos if c in grid) - sum(grid[c] for c in neg if c in grid and c != u)
        if 1 <= v <= 9:
            eq = fmt_eq(pos, neg, W)
            return (u, v, f"关系式 {eq}（来自{region}、{src}）里只剩 {cell_name(u)} 未知，代入已知数得 {v}")
    return None

def find_ghost_elim():
    for cells, V, region in REL_GHOSTS:
        if any(c in grid for c in cells):
            continue
        asg = ghost_assignments(cells, V)
        if not asg:
            continue
        for i, cell in enumerate(cells):
            allowed = set(a[i] for a in asg)
            new = cands[cell] & allowed
            if len(new) < len(cands[cell]) and new:
                keep = "".join(map(str, sorted(new)))
                return ("elim", cell, new,
                        f"幽灵笼子[{region}]: {cells_str(cells)} 这几格的和 = {V}（45法则推出），"
                        f"{cell_name(cell)} 在所有合法赋值里只能取 {{{keep}}}，候选砍掉其余")
    return None

def find_combo_elim():
    for cg in cages:
        valid = cage_valid_combos(cg)
        if len(valid) != 1:
            continue
        cb = valid[0]
        for cell in cg["cells"]:
            if cell in grid:
                continue
            allowed = set(d for d in set(cb) if d in cands[cell])
            if len(allowed) < len(cands[cell]) and allowed:
                keep = "".join(map(str, sorted(allowed)))
                return ("elim", cell, allowed,
                        f"{cname(cg)}只剩唯一组合 {list(cb)}，{cell_name(cell)} 只能取其中的数字，候选砍到 {{{keep}}}")
    return None

def find_pair_elim():
    # 显性数对：同一单元内两格候选完全相同且各2个 → 从其他格删（一次删完所有可删格）
    for name, cs in units:
        open_cells = [c for c in cs if c not in grid]
        for a, b in combinations(open_cells, 2):
            if len(cands[a]) == 2 and cands[a] == cands[b]:
                targets = [c for c in open_cells
                           if c not in (a, b) and (cands[c] - cands[a])
                           and len(cands[c] - cands[a]) < len(cands[c])]
                if targets:
                    ds = "".join(map(str, sorted(cands[a])))
                    return ("multi-elim", targets, set(cands[a]),
                            f"{name}里 {cell_name(a)} 和 {cell_name(b)} 构成数对{{{ds}}}（这两格只能是这俩数），"
                            f"{cells_str(targets)} 删掉候选中的 {ds}")
    return None

def find_pointing():
    # 指向: 宫内某数字候选全在同一行/列 → 该行/列在宫外的格子删它
    boxes = [(n, cs) for n, cs in units if n.endswith("宫")]
    for name, cs in boxes:
        for d in range(1, 10):
            places = [c for c in cs if c not in grid and d in cands[c]]
            if len(places) < 2:
                continue
            rows = set(c // 9 for c in places)
            cols = set(c % 9 for c in places)
            if len(rows) == 1:
                r = places[0] // 9
                targets = [c for c in range(9 * r, 9 * r + 9)
                           if c not in grid and c not in cs and d in cands[c]]
                if targets:
                    t = cells_str(targets)
                    return ("multi-elim", targets, {d},
                            f"{name}里数字{d}的候选全在第{r + 1}行（指向），第{r + 1}行宫外的 {t} 删掉{d}")
            if len(cols) == 1:
                c0 = places[0] % 9
                targets = [c for c in range(c0, 81, 9)
                           if c not in grid and c not in cs and d in cands[c]]
                if targets:
                    t = cells_str(targets)
                    return ("multi-elim", targets, {d},
                            f"{name}里数字{d}的候选全在第{c0 + 1}列（指向），第{c0 + 1}列宫外的 {t} 删掉{d}")
    # 反向(claiming): 行/列里某数字候选全在同一宫 → 宫内其他格删它
    for name, cs in units:
        if name.endswith("宫"):
            continue
        for d in range(1, 10):
            places = [c for c in cs if c not in grid and d in cands[c]]
            if len(places) < 2:
                continue
            box = set((c // 9 // 3, c % 9 // 3) for c in places)
            if len(box) == 1:
                br, bc = places[0] // 9 // 3, places[0] % 9 // 3
                box_cells = [rr * 9 + cc for rr in range(br * 3, br * 3 + 3)
                             for cc in range(bc * 3, bc * 3 + 3)]
                targets = [c for c in box_cells
                           if c not in grid and c not in cs and d in cands[c]]
                if targets:
                    t = cells_str(targets)
                    return ("multi-elim", targets, {d},
                            f"{name}里数字{d}的候选全在第{br * 3 + bc + 1}宫（区块），宫内 {t} 删掉{d}")
    return None

def find_hidden_pair():
    # 隐性数对: 同一单元内两个数字的候选位置完全相同且只有两格 → 这两格删其他候选
    for name, cs in units:
        open_cells = [c for c in cs if c not in grid]
        pos = {}
        for d in range(1, 10):
            ps = frozenset(c for c in open_cells if d in cands[c])
            if 2 <= len(ps) <= 4:
                pos.setdefault(ps, []).append(d)
        for ps, ds in pos.items():
            if len(ds) == 2 and len(ps) == 2:
                a, b = sorted(ps)
                extra = (cands[a] | cands[b]) - set(ds)
                if extra:
                    da, db = ds
                    return ("multi-elim", [a, b], set(extra),
                            f"{name}里数字{da}和{db}只能出现在 {cell_name(a)}、{cell_name(b)} 这两格（隐性数对{{{da}{db}}}），"
                            f"这两格删掉其他候选")
    return None

def find_linear_move():
    """线性消元定值：把笼子和、单位45、全部45关系式联立做高斯消元，
    解出只剩一个未知变量的格子。这是所有 45 法则类推理的完全体。"""
    from fractions import Fraction
    eqs = []
    for cg in cages:
        coef, rhs = {}, Fraction(cg["sum"])
        for c in cg["cells"]:
            if c in grid:
                rhs -= grid[c]
            else:
                coef[c] = coef.get(c, 0) + 1
        if coef:
            eqs.append((coef, rhs, cname(cg)))
    for name, cs in units:
        coef, rhs = {}, Fraction(45)
        for c in cs:
            if c in grid:
                rhs -= grid[c]
            else:
                coef[c] = 1
        if coef:
            eqs.append((coef, rhs, f"{name}格子和=45"))
    for key, (W, region, src) in REL_EQS.items():
        coef, rhs = {}, Fraction(W)
        for c, s in key:
            if c in grid:
                rhs -= s * grid[c]
            else:
                coef[c] = coef.get(c, 0) + s
        coef = {c: v for c, v in coef.items() if v != 0}
        if coef:
            pos = sorted(c for c, s in key if s > 0)
            neg = sorted(c for c, s in key if s < 0)
            eqs.append((coef, rhs, f"{fmt_eq(pos, neg, W)}({region})"))
    if os.environ.get("CHECK_EQS"):
        # 自检: 真值代入每条方程，残差必须为 0
        SOL = [[3,4,2,9,7,8,1,5,6],[1,7,6,3,2,5,4,9,8],[9,8,5,6,4,1,3,2,7],
               [2,3,8,7,6,9,5,1,4],[5,1,7,4,8,3,9,6,2],[6,9,4,5,1,2,8,7,3],
               [8,5,1,2,3,6,7,4,9],[7,6,9,8,5,4,2,3,1],[4,2,3,1,9,7,6,8,5]]
        bad = 0
        for coef, rhs, label in eqs:
            resid = Fraction(rhs)
            for c, f in coef.items():
                rr, cc = divmod(c, 9)
                resid -= f * SOL[rr][cc]
            if resid != 0:
                bad += 1
                print(f"!! 方程违背真值: {label}")
                print(f"   残差 = {resid}")
                print(f"   内容: " + " + ".join(f"{f}·{cell_name(c)}" for c, f in sorted(coef.items())) + f" = {rhs}")
        print(f"[方程自检] {len(eqs)} 条方程，违背真值 {bad} 条")
        if bad:
            sys.exit(0)
    # 高斯消元（池式：每列选一条主元方程，其余方程全部减去倍数消去该列；
    # 主元方程留在池里继续参与后续列的消元，最终每条方程只剩少量变量）
    rows = []
    for coef, rhs, label in eqs:
        rows.append([{c: Fraction(v) for c, v in coef.items()}, Fraction(rhs), [label]])
    for col in range(81):
        pivot = None
        for e in rows:
            if e[0].get(col):
                pivot = e
                break
        if pivot is None:
            continue
        pc, prhs, plab = pivot
        f = pc[col]
        pivot[0] = {k: v / f for k, v in pc.items()}
        pivot[1] = prhs / f
        pc, prhs = pivot[0], pivot[1]
        for e in rows:
            if e is pivot or not e[0].get(col):
                continue
            f2 = e[0][col]
            # 关键: 要遍历两边的并集——主元方程里有、当前方程里没有的变量
            # 必须以 -f2*系数 引入，否则变量凭空蒸发、方程被摧毁
            newc = dict(e[0])
            for k, v in pc.items():
                newc[k] = newc.get(k, 0) - f2 * v
            e[0] = {k: v for k, v in newc.items() if v != 0}
            e[1] = e[1] - f2 * prhs
            for lb in plab:
                if lb not in e[2]:
                    e[2].append(lb)
        if os.environ.get("CHECK_EQS"):
            SOL = [[3,4,2,9,7,8,1,5,6],[1,7,6,3,2,5,4,9,8],[9,8,5,6,4,1,3,2,7],
                   [2,3,8,7,6,9,5,1,4],[5,1,7,4,8,3,9,6,2],[6,9,4,5,1,2,8,7,3],
                   [8,5,1,2,3,6,7,4,9],[7,6,9,8,5,4,2,3,1],[4,2,3,1,9,7,6,8,5]]
            for coef, rhs, labels in rows:
                resid = Fraction(rhs)
                for c, f in coef.items():
                    rr, cc = divmod(c, 9)
                    resid -= f * SOL[rr][cc]
                if resid != 0:
                    print(f"!! 第一现场: 处理列 {col}（{cell_name(col)}）后出现违背行")
                    print(f"   主元方程: {'、'.join(plab)}")
                    print(f"   违背行来源: {'、'.join(labels[:8])}")
                    print(f"   违背行: " + " + ".join(f"{f}·{cell_name(c)}" for c, f in sorted(coef.items())) + f" = {rhs}")
                    print(f"   主元方程规格化后: " + " + ".join(f"{f}·{cell_name(c)}" for c, f in sorted(pc.items())) + f" = {prhs}")
                    sys.exit(0)
    if os.environ.get("CHECK_EQS"):
        SOL = [[3,4,2,9,7,8,1,5,6],[1,7,6,3,2,5,4,9,8],[9,8,5,6,4,1,3,2,7],
               [2,3,8,7,6,9,5,1,4],[5,1,7,4,8,3,9,6,2],[6,9,4,5,1,2,8,7,3],
               [8,5,1,2,3,6,7,4,9],[7,6,9,8,5,4,2,3,1],[4,2,3,1,9,7,6,8,5]]
        bad = 0
        for coef, rhs, labels in rows:
            resid = Fraction(rhs)
            for c, f in coef.items():
                rr, cc = divmod(c, 9)
                resid -= f * SOL[rr][cc]
            if resid != 0:
                bad += 1
                if bad <= 3:
                    print(f"!! 消元后行违背真值: 残差={resid}")
                    print(f"   来源: {'、'.join(labels[:8])}")
                    print(f"   行: " + " + ".join(f"{f}·{cell_name(c)}" for c, f in sorted(coef.items())) + f" = {rhs}")
        print(f"[消元自检] {len(rows)} 行，违背真值 {bad} 行")
        sys.exit(0)
    for coef, rhs, labels in rows:
        if len(coef) == 1:
            (c, f), = coef.items()
            if c in grid:
                continue
            v = rhs / f
            if v.denominator != 1 or not (1 <= v <= 9):
                continue
            v = int(v)
            if v not in cands[c]:
                lab = "、".join(labels[:6])
                print(f"!! 线性消元与候选冲突: {cell_name(c)} = {v} 不在候选 {sorted(cands[c])}")
                print(f"   来源方程: {lab}")
                print(f"   该行方程: " + " + ".join(f"{float(fv):g}·{cell_name(cc)}" for cc, fv in sorted(coef.items())) + f" = {float(rhs):g}")
                continue
            lab = "、".join(labels[:4]) + ("等" if len(labels) > 4 else "")
            return (c, v, f"把 {lab} 这几条式子联立消元，解出 {cell_name(c)} = {v}")
    return None

# ---------------- 反证法（假设某格=某数，确定性推进，矛盾则排除） ----------------
QUIET = False
def log(desc, typ):
    if not QUIET:
        steps.append((desc, typ))

def solve_det():
    """在当前全局状态上做确定性推进（elim 招 + 落子招循环），静默不记步骤。
    返回 'contradiction' / 'solved' / 'stuck'"""
    while len(grid) < 81:
        while True:
            step = None
            for fn in ELIM_FUNCS:
                step = fn()
                if step:
                    break
            if step is None:
                break
            if not apply_elim(step):
                continue
            if not propagate():
                return "contradiction"
        r = find_hidden_single() or find_cage_move() or find_rel_move() or find_linear_move()
        if r is None:
            step = None
            for fn in ELIM_FUNCS:
                step = fn()
                if step:
                    break
            if step is None:
                return "stuck"
            apply_elim(step)
            if not propagate():
                return "contradiction"
            continue
        cell, v, why = r
        grid[cell] = v
        cands[cell] = {v}
        if not propagate():
            return "contradiction"
    return "solved"

def find_contradiction():
    global grid, cands, QUIET
    open_cells = sorted([c for c in cands if c not in grid],
                        key=lambda c: (len(cands[c]), c))
    for cell in open_cells:
        for v in sorted(cands[cell]):
            snap_g = dict(grid)
            snap_c = {c: set(s) for c, s in cands.items()}
            n_steps = len(steps)
            grid[cell] = v
            cands[cell] = {v}
            ok = propagate()
            result = solve_det() if ok else "contradiction"
            grid = snap_g
            cands = snap_c
            del steps[n_steps:]
            if result == "contradiction":
                return ("elim", cell, cands[cell] - {v},
                        f"反证: 假设 {cell_name(cell)} = {v}，用全部确定性招往下推，必然自相矛盾"
                        f"（推不动还出错），所以 {cell_name(cell)} ≠ {v}")
            if result == "solved":
                # 假设分支解出了完整合法盘 —— 题目唯一解时这就是真值
                return ("place", cell, v,
                        f"反证: 只有假设 {cell_name(cell)} = {v} 能推到完整合法解（其他候选全部矛盾），故填 {v}")
    return None

def find_step():
    r = find_hidden_single()
    if r: return ("place",) + r
    r = find_cage_move()
    if r: return ("place",) + r
    r = find_rel_move()
    if r: return ("place",) + r
    r = find_ghost_elim()
    if r: return r
    r = find_combo_elim()
    if r: return r
    r = find_pair_elim()
    if r: return r
    return None

# ---------------- 主循环 ----------------
# 关键顺序: 每一轮先把所有"删候选"的招全部用完（候选收敛后才不会误判落子），再落子。
ELIM_FUNCS = (find_ghost_elim, find_combo_elim, find_pair_elim,
              find_pointing, find_hidden_pair)

def apply_elim(step):
    if step[0] == "multi-elim":
        _, targets, rem, why = step
        parts = []
        for cell in targets:
            old = cands[cell]
            new = old - rem
            if len(new) < len(old) and new:
                cands[cell] = set(new)
                parts.append(f"{cell_name(cell)}去掉{{{''.join(map(str, sorted(old - new)))}}}")
        if parts:
            log(f"删候选: {'、'.join(parts)} —— {why}", "elim")
        return bool(parts)
    else:
        _, cell, new, why = step
        old = cands[cell]
        cands[cell] = set(new)
        removed = "".join(map(str, sorted(old - new)))
        log(f"删候选: {cell_name(cell)} 去掉 {{{removed}}} —— {why}", "elim")
        return True

print("开始求解……\n")
stall = False
while len(grid) < 81:
    # 阶段1: 删候选类招数轮转，直到一个不剩
    while True:
        step = None
        for fn in ELIM_FUNCS:
            step = fn()
            if step:
                break
        if step is None:
            break
        if not apply_elim(step):
            continue
        if not propagate():
            print("!! 传播出现矛盾，停止"); stall = True; break
    if stall or len(grid) == 81:
        break
    # 阶段2: 落子类招数
    r = find_hidden_single() or find_cage_move() or find_rel_move() or find_linear_move()
    if r is None:
        # 落子招没有 → 回头再试删候选（传播后可能有新的）
        step = None
        for fn in ELIM_FUNCS:
            step = fn()
            if step:
                break
        if step is None:
            # 最后的硬家伙: 反证法
            r = find_contradiction()
            if r is None:
                stall = True
                break
            if r[0] == "place":
                cell, v, why = r
                grid[cell] = v
                cands[cell] = {v}
                log(f"在 {cell_name(cell)} 填 {v} —— {why}", "place")
                if not propagate():
                    print("!! 传播出现矛盾，停止"); stall = True; break
                continue
            apply_elim(r)
            if not propagate():
                print("!! 传播出现矛盾，停止"); stall = True; break
            continue
        apply_elim(step)
        if not propagate():
            print("!! 传播出现矛盾，停止"); stall = True; break
        continue
    cell, v, why = r
    grid[cell] = v
    cands[cell] = {v}
    log(f"在 {cell_name(cell)} 填 {v} —— {why}", "place")
    if not propagate():
        print("!! 传播出现矛盾，停止"); stall = True; break

# ---------------- 输出 ----------------
def verify():
    for name, cs in units:
        vals = [grid[c] for c in cs]
        if sorted(vals) != list(range(1, 10)):
            return False
    for cg in cages:
        if sum(grid[c] for c in cg["cells"]) != cg["sum"]:
            return False
        if len(set(grid[c] for c in cg["cells"])) != len(cg["cells"]):
            return False
    return True

print("=" * 62)
n_place = sum(1 for _, t in steps if t == "place")
print(f"步骤单（共 {len(steps)} 步，其中落子 {n_place} 步）")
print("=" * 62)
for i, (desc, typ) in enumerate(steps, 1):
    mark = "★" if typ == "place" else ("·" if typ == "chain" else "◇")
    print(f"{mark} 第{i:>2}步  {desc}")

print("=" * 62)
if stall and len(grid) < 81:
    print("DEBUG: 卡住后再跑一次 propagate……")
    r2 = propagate()
    n2 = sum(1 for _, t in steps if t == "chain")
    print(f"DEBUG: propagate 返回 {r2}，现在已定 {len(grid)}/81，新增连锁 {sum(1 for _, t in steps if t == 'chain') - (len(steps) - sum(1 for _, t in steps if t == 'chain')) if False else ''}")
    print(f"!! 卡住：已定 {len(grid)}/81 格。卡点附近候选最少的格子：")
    open_cells = [c for c in sorted(cands) if c not in grid]
    for cell in sorted(open_cells, key=lambda c: len(cands[c]))[:8]:
        print(f"   {cell_name(cell)}: {sorted(cands[cell])}")
elif len(grid) == 81:
    ok = verify()
    print(f"解完！81/81 格，行/列/宫/笼子全检: {'通过' if ok else '不通过'}")
    print("\n解盘:")
    for r in range(9):
        print("  " + " ".join(str(grid[r * 9 + c]) for c in range(9)))

# 步骤单存档
out = os.path.splitext(path)[0] + "_steps.txt"
with open(out, "w", encoding="utf-8") as f:
    for i, (desc, typ) in enumerate(steps, 1):
        mark = "★" if typ == "place" else ("·" if typ == "chain" else "◇")
        f.write(f"{mark} 第{i:>2}步  {desc}\n")
    if len(grid) == 81 and verify():
        f.write("\n解盘:\n")
        for r in range(9):
            f.write("  " + " ".join(str(grid[r * 9 + c]) for c in range(9)) + "\n")
print(f"\n步骤单已存: {out}")

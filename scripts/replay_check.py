# -*- coding: utf-8 -*-
"""通用重放裁判：解出题目真解，逐行核对 human_solve.py 的步骤单，
找出第一个与真解矛盾的步骤（落子错 / 删候选删掉真值）。

用法: python replay_check.py <题目.json> <步骤单.txt>
"""
import json
import re
import sys
from itertools import combinations

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def solve(puzzle):
    """MRV 回溯求解杀手数独，返回 9x9 解或 None。"""
    cages = []
    for cg in puzzle["cages"]:
        cages.append((set((r, c) for r, c in cg["cells"]), cg["sum"]))
    cage_of = {}
    for i, (cells, _) in enumerate(cages):
        for cell in cells:
            cage_of[cell] = i

    cands = {}
    for r in range(9):
        for c in range(9):
            cands[(r, c)] = set(range(1, 10))
    for cells, s in cages:
        combos = [cb for cb in combinations(range(1, 10), len(cells)) if sum(cb) == s]
        if not combos:
            return None
        pool = set(d for cb in combos for d in cb)
        for cell in cells:
            cands[cell] &= pool

    peers = {}
    for r in range(9):
        for c in range(9):
            ps = set()
            for k in range(9):
                ps.add((r, k)); ps.add((k, c))
            br, bc = r // 3 * 3, c // 3 * 3
            for dr in range(3):
                for dc in range(3):
                    ps.add((br + dr, bc + dc))
            ps.discard((r, c))
            peers[(r, c)] = ps

    def assign(cand, cell, v):
        cand[cell] = {v}
        queue = [cell]
        while queue:
            cc = queue.pop()
            if not cand[cc]:
                return False
            if len(cand[cc]) == 1:
                vv = next(iter(cand[cc]))
                for p in peers[cc]:
                    if vv in cand[p]:
                        cand[p] = cand[p] - {vv}
                        if len(cand[p]) == 0:
                            return False
                        queue.append(p)
        return True

    # 笼子约束传播：候选并集 / 唯一组合的数字并集
    def cage_propagate(cand):
        changed = True
        while changed:
            changed = False
            for cells, s in cages:
                unknown = [c for c in cells if len(cand[c]) > 1]
                fixed = sum(next(iter(cand[c])) for c in cells if len(cand[c]) == 1)
                if len(unknown) == 1:
                    v = s - fixed
                    if v not in cand[unknown[0]]:
                        return False
                    if len(cand[unknown[0]]) != 1:
                        cand[unknown[0]] = {v}
                        changed = True
                    continue
                ok = []
                for cb in combinations(range(1, 10), len(unknown)):
                    if sum(cb) != s - fixed:
                        continue
                    # 二分匹配：组合数字能不重复地分配给未知格
                    used = set()
                    def bt(i):
                        if i == len(unknown):
                            return True
                        for d in cb:
                            if d not in used and d in cand[unknown[i]]:
                                used.add(d)
                                if bt(i + 1):
                                    return True
                                used.discard(d)
                        return False
                    if bt(0):
                        ok.append(cb)
                if not ok:
                    return False
                pool = set(d for cb in ok for d in cb)
                for c in unknown:
                    new = cand[c] & pool
                    if new != cand[c]:
                        if not new:
                            return False
                        cand[c] = new
                        changed = True
        return True

    def search(cand):
        if not cage_propagate(cand):
            return None
        unsolved = [c for c in cands if len(cand[c]) > 1]
        if not unsolved:
            return cand
        cell = min(unsolved, key=lambda c: len(cand[c]))
        for v in sorted(cand[cell]):
            trial = {c: set(s) for c, s in cand.items()}
            if assign(trial, cell, v):
                res = search(trial)
                if res:
                    return res
        return None

    result = search(cands)
    if not result:
        return None
    grid = [[0] * 9 for _ in range(9)]
    for (r, c), s in result.items():
        grid[r][c] = next(iter(s))
    return grid


def check_solution(grid, cages):
    for i in range(9):
        if sorted(grid[i]) != list(range(1, 10)):
            return False
        if sorted(grid[r][i] for r in range(9)) != list(range(1, 10)):
            return False
    for br in range(3):
        for bc in range(3):
            vals = [grid[br * 3 + dr][bc * 3 + dc] for dr in range(3) for dc in range(3)]
            if sorted(vals) != list(range(1, 10)):
                return False
    for cells, s in cages:
        if sum(grid[r][c] for r, c in cells) != s:
            return False
        if len(set(grid[r][c] for r, c in cells)) != len(cells):
            return False
    return True


def main():
    if len(sys.argv) != 3:
        print("用法: python replay_check.py <题目.json> <步骤单.txt>")
        sys.exit(1)
    with open(sys.argv[1], encoding="utf-8") as f:
        puzzle = json.load(f)
    cages = [ (set((r, c) for r, c in cg["cells"]), cg["sum"]) for cg in puzzle["cages"] ]
    sol = solve(puzzle)
    if sol is None:
        print("!! 题目无解或求解失败，无法对账")
        sys.exit(2)
    if not check_solution(sol, cages):
        print("!! 求出的解未通过合法性校验，无法对账")
        sys.exit(2)

    with open(sys.argv[2], encoding="utf-8") as f:
        lines = [ln.rstrip("\n") for ln in f if ln.strip() and ln.startswith(("★", "·", "◇"))]

    def sol_at(r, c):
        return sol[r - 1][c - 1]

    cell_re = re.compile(r"(\d)行(\d)列")
    bad = 0
    for ln in lines:
        m = re.match(r"(.{1}) 第\s*(\d+)步\s*(.*)", ln)
        if not m:
            continue
        mark, num, desc = m.group(1), int(m.group(2)), m.group(3)
        kind = "place" if mark == "★" else ("chain" if mark == "·" else "elim")
        head = desc.split("——")[0]
        if kind in ("place", "chain"):
            mc = re.search(r"(\d)行(\d)列 = (\d)", head)
            if not mc:
                continue
            r, c, v = int(mc.group(1)), int(mc.group(2)), int(mc.group(3))
            truth = sol_at(r, c)
            if truth != v:
                print(f"[落子错误] 第{num}步: {desc}")
                print(f"          真值: {r}行{c}列 = {truth}")
                bad += 1
                if bad >= 3:
                    break
        else:
            # 单格删候选 或 多格隐性数对(multi-elim)
            if head.startswith("删候选:"):
                mc = re.match(r"删候选: (\d)行(\d)列 去掉 \{([\d]*)\}", head)
                if not mc:
                    continue
                r, c = int(mc.group(1)), int(mc.group(2))
                removed = set(int(d) for d in mc.group(3))
                if sol_at(r, c) in removed:
                    print(f"[删候选错误] 第{num}步: {desc}")
                    print(f"          真值: {r}行{c}列 = {sol_at(r, c)}，真值被删掉了！")
                    bad += 1
                    if bad >= 5:
                        break
    if bad == 0:
        total = sum(1 for ln in lines if re.match(r"[★·◇] 第\s*\d+步", ln))
        print(f"重放完毕：{total} 步全部与唯一解一致，0 错误。")


if __name__ == "__main__":
    main()

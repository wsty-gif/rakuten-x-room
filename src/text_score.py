"""商品画像が「文字だらけの宣伝バナー」かどうかを数値化する（numpy のみ）。

考え方: 文字は「同じ高さの小さな部品が、横一列（または縦一列）に4個以上並ぶ」。
暗い画素・明るい画素・彩度の高い画素・背景と差の大きい画素のそれぞれで連結成分を取り、
行/列に並ぶ部品の数を足す。目安: 20 以下 = 物の写真、25 以上 = 文字バナー。
"""
from __future__ import annotations

import numpy as np
from PIL import Image

S = 448


def _components(mask: np.ndarray):
    """ランレングス＋Union-Find で 8連結の成分を求め、(y0, y1, x0, x1, area) の一覧を返す。"""
    H, W = mask.shape
    parent: list[int] = []
    runs_by_row: list[list[tuple[int, int, int]]] = []

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for y in range(H):
        row = mask[y]
        runs = []
        idx = np.flatnonzero(np.diff(np.concatenate(([0], row.astype(np.int8), [0]))))
        for x0, x1 in zip(idx[::2], idx[1::2]):
            lab = len(parent)
            parent.append(lab)
            runs.append((int(x0), int(x1), lab))
        if y > 0:
            for x0, x1, lab in runs:
                for px0, px1, plab in runs_by_row[y - 1]:
                    if px0 <= x1 and x0 <= px1:
                        union(lab, plab)
        runs_by_row.append(runs)
    stats: dict[int, list[int]] = {}
    for y, runs in enumerate(runs_by_row):
        for x0, x1, lab in runs:
            r = find(lab)
            s = stats.setdefault(r, [y, y, x0, x1, 0])
            s[0] = min(s[0], y); s[1] = max(s[1], y); s[2] = min(s[2], x0); s[3] = max(s[3], x1); s[4] += x1 - x0
    return list(stats.values())


def glyphs(mask: np.ndarray):
    out = []
    for y0, y1, x0, x1, area in _components(mask):
        h, w = y1 - y0 + 1, x1 - x0
        if 5 <= h <= 140 and 2 <= w <= 300 and area >= 8:
            fill = area / (w * h)
            max_aspect = 12 if h <= 56 else 6
            if 0.10 <= fill <= 0.95 and 0.1 <= w / h <= max_aspect:
                out.append((y0, y1, x0, x1))
    return out


def aligned_groups(boxes) -> list[list[tuple[int, int, int, int]]]:
    """同じ行（中心yが近く、高さが近い）に 4 個以上並ぶ部品のグループ＝文字行。"""
    if len(boxes) < 4:
        return []
    groups: list[list[tuple[int, int, int, int]]] = []
    boxes = sorted(boxes, key=lambda b: (b[0] + b[1]) / 2)
    used = [False] * len(boxes)
    for i, b in enumerate(boxes):
        if used[i]:
            continue
        cy, h = (b[0] + b[1]) / 2, b[1] - b[0] + 1
        group = [j for j, c in enumerate(boxes) if not used[j] and abs((c[0] + c[1]) / 2 - cy) <= max(3, h * 0.35)
                 and 0.6 <= (c[1] - c[0] + 1) / h <= 1.6]
        if len(group) >= 4:
            # 横に並んでいる（x が重ならず、間隔が高さの3倍以内）
            xs = sorted((boxes[j][2], boxes[j][3]) for j in group)
            chain = 1
            best = 1
            for (a0, a1), (b0, b1) in zip(xs, xs[1:]):
                if 0 <= b0 - a1 <= h * 3:
                    chain += 1
                else:
                    chain = 1
                best = max(best, chain)
            if best >= 4:
                groups.append([boxes[j] for j in group])
                for j in group:
                    used[j] = True
    return groups


def aligned_count(boxes) -> int:
    return sum(len(g) for g in aligned_groups(boxes))


def _transpose(boxes):
    return [(x0, x1, y0, y1) for (y0, y1, x0, x1) in boxes]


def lines_count(boxes) -> int:
    """横書きの行と縦書きの列、どちらも数える。"""
    return aligned_count(boxes) + aligned_count(_transpose(boxes))


def text_score(img: Image.Image) -> float:
    im = img.convert("RGB").resize((S, S))
    a = np.asarray(im).astype(np.int32)
    L = (a[..., 0] * 299 + a[..., 1] * 587 + a[..., 2] * 114) // 1000
    dark = L < 100
    light = L > 225
    sat = (a.max(axis=2) - a.min(axis=2)) > 80
    med = int(np.median(L))
    contrast = np.abs(L - med) > 70
    return (lines_count(glyphs(dark)) + lines_count(glyphs(light)) + 0.7 * lines_count(glyphs(sat & (L > 50)))
            + 0.7 * lines_count(glyphs(contrast)))


def _masks(img: Image.Image):
    im = img.convert("RGB").resize((S, S))
    a = np.asarray(im).astype(np.int32)
    L = (a[..., 0] * 299 + a[..., 1] * 587 + a[..., 2] * 114) // 1000
    med = int(np.median(L))
    return [L < 100, L > 225, np.abs(L - med) > 70]


def photo_band(img: Image.Image) -> tuple[float, float]:
    """横書きの文字行を除いた、いちばん高い「写真だけの帯」を (上端, 下端) の割合で返す。
    文字が無ければ (0.0, 1.0)。商品画像の下に説明文が付いている合成画像を切り落とすのに使う。"""
    text_rows = np.zeros(S, dtype=bool)
    for m in _masks(img):
        for g in aligned_groups(glyphs(m)):
            y0 = max(0, min(b[0] for b in g) - 3)
            y1 = min(S, max(b[1] for b in g) + 4)
            text_rows[y0:y1] = True
    best, cur_start, best_span = (0, S), 0, 0
    for y in range(S + 1):
        if y == S or text_rows[y]:
            if y - cur_start > best_span:
                best_span, best = y - cur_start, (cur_start, y)
            cur_start = y + 1
    y0, y1 = best
    a = np.asarray(img.convert("RGB").resize((S, S))).astype(np.int32)
    if y0 > 0 and not _caption_like(a[:y0]):
        y0 = 0
    if y1 < S and not _caption_like(a[y1:]):
        y1 = S
    return y0 / S, y1 / S


def _caption_like(region: np.ndarray) -> bool:
    """帯が「無地の背景＋小さな文字」だけかどうか。大きな物体があれば False。"""
    if region.shape[0] < 4:
        return True
    med = np.median(region.reshape(-1, 3), axis=0)
    nonbg = (np.abs(region - med).max(axis=2) > 34)
    if nonbg.mean() > 0.45:
        return False
    limit_h, limit_area = 0.22 * S, 0.03 * S * S
    for y0, y1, x0, x1, area in _components(nonbg):
        if (y1 - y0 + 1) > limit_h or area > limit_area:
            return False
    return True

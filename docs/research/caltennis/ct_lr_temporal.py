"""短缺口參考：ct_lr_temporal.py <參考 npz 目錄> <原正式輸出目錄> <新輸出目錄>。"""
from pathlib import Path
import json
import sys
import warnings
import numpy as np

sys.path[:0] = [str(Path(__file__).resolve().parent), str(Path(__file__).resolve().parents[3] / "tools")]
from ct_lr import SW, SUPPORT, JOINTS, UP, orientation, triangulate, label_pose
from ct_tri import proj, interp, clock
from proxy import map_pose


def bridge(X, state, geometry):
    out = state.copy()
    torso = np.array([[11, 12], [23, 24]])
    a, b = X[:-1, torso], X[1:, torso]
    own = np.linalg.norm(b - a, axis=3).sum(2)
    other = np.linalg.norm(b[:, :, ::-1] - a, axis=3).sum(2)
    same, swap = (own < .5 * other).all(1), (other < .5 * own).all(1)
    matched = b.copy(); matched[swap] = matched[swap, :, ::-1]
    edge = (same | swap) & (np.linalg.norm(matched - a, axis=3) <= .08).all((1, 2))
    v, w = a[:, :, 1, :2] - a[:, :, 0, :2], matched[:, :, 1, :2] - matched[:, :, 0, :2]
    cosine = np.sum(v * w, axis=2) / (np.linalg.norm(v, axis=2) * np.linalg.norm(w, axis=2))
    edge &= (cosine >= np.cos(np.radians(10))).all(1)
    # 面向有強證據時仍須尊重；時間連續性不能掩蓋鼻、腳與肩髖矛盾。
    signs, evidence = [], []
    nose = X[:, 0] - X[:, [11, 12]].mean(1)
    foot = X[:, [31, 32]].mean(1) - X[:, [29, 30]].mean(1)
    for fw, minimum in ((nose, .03), (foot, .05)):
        fw = fw.copy(); fw[:, 2] = 0
        right = np.cross(fw, UP)
        for l, r in torso:
            line = X[:, r] - X[:, l]; line[:, 2] = 0
            score = np.sum(line * right, axis=1) / (np.linalg.norm(line, axis=1) * np.linalg.norm(right, axis=1))
            signs.append(score < 0)
            evidence.append((np.linalg.norm(fw, axis=1) >= minimum) & (abs(score) >= .2))
    anchors = np.flatnonzero(state >= 0)
    for left, right in zip(anchors[:-1], anchors[1:]):
        if not 1 <= right - left - 1 <= 12: continue
        if not geometry[left:right + 1].all() or not edge[left:right].all(): continue
        expected = np.r_[state[left], state[left] ^ np.bitwise_xor.accumulate(swap[left:right])].astype(np.int8)
        if expected[-1] != state[right]: continue
        conflict = any((ev[left:right + 1] & (sg[left:right + 1] != expected)).any() for ev, sg in zip(evidence, signs))
        if not conflict: out[left + 1:right] = expected[1:-1]
    return out


def main():
    if len(sys.argv) != 4:
        sys.exit("用法：ct_lr_temporal.py <參考 npz 目錄> <原正式輸出目錄> <新輸出目錄>")
    refdir, olddir, dest = map(Path, sys.argv[1:])
    dest.mkdir(parents=True, exist_ok=False)
    poses = {a: dict(np.load(refdir / f'c{a}.npz')) for a in range(1, 5)}
    report = []
    for a, b in ((1, 3), (2, 4), (3, 1), (4, 2)):
        Pa, _ = proj(a); Pb, _ = proj(b)
        A, B = poses[a], poses[b]
        P = np.load(olddir / f'c{a}/pose.npy')
        assert np.array_equal(A['t'], np.load(olddir / f'c{a}/t.npy'))
        observed = map_pose(P, 1920, 1088, inverse=True)[..., :2] * (1920, 1088)
        labels, states, diagnostics, geometries = [], [], [], []
        for offset in (-1, 0, 1):
            cache = dest / f'c{a}_raw_{offset}.npz'
            ub = interp(clock(a, A) + offset / 60, clock(b, B), B['lm'])[..., :2]
            X, err, _, margin = triangulate(Pa, Pb, A['lm'][..., :2], ub)
            np.savez(cache, X=X, err=err, margin=margin)
            geometry = np.isfinite(X[:, JOINTS]).all((1, 2)) & (err[:, JOINTS] <= 20).all(1)
            geometry &= (np.median(err[:, SUPPORT], axis=1) <= 10) & (margin >= 1)
            length = np.linalg.norm(X[:, [11, 12]].mean(1) - X[:, [23, 24]].mean(1), axis=1)
            geometry &= (length >= .15) & (length <= 1)
            for l, r in ((11, 12), (23, 24)):
                width = np.linalg.norm(X[:, r] - X[:, l], axis=1)
                geometry &= (width >= .08) & (width <= .8)
            for p in (Pa, Pb):
                depth = X[:, SUPPORT] @ p[2, :3] + p[2, 3]
                geometry &= (depth > 0).all(1)
            geometries.append(geometry)
            original = orientation(X, err); original[~geometry] = -1
            old = dict(np.load(olddir / f'c{a}/reference_{offset}.npz'))
            assert np.array_equal(original, old['state']), '未重現舊參考'
            state = bridge(X, original, geometry)
            assert (state[original >= 0] == original[original >= 0]).all()
            # 留掉嚴格錨點的短段，只核對恢復方向，不當成獨立真值。
            masked = original.copy(); masked[np.arange(len(masked)) % 20 < 7] = -1
            recovered = bridge(X, masked, geometry)
            check = (original >= 0) & (masked < 0) & (recovered >= 0)
            mismatch = int((recovered[check] != original[check]).sum())
            assert mismatch == 0, '錨點留出核對方向不一致'
            canonical = X.copy(); canonical[state == 1] = X[state == 1][:, SW]
            uvw = canonical @ Pa[:, :3].T + Pa[:, 3]
            uv = uvw[..., :2] / uvw[..., 2:]
            label = label_pose(observed, uv)
            labels.append(label); states.append(state)
            diagnostics.append(dict(offset=offset, geometry=int(geometry.sum()), strict=int((original >= 0).sum()),
                                    bridged=int(((original < 0) & (state >= 0)).sum()),
                                    withheld_recovered=int(check.sum()), withheld_mismatch=mismatch))
            print(a, diagnostics[-1], flush=True)
        labels, states = np.array(labels), np.array(states)
        stable = (states >= 0).all(0) & (labels >= 0).all(0) & (labels == labels[1]).all(0)
        truth = np.where(stable, labels[1], -1).astype(np.int8)
        oldtruth = np.load(olddir / f'c{a}/truth.npz')['truth']
        assert (truth[oldtruth >= 0] == oldtruth[oldtruth >= 0]).all(), '原嚴格標籤退步'
        np.savez(dest / f'c{a}_truth.npz', truth=truth, states=states, labels=labels)
        row = dict(cam=a, frames=len(P), previous_known=int((oldtruth >= 0).sum()), known=int(stable.sum()),
                   unknown=int((~stable).sum()), swapped=int((truth == 1).sum()),
                   added=int(((oldtruth < 0) & stable).sum()), old_changed=int((truth[oldtruth >= 0] != oldtruth[oldtruth >= 0]).sum()),
                   geometry_all_offsets=int(np.array(geometries).all(0).sum()),
                   reference_all_offsets=int((states >= 0).all(0).sum()), diagnostics=diagnostics)
        report.append(row)
        (dest / 'summary.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(json.dumps(row, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', RuntimeWarning)
        main()

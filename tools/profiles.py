# 場次級 profiles：work/<s>/profiles.json 優先，沒列的名字逐名字回退全域 work/profiles.json（common.load_profiles 的檔）。
from common import ROOT, load


def load_session_profiles(s, root=ROOT):
    """-> (profiles, where): {name: raw profile}, {name: 'work/<s>/profiles.json' | 'work/profiles.json'}.
    Same name in both files: the session file wins. A file that is not a JSON object raises ValueError (never read as 'no profile' = R)."""
    P, where = {}, {}
    for rel in ([f"work/{s}/profiles.json"] if s else []) + ["work/profiles.json"]:
        try: d = load(root / rel, {})
        except ValueError as e: raise ValueError(f"{rel}: {e}") from e
        if not isinstance(d, dict): raise ValueError(f"{rel} must be a JSON object {{name: {{hand, backhand}}}}, got {type(d).__name__}")
        for n, p in d.items():
            if n not in P: P[n], where[n] = p, rel
    return P, where

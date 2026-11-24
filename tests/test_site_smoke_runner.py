"""驗證背景播放測試只在明確開啟時執行，不啟動瀏覽器。"""
from contextlib import redirect_stdout
import io
import os
from pathlib import Path
import runpy
import subprocess
from unittest.mock import patch

runner = Path(__file__).with_name("test_site_smoke.py")
background = str(runner.resolve().with_name("site_cache_playing_background.mjs"))
run = subprocess.run

for enabled in (False, True):
    calls = []

    def record(command, *args, **kwargs):
        if command[0] != "node":
            return run(command, *args, **kwargs)
        calls.append(command)
        return subprocess.CompletedProcess(command, 0)

    with patch.dict(os.environ, {"SITE_E2E_URL": "http://fixture.invalid", "SITE_REF": "HEAD"}):
        os.environ.pop("SITE_RESULTS", None)
        os.environ.pop("SITE_SERVER_LOG", None)
        os.environ.pop("SITE_PLAYING_BACKGROUND", None)
        if enabled:
            os.environ["SITE_PLAYING_BACKGROUND"] = "1"
        with patch.object(subprocess, "run", side_effect=record), redirect_stdout(io.StringIO()) as output:
            runpy.run_path(str(runner))
    assert "skipped site_card_medians.mjs" in output.getvalue()
    assert calls.count(["node", background]) == int(enabled), enabled

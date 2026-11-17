"""研究入口的時間與釋鎖失敗路徑；只用臨時檔案，不執行姿態。"""
import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'docs/research/caltennis'))
import ct_world_run as run

with tempfile.TemporaryDirectory() as td:
    root=Path(td); lock=root/'heavy.lock'; lock.mkdir(); owner=lock/'owner.txt';owner.write_text('測試')
    original=RuntimeError('原始錯誤')
    try:
        try: raise original
        finally:
            with patch.object(run.subprocess,'run',side_effect=FileNotFoundError('trash不存在')),contextlib.redirect_stderr(io.StringIO()):
                run.release_lock(lock)
    except RuntimeError as e: assert e is original
    assert not lock.exists(),'trash失敗應清理owner並嘗試移除鎖'

    lock.mkdir();owner.write_text('測試');errlog=io.StringIO()
    try:
        try: raise original
        finally:
            with patch.object(run.subprocess,'run',side_effect=OSError('trash失敗')),patch.object(Path,'unlink',side_effect=OSError('owner無法移除')),patch.object(Path,'rmdir',side_effect=OSError('鎖無法移除')) as remove,contextlib.redirect_stderr(errlog):
                run.release_lock(lock)
    except RuntimeError as e: assert e is original
    assert remove.call_count==1 and '鎖無法移除' in errlog.getvalue()
    owner.unlink();lock.rmdir()

    # 乾淨工作目錄亦須先建立testset/results，低記憶體錯誤要保留。
    (root/'manifest.json').write_text(json.dumps({'cameras':[{'reference':'out/reference.npz'}]}))
    def command(args,**kw):
        if args[0]=='trash':Path(args[1]).unlink();return subprocess.CompletedProcess(args,0)
        assert args[0]=='pgrep';return subprocess.CompletedProcess(args,1,'','')
    with contextlib.chdir(root),patch.object(sys,'argv',['ct_world_run.py','manifest.json','0','reference']),patch.object(run,'memory',return_value=0),patch.object(run.subprocess,'run',side_effect=command):
        try:run.main()
        except SystemExit as e:assert '記憶體不足' in str(e)
        else:raise AssertionError('低記憶體必須停止')
    assert (root/'testset/results').is_dir() and not (root/'testset/results/heavy.lock').exists()
print('ct_world_run：新父目錄、trash失敗、清理再失敗、保留原例外通過')

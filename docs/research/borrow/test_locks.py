"""在暫存 checkout 執行各入口的鎖建立敘述，不啟動模型或共用鎖。"""
import ast
from pathlib import Path
import tempfile

for name in ('rtmo_coco.py','far_clip.py','lift_clip.py'):
    tree=ast.parse(Path(__file__).with_name(name).read_text(encoding='utf-8'))
    main=next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='main')
    # 只抽取實際入口的鎖路徑與 mkdir，避免模型／私人資料相依。
    nodes=[node for node in ast.walk(main)
           if (isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='lock' for t in node.targets))
           or (isinstance(node,ast.Expr) and isinstance(node.value,ast.Call)
               and isinstance(node.value.func,ast.Attribute) and node.value.func.attr=='mkdir'
               and ast.unparse(node.value.func.value) in ('lock','lock.parent'))]
    code=compile(ast.Module(body=sorted(nodes,key=lambda n:n.lineno),type_ignores=[]),name,'exec')
    with tempfile.TemporaryDirectory() as directory:
        repo=Path(directory); scope={'repo':repo}
        exec(code,scope)
        lock=repo/'testset/results/heavy.lock'
        assert lock.is_dir(), name
        owner=lock/'owner.txt'; owner.write_text('另一工作持有',encoding='utf-8')
        try: exec(code,scope)
        except FileExistsError: pass
        else: raise AssertionError(name+'未拒絕重複取鎖')
        assert owner.read_text(encoding='utf-8')=='另一工作持有'
print('全新checkout鎖建立與排他自檢通過')

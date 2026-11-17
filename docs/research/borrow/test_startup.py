"""暫存環境驗證入口與空彙總，不取共用鎖、不載入模型。"""
from contextlib import ExitStack, redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch, Mock

import numpy as np

BASE = Path(__file__).resolve().parent
sys.path[:0] = [str(BASE.parent/'caltennis'), str(BASE.parents[2]/'tools')]


def load(name):
    spec = importlib.util.spec_from_file_location(name, BASE/f'{name}.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def release(lock):
    (lock/'owner.txt').unlink(); lock.rmdir()


class StartupTests(unittest.TestCase):
    def environment(self, stack, module, root, memory=16, busy=1):
        stack.enter_context(patch.object(module, '__file__', str(root/'docs/research/borrow'/Path(module.__file__).name)))
        stack.enter_context(patch.object(sys, 'path', sys.path.copy()))
        stack.enter_context(patch.dict(sys.modules, {
            'ct_lr_run': SimpleNamespace(memory=lambda: memory),
            'ct_world_run': SimpleNamespace(release_lock=release),
        }))
        stack.enter_context(patch.object(module.subprocess, 'run', return_value=SimpleNamespace(returncode=busy, stdout='', stderr='')))
        stack.enter_context(redirect_stdout(io.StringIO()))

    def test_far_parent_before_log(self):
        module = load('far_clip')
        with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
            root = Path(directory); target = root/'output/deep/A_rtmo'
            summary = root/'work/rtmo-coco/summary.json'; summary.parent.mkdir(parents=True)
            summary.write_text('{"reproduced":true}', encoding='utf-8')
            manifest = root/'manifest.json'; manifest.write_text(json.dumps({'A': {'out': str(target)}}), encoding='utf-8')
            self.environment(stack, module, root)
            stack.enter_context(patch.object(sys, 'argv', ['far_clip', str(manifest), 'A', 'rtmo']))
            def launch(*args, **kwargs):
                self.assertTrue(target.with_suffix('.log').exists())
                self.assertFalse(target.exists())
                kwargs['stdout'].write('合成子程序\n')
                return SimpleNamespace(returncode=0, poll=lambda: 0)
            proc = stack.enter_context(patch.object(module.subprocess, 'Popen', side_effect=launch))
            module.main()
            self.assertEqual(target.with_suffix('.log').read_text(encoding='utf-8'), '合成子程序\n')
            self.assertFalse((root/'testset/results/heavy.lock').exists())
            with self.assertRaises(FileExistsError): module.main()
            self.assertEqual(proc.call_count, 1)
            self.assertEqual(target.with_suffix('.log').read_text(encoding='utf-8'), '合成子程序\n')

    def test_coco_rejection_leaves_output_unused(self):
        for condition in ('busy', 'locked', 'low_memory'):
            with self.subTest(condition=condition), tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
                module = load('rtmo_coco'); root = Path(directory); out = root/'output'
                annotations = root/'annotations.json'; annotations.write_text('{"images":[]}', encoding='utf-8')
                model = root/'model.onnx'; model.touch()
                self.environment(stack, module, root, memory=7 if condition=='low_memory' else 16, busy=0 if condition=='busy' else 1)
                stack.enter_context(patch.object(module, 'image_paths', return_value=[]))
                rtmo = Mock(side_effect=AssertionError('拒判前不應啟動模型'))
                stack.enter_context(patch.dict(sys.modules, {
                    'rtmlib': SimpleNamespace(RTMO=rtmo),
                    'rtmlib.tools.object_detection.post_processings': SimpleNamespace(multiclass_nms=None),
                    'pycocotools.coco': SimpleNamespace(COCO=None),
                    'pycocotools.cocoeval': SimpleNamespace(COCOeval=None),
                    'cv2': SimpleNamespace(),
                }))
                stack.enter_context(patch.object(sys, 'argv', ['rtmo_coco', '--annotations', str(annotations), '--images', str(root), '--model', str(model), '--rtmlib', str(root/'clone'), '--out', str(out)]))
                lock = root/'testset/results/heavy.lock'
                if condition=='locked':
                    lock.mkdir(parents=True); (lock/'owner.txt').write_text('另一工作', encoding='utf-8')
                with self.assertRaises(FileExistsError if condition=='locked' else RuntimeError): module.main()
                self.assertFalse(out.exists())
                rtmo.assert_not_called()
                if condition=='locked': self.assertEqual((lock/'owner.txt').read_text(encoding='utf-8'), '另一工作')
                else: self.assertFalse(lock.exists())

    def test_empty_lift_denominator(self):
        module = load('lift_clip')
        with tempfile.TemporaryDirectory() as directory, redirect_stdout(io.StringIO()):
            root = Path(directory); rows = root/'rows.json'; rows.write_text('[]', encoding='utf-8')
            for camera in ('0','1'):
                (root/camera).mkdir(); np.save(root/camera/'world.npy', np.full((5,33,3),np.nan))
            module.summarize({'rows': str(rows)}, root)
            result = json.loads((root/'summary.json').read_text(encoding='utf-8'))
            for metric in result.values():
                self.assertEqual((metric['n'],metric['reference_eligible'],metric['coverage']), (0,0,0))
                self.assertIsNone(metric['median']); self.assertIsNone(metric['p90'])
                self.assertFalse(metric['passed'])


if __name__=='__main__': unittest.main()

"""Real core/audit paths with synthetic images and inert provider/executor stubs."""
import importlib
import sys
import tempfile
import types
import unittest
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import AsyncMock, patch

from PIL import Image


class AgentBoundaryTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        # Block heavy imports before loading core. No YOLO, browser or API client
        # is instantiated; the actual Detection and Action dataclass definitions
        # are loaded from their source AST with standard-library dependencies.
        import ast
        def data_class(file, name):
            tree = ast.parse(Path(file).read_text(encoding='utf-8'))
            cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == name)
            scope = {'dataclass': dataclass}
            exec(compile(ast.Module(body=[cls], type_ignores=[]), file, 'exec'), scope)
            return scope[name]
        self.Detection = data_class('detector/model.py', 'Detection')
        Action = data_class('agent/reasoner.py', 'Action')
        detector = types.ModuleType('detector.model')
        detector.Detection = self.Detection
        reasoner = types.ModuleType('agent.reasoner')
        reasoner.Action = Action
        reasoner.VisionReasoner = object
        controller = types.ModuleType('agent.controller')
        controller.PlaywrightController = object
        config = types.ModuleType('config')
        config.settings = types.SimpleNamespace(max_agent_steps=1, action_delay_ms=0,
            wcag_contrast_aa=4.5, wcag_contrast_aaa=7, min_touch_target_px=44)
        config.CLASS_COLORS = {'Button': (59, 130, 246)}
        self.mods = patch.dict(sys.modules, {'detector.model': detector,
            'agent.reasoner': reasoner, 'agent.controller': controller, 'config': config})
        self.mods.start()
        for name in ['agent.core', 'agent.memory', 'agent.annotator', 'audit.accessibility']:
            sys.modules.pop(name, None)
        self.core = importlib.import_module('agent.core')
        self.tmp = tempfile.TemporaryDirectory()
        self.dir_patch = patch.object(self.core, '_SCREENSHOTS_DIR', Path(self.tmp.name))
        self.dir_patch.start()
        self.image = Image.new('RGB', (100, 100), 'white')
        detection = self.Detection((10, 10, 70, 70), 'Button', .9, 7)
        self.detector = types.SimpleNamespace(detect=lambda image: [detection])
        self.controller = types.SimpleNamespace(capture=AsyncMock(return_value=self.image),
            execute=AsyncMock(return_value=True))
        self.reasoner = types.SimpleNamespace(decide=AsyncMock(return_value=Action(7, 'done', '', 'offline')))
        self.agent = self.core.GuiGazerAgent(self.detector, self.reasoner, self.controller)

    def tearDown(self):
        self.dir_patch.stop()
        self.tmp.cleanup()
        self.mods.stop()
        for name in ['agent.core', 'agent.memory', 'agent.annotator', 'audit.accessibility']:
            sys.modules.pop(name, None)

    async def test_detected_object_reaches_real_accessibility_audit_with_id(self):
        result = await self.agent.run_accessibility_audit()
        self.assertEqual(result['summary']['total_elements'], 1)
        self.assertEqual(result['details']['contrast'][0]['element_id'], 7)
        self.assertTrue(result['details']['touch_targets'][0]['passes'])

    async def test_step_callback_carries_an_image_for_server_encoding(self):
        frames = []
        async def capture_frame(frame):
            frames.append(frame)
        result = await self.agent.run_task('offline fixture', callback=capture_frame)
        self.assertTrue(result['completed'])
        self.assertIsInstance(frames[0].get('screenshot'), Image.Image)
        self.assertEqual(frames[0]['screenshot'].size, (100, 100))


if __name__ == '__main__':
    unittest.main()

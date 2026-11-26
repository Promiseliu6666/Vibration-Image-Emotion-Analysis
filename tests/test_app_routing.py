import ast
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request

from fastapi import FastAPI
from fastapi.openapi.docs import get_swagger_ui_html, get_swagger_ui_oauth2_redirect_html
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / 'ruoyi-fastapi-backend'


def source_tree(path):
    return ast.parse(path.read_text(encoding='utf-8'))


class ControllerRegistrationTests(unittest.TestCase):
    def test_video_management_and_camera_routers_are_both_registered_once(self):
        tree = source_tree(BACKEND / 'server.py')
        imports = {
            imported.asname or imported.name: node.module
            for node in tree.body if isinstance(node, ast.ImportFrom)
            for imported in node.names
        }
        declaration = next(
            node for node in tree.body if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == 'controller_list'
                    for target in node.targets)
        )
        controllers = eval(compile(ast.Expression(declaration.value), '<controllers>', 'eval'), imports)
        modules = [controller['router'] for controller in controllers]
        self.assertEqual(modules.count('module_xuzhou.controller.video_controller'), 1)
        self.assertEqual(modules.count('hik_vision.hik_vision'), 1)
        self.assertEqual(len(modules), len(set(modules)))


class SwaggerRoutingTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.app = FastAPI(docs_url=None)
        namespace = {
            'app': self.app,
            'FastAPI': FastAPI,
            'Path': Path,
            '__file__': str(BACKEND / 'sub_applications/staticfiles.py'),
            'StaticFiles': StaticFiles,
            'UploadConfig': SimpleNamespace(UPLOAD_PREFIX='/profile', UPLOAD_PATH=temporary.name),
            'get_swagger_ui_html': get_swagger_ui_html,
            'get_swagger_ui_oauth2_redirect_html': get_swagger_ui_oauth2_redirect_html,
        }
        static_tree = source_tree(BACKEND / 'sub_applications/staticfiles.py')
        static_functions = [node for node in static_tree.body if isinstance(node, ast.FunctionDef)]
        exec(compile(ast.Module(body=static_functions, type_ignores=[]), '<staticfiles>', 'exec'), namespace)
        with patch('os.getcwd', return_value=temporary.name):
            namespace['mount_staticfiles'](self.app)
        server_tree = source_tree(BACKEND / 'server.py')
        docs_functions = [node for node in server_tree.body
                          if getattr(node, 'name', '') in {'custom_swagger_ui_html', 'swagger_ui_redirect'}]
        exec(compile(ast.Module(body=docs_functions, type_ignores=[]), '<swagger>', 'exec'), namespace)

    def assert_swagger_resources(self, client):
        response = client.get('/docs')
        self.assertEqual(response.status_code, 200)
        for resource, content_type in [
            ('swagger-ui-bundle.js', 'javascript'),
            ('swagger-ui.css', 'text/css'),
        ]:
            path = f'/static/swagger-ui/{resource}'
            self.assertIn(path, response.text)
            asset = client.get(path)
            self.assertEqual(asset.status_code, 200)
            self.assertIn(content_type, asset.headers['content-type'])
        self.assertEqual(client.get('/openapi.json').status_code, 200)

    def test_direct_backend_docs_assets(self):
        with TestClient(self.app) as client:
            self.assert_swagger_resources(client)

    def test_docs_assets_behind_stripping_proxy(self):
        async def upstream(scope, receive, send):
            if scope['type'] == 'http':
                scope = {**scope, 'path': '/dev-api' + scope['path']}
            await self.app(scope, receive, send)

        with TestClient(upstream, root_path='/dev-api') as client:
            self.assert_swagger_resources(client)


class PortableRuntimeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.project = Path(temporary.name)
        (self.project / 'prepare-portable.ps1').touch()
        bundled = self.project / '.runtime/python/python.exe'
        bundled.parent.mkdir(parents=True)
        bundled.touch()
        tree = source_tree(ROOT / 'start_local.py')
        function = next(node for node in tree.body if getattr(node, 'name', '') == 'prepare_xiaozhi_runtime')
        namespace = {'subprocess': subprocess}
        exec(compile(ast.Module(body=[function], type_ignores=[]), '<portable-runtime>', 'exec'), namespace)
        self.prepare_runtime = namespace['prepare_xiaozhi_runtime']

    def test_bundled_runtime_uses_existing_relocation_script(self):
        with patch('subprocess.run') as run:
            self.prepare_runtime(self.project)
        run.assert_called_once_with(
            ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
             str(self.project / 'prepare-portable.ps1')],
            cwd=self.project, check=True, creationflags=0x08000000,
        )

    def test_external_runtime_is_not_modified(self):
        (self.project / '.runtime/python/python.exe').unlink()
        with patch('subprocess.run') as run:
            self.prepare_runtime(self.project)
        run.assert_not_called()

    def test_preparation_failure_is_not_ignored(self):
        with patch('subprocess.run', side_effect=subprocess.CalledProcessError(1, 'powershell.exe')):
            with self.assertRaises(subprocess.CalledProcessError):
                self.prepare_runtime(self.project)


class StartupReadinessTests(unittest.TestCase):
    def setUp(self):
        tree = source_tree(ROOT / 'start_local.py')
        function = next(node for node in tree.body if getattr(node, 'name', '') == 'http_ready')
        namespace = {'urllib': __import__('urllib')}
        exec(compile(ast.Module(body=[function], type_ignores=[]), '<startup>', 'exec'), namespace)
        self.http_ready = namespace['http_ready']

    def test_success_is_ready(self):
        with patch('urllib.request.urlopen') as request:
            request.return_value.__enter__.return_value.status = 200
            self.assertTrue(self.http_ready('http://localhost/openapi.json'))

    def test_client_and_server_errors_are_not_ready(self):
        for status in (401, 404, 500, 503):
            with self.subTest(status=status), patch('urllib.request.urlopen') as request:
                request.side_effect = urllib.error.HTTPError('http://localhost/', status, 'error', {}, None)
                self.assertFalse(self.http_ready('http://localhost/openapi.json'))

    def test_unavailable_service_is_not_ready(self):
        with patch('urllib.request.urlopen', side_effect=OSError('connection refused')):
            self.assertFalse(self.http_ready('http://localhost/openapi.json'))


if __name__ == '__main__':
    unittest.main()

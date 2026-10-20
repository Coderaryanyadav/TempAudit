import importlib
import os
import sys
import unittest
from fastapi import FastAPI


class TestCleanEnvironmentImport(unittest.TestCase):
    """
    Guarantees that all backend application modules, routers, services,
    and audit engines can be imported cleanly without missing dependencies
    or runtime NameErrors (e.g. unimported typing annotations like Optional in Python 3.12).
    """

    def test_import_all_backend_app_modules(self):
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)

        app_dir = os.path.join(project_root, "backend", "app")
        import_errors = []

        for root, _, files in os.walk(app_dir):
            for file in files:
                if file.endswith(".py") and not file.startswith("__pycache__"):
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, project_root)
                    module_name = os.path.splitext(rel_path)[0].replace(os.sep, ".")
                    try:
                        importlib.import_module(module_name)
                    except Exception as e:
                        import_errors.append(f"{module_name}: {type(e).__name__}: {e}")

        self.assertEqual(
            len(import_errors),
            0,
            f"The following backend modules failed clean import:\n" + "\n".join(import_errors)
        )

    def test_fastapi_app_initialization(self):
        from backend.app.main import app
        self.assertIsInstance(app, FastAPI)
        self.assertGreater(len(app.routes), 30, "FastAPI application did not mount expected routes")

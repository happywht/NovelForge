import sys
import uvicorn
import builtins
import traceback
from types import ModuleType
import importlib.machinery

# 强制 Mock torch，防止加载 DLL
print("DEBUG: Mocking torch to prevent DLL initialization error...")

class MockSpec:
    def __init__(self, name):
        self.name = name
        self.loader = None
        self.origin = "mock"
        self.submodule_search_locations = []

mock_torch = ModuleType("torch")
mock_torch.__version__ = "2.9.1+cpu-mock"
mock_torch.__spec__ = MockSpec("torch")
mock_torch.__path__ = []
mock_torch.cuda = ModuleType("torch.cuda")
mock_torch.cuda.is_available = lambda: False
mock_torch.nn = ModuleType("torch.nn")
mock_torch.nn.Module = type("Module", (), {})

sys.modules["torch"] = mock_torch

# 追踪 torch 导入
_original_import = builtins.__import__
def _trace_import(name, globals=None, locals=None, fromlist=(), level=0):
    if name == 'torch' or (isinstance(name, str) and 'torch' in name):
        if name not in sys.modules:
            print(f"\nDEBUG: Sub-importing '{name}' from:")
            traceback.print_stack(limit=10)
            print("-" * 40)
            # 自动为子模块创建 mock
            m = ModuleType(name)
            m.__spec__ = MockSpec(name)
            sys.modules[name] = m
            return m
    return _original_import(name, globals, locals, fromlist, level)

builtins.__import__ = _trace_import

# PyInstaller 兼容性
if getattr(sys, 'frozen', False):
    import inspect
    _original_getsource = inspect.getsource
    _original_getsourcelines = inspect.getsourcelines
    _original_findsource = inspect.findsource
    def _getsource_fallback(obj):
        try: return _original_getsource(obj)
        except (OSError, TypeError): return f"# Source not available\n"
    def _getsourcelines_fallback(obj):
        try: return _original_getsourcelines(obj)
        except (OSError, TypeError): return (["# Source not available\n"], 0)
    def _findsource_fallback(obj):
        try: return _original_findsource(obj)
        except (OSError, TypeError): return (["# Source not available\n"], 0)
    inspect.getsource = _getsource_fallback
    inspect.getsourcelines = _getsourcelines_fallback
    inspect.findsource = _findsource_fallback

if __name__ == "__main__":
    from main import app
    print("Starting backend on port 8000 with Advanced Mocked Torch...")
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
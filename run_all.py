"""One command: schema -> world -> (optional) DuckDB load + validation.   python run_all.py"""
import subprocess, sys, os
ROOT = os.path.dirname(os.path.abspath(__file__))
env = dict(os.environ, PYTHONPATH=ROOT)
for cmd in (["build_schema.py"], ["build_world.py"]): subprocess.run([sys.executable, os.path.join(ROOT, cmd[0])], check=True, env=env, cwd=ROOT)
try:
    import duckdb  # noqa
    subprocess.run([sys.executable, os.path.join(ROOT, "load_duckdb.py")], check=True, env=env, cwd=ROOT)
except ImportError:
    print("duckdb not installed: run `pip install duckdb` then `python load_duckdb.py`")

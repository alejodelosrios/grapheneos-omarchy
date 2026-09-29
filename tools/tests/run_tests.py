#!/usr/bin/env python3
"""Runner mínimo pytest-compatible para tools/tests (este host no tiene pytest instalado).

Los tests están escritos como pytest (funciones `test_*` con `assert` simple, sin fixtures):
con pytest instalado, `python3 -m pytest -q tools/tests tests` los corre tal cual. Este runner
descubre `test_*.py` en las rutas dadas, ejecuta cada `test_*` y reporta PASS/FAIL.

    python3 tools/tests/run_tests.py [ruta...] [--only SUBCADENA]

Exit 0 = todo verde; 1 = algún fallo **o cero tests ejecutados** (vacío no es éxito).
"""
from __future__ import annotations

import importlib.util
import sys
import traceback
from pathlib import Path


def load_module(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[path.stem] = mod
    spec.loader.exec_module(mod)
    return mod


def collect(paths: list[str]) -> list[Path]:
    out: list[Path] = []
    for p in paths:
        q = Path(p)
        if q.is_dir():
            out += sorted(q.rglob("test_*.py"))
        elif q.is_file():
            out.append(q)
    return out


def main(argv: list[str]) -> int:
    only = None
    if "--only" in argv:
        i = argv.index("--only")
        only = argv[i + 1]
        del argv[i:i + 2]
    files = collect(argv[1:] or ["tools/tests", "tests"])
    n_pass = n_fail = ran = 0
    for f in files:
        try:
            mod = load_module(f)
        except Exception as e:
            n_fail += 1
            print(f"FAIL {f}: no importa: {e.__class__.__name__}: {e}")
            continue
        for name in sorted(dir(mod)):
            if not name.startswith("test_"):
                continue
            fn = getattr(mod, name)
            if not callable(fn):
                continue
            if only and only not in name:
                continue
            ran += 1
            try:
                fn()
                n_pass += 1
                print(f"PASS {f.name}::{name}")
            except Exception as e:
                n_fail += 1
                print(f"FAIL {f.name}::{name}: {e.__class__.__name__}: {e}")
                for fr in traceback.extract_tb(e.__traceback__):
                    if fr.filename == str(f):
                        print(f"     en {f.name}:{fr.lineno}")
    print(f"{n_pass} passed, {n_fail} failed, {ran} run")
    return 1 if (n_fail or not ran) else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

"""Tests de QA del issue #10 (design-10 «Criterios estáticos S6-S8» + docs).

Criterios verificables SIN host de build ni Pixel:
  S6 (condición 1). .github/workflows/lib.yml: todo `uses:` casa con
      `^[\\w.-]+/[\\w./-]+@[0-9a-f]{40} # v\\d+\\.\\d+\\.\\d+$`; `permissions` de la raíz ==
      {contents: read}; cero `secrets.` y cero `pull_request_target`; `persist-credentials:
      false` en el checkout.
  S7 (condición 3). `git check-ignore -q` ignora apps/sdk/{build,.gradle}/x,
      apps/sdk/local.properties y apps/sdk/sample/build/x; ni gradle-wrapper.jar ni
      gradlew están en `git ls-files`.
  S8. Todos los archivos de apps/sdk que hay en disco (fuera de los ignorados) y
      .github/workflows/lib.yml pasan `git ls-files --error-unmatch`.
  Docs: docs/THEMING.md contiene cada una de las 28 columnas entre backticks (D4);
      docs-writer lo escribe en paralelo, así que un fallo aquí puede ser suyo, no de qa.

Compatible con pytest y con tools/tests/run_tests.py (funciones `test_*`, sin fixtures,
stdlib salvo PyYAML si está instalado, con fallback textual). Cada test se vio en ROJO
con su sabotaje sobre el texto en memoria: nunca se edita un archivo del repo.
"""
from __future__ import annotations

import re
import subprocess
import tomllib
from pathlib import Path

try:
    import yaml

    HAVE_YAML = True
except ImportError:  # pragma: no cover - entorno sin PyYAML
    HAVE_YAML = False

REPO = Path(__file__).resolve().parents[2]
LIB_WORKFLOW = REPO / ".github" / "workflows" / "lib.yml"
SDK_DIR = REPO / "apps" / "sdk"
THEMING_MD = REPO / "docs" / "THEMING.md"

USES_RE = re.compile(r"^[\w.-]+/[\w./-]+@[0-9a-f]{40} # v\d+\.\d+\.\d+$")


# --- helpers -----------------------------------------------------------------------


def uses_lines(text: str) -> list[str]:
    return [m.group(1) for m in re.finditer(r"uses:\s*(\S.*\S|\S)\s*$", text, re.MULTILINE)]


def uses_all_pinned(text: str) -> bool:
    lines = uses_lines(text)
    assert lines, "no se encontró ningún `uses:` en el workflow"
    return all(USES_RE.match(line) for line in lines)


def root_permissions_yaml_safe(text: str) -> dict:
    """`permissions:` de nivel raíz, como dict. PyYAML si está instalado; si no, un
    parseo textual del bloque `permissions:\\n  clave: valor` en columna 0."""
    if HAVE_YAML:
        doc = yaml.safe_load(text)
        return doc.get("permissions", {})
    m = re.search(r"^permissions:\s*\n((?:^  \S.*\n?)+)", text, re.MULTILINE)
    assert m, "no se encontró `permissions:` de nivel raíz"
    perms = {}
    for line in m.group(1).splitlines():
        key, _, val = line.strip().partition(":")
        perms[key.strip()] = val.strip()
    return perms


def has_no_secrets_or_pr_target(text: str) -> bool:
    return "secrets." not in text and "pull_request_target" not in text


def checkout_persists_no_credentials(text: str) -> bool:
    m = re.search(r"uses:\s*actions/checkout@[^\n]*\n(\s+with:\n(?:\s{2,}.*\n?)+)", text)
    if not m:
        return False
    block = m.group(1)
    return re.search(r"persist-credentials:\s*false", block) is not None


def check_ignore(path: str) -> bool:
    out = subprocess.run(["git", "check-ignore", "-q", path], cwd=REPO)
    return out.returncode == 0


def git_ls_files(patterns: list[str]) -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", *patterns], capture_output=True, cwd=REPO, text=True
    )
    assert out.returncode == 0, out.stderr
    return [line for line in out.stdout.splitlines() if line]


def git_error_unmatch(path: str) -> bool:
    out = subprocess.run(
        ["git", "ls-files", "--error-unmatch", path], capture_output=True, cwd=REPO, text=True
    )
    return out.returncode == 0


def sdk_disk_files_not_ignored() -> list[Path]:
    files = []
    for f in SDK_DIR.rglob("*"):
        if f.is_dir():
            continue
        rel = str(f.relative_to(REPO))
        if check_ignore(rel):
            continue
        files.append(f)
    return files


def theming_columns() -> list[str]:
    theme_dirs = sorted((REPO / "themes").iterdir())
    data = tomllib.loads((theme_dirs[0] / "theme.toml").read_text())
    color_keys = [k for k, v in data.items() if k not in ("name", "mode") and not isinstance(v, dict)]
    return ["id", "name", "mode"] + color_keys


def missing_backticked_columns(text: str, columns: list[str]) -> list[str]:
    return [c for c in columns if f"`{c}`" not in text]


# --- S6 ------------------------------------------------------------------------------


def test_i10_s6_uses_pinneados_a_sha40_mas_version():
    assert uses_all_pinned(LIB_WORKFLOW.read_text())


def test_i10_s6_sabotaje_sha_reemplazado_por_tag_da_rojo():
    text = LIB_WORKFLOW.read_text()
    assert uses_all_pinned(text)
    sabotaged = text.replace(
        "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1",
        "actions/checkout@v7",
        1,
    )
    assert sabotaged != text, "el sabotaje no encontró el `uses: actions/checkout@<sha>`"
    assert not uses_all_pinned(sabotaged)


def test_i10_s6_permissions_raiz_es_solo_contents_read():
    perms = root_permissions_yaml_safe(LIB_WORKFLOW.read_text())
    assert perms == {"contents": "read"}, perms


def test_i10_s6_sabotaje_permissions_ampliados_da_rojo():
    text = LIB_WORKFLOW.read_text()
    assert root_permissions_yaml_safe(text) == {"contents": "read"}
    sabotaged = text.replace("permissions:\n  contents: read\n", "permissions:\n  contents: write\n", 1)
    assert sabotaged != text, "el sabotaje no encontró `permissions: contents: read`"
    assert root_permissions_yaml_safe(sabotaged) != {"contents": "read"}


def test_i10_s6_sin_secrets_ni_pull_request_target():
    assert has_no_secrets_or_pr_target(LIB_WORKFLOW.read_text())


def test_i10_s6_sabotaje_secrets_da_rojo():
    text = LIB_WORKFLOW.read_text()
    assert has_no_secrets_or_pr_target(text)
    sabotaged = text + "\n      - run: echo ${{ secrets.TOKEN }}\n"
    assert not has_no_secrets_or_pr_target(sabotaged)


def test_i10_s6_checkout_persist_credentials_false():
    assert checkout_persists_no_credentials(LIB_WORKFLOW.read_text())


def test_i10_s6_sabotaje_persist_credentials_true_da_rojo():
    text = LIB_WORKFLOW.read_text()
    assert checkout_persists_no_credentials(text)
    sabotaged = text.replace("persist-credentials: false", "persist-credentials: true", 1)
    assert sabotaged != text, "el sabotaje no encontró `persist-credentials: false`"
    assert not checkout_persists_no_credentials(sabotaged)


# --- S7 ------------------------------------------------------------------------------


def test_i10_s7_gitignore_cubre_build_gradle_localproperties():
    for rel in (
        "apps/sdk/build/x",
        "apps/sdk/.gradle/x",
        "apps/sdk/local.properties",
        "apps/sdk/sample/build/x",
    ):
        assert check_ignore(rel), f"{rel} no está ignorado"


def test_i10_s7_ningun_gradle_wrapper_trackeado():
    tracked = git_ls_files(["apps/sdk"])
    wrapper_hits = [f for f in tracked if f.endswith("gradle-wrapper.jar") or f.endswith("/gradlew") or f == "gradlew"]
    assert not wrapper_hits, f"wrapper trackeado: {wrapper_hits}"


# --- S8 ------------------------------------------------------------------------------


def test_i10_s8_archivos_de_disco_en_apps_sdk_estan_trackeados():
    disk_files = sdk_disk_files_not_ignored()
    assert disk_files, "no se encontraron archivos en apps/sdk"
    untracked = [str(f.relative_to(REPO)) for f in disk_files if not git_error_unmatch(str(f.relative_to(REPO)))]
    assert not untracked, f"sin trackear: {untracked}"


def test_i10_s8_workflow_esta_trackeado():
    assert git_error_unmatch(".github/workflows/lib.yml")


# --- Docs ------------------------------------------------------------------------------


def test_i10_docs_theming_documenta_las_28_columnas():
    columns = theming_columns()
    assert len(columns) == 28, f"se esperaban 28 columnas, hay {len(columns)}"
    text = THEMING_MD.read_text()
    missing = missing_backticked_columns(text, columns)
    assert not missing, (
        f"docs/THEMING.md no menciona entre backticks: {missing} "
        "(si docs-writer aún no terminó §API, este fallo es suyo, no de qa)"
    )


def test_i10_docs_sabotaje_columna_quitada_da_rojo():
    text = THEMING_MD.read_text()
    columns = theming_columns()
    assert not missing_backticked_columns(text, columns)
    sabotaged = text.replace("`bright_magenta`", "bright_magenta")
    assert sabotaged != text, "el sabotaje no encontró `bright_magenta`"
    assert missing_backticked_columns(sabotaged, columns) == ["bright_magenta"]

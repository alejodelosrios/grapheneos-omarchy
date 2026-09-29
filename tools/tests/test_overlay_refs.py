"""Tests del check de referencias de OmarchySystemUIOverlay (design-5 §qa).

Cubre el check estático nuevo: `@color/`, `@dimen/`, `@drawable/`, `?android:attr/` solo pueden
ser locales del overlay o `@android:` de la lista cerrada del diseño (tools/system-colors.txt NO
se usa — es de #8). Los tests sintéticos fijan que el check NO es vacío (detecta lo prohibido);
el test del overlay real fija que el overlay actual está limpio.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import overlay_refs  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
RES = REPO / "overlay" / "OmarchySystemUIOverlay" / "res"


def make_res(files: dict[str, str]) -> Path:
    res = Path(tempfile.mkdtemp(prefix="qa-refs-")) / "res"
    for rel, text in files.items():
        p = res / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return res


def test_overlay_real_sin_violaciones():
    viol = overlay_refs.check_res_dir(RES)
    assert viol == [], "violaciones en el overlay real:\n" + "\n".join(viol)


def test_lista_cerrada_es_la_del_diseno():
    """La lista cerrada es literalmente la de design-5 §Tabla de citas: ni un símbolo más."""
    esperado = {
        "color": frozenset({
            "system_surface_container_high_light",
            "system_surface_container_high_dark",
            "system_on_surface_light",
            "system_on_surface_dark",
            "system_secondary_light",
            "system_secondary_dark",
            "system_accent1_500",
            "transparent",
        }),
        "dimen": frozenset(),
        "drawable": frozenset(),
        "attr": frozenset({"colorControlHighlight"}),
    }
    assert overlay_refs.CLOSED_ANDROID == esperado, (
        f"lista cerrada alterada: {overlay_refs.CLOSED_ANDROID}"
    )


def test_comentario_no_es_referencia():
    xml = (
        '<?xml version="1.0" encoding="utf-8"?>\n<resources>\n'
        "    <!-- prohibido pero solo en comentario: @color/materialColorSurfaceContainerHigh"
        " y @android:color/system_accent1_100 -->\n"
        '    <color name="ok">@android:color/transparent</color>\n</resources>\n'
    )
    res = make_res({"values/colors.xml": xml})
    viol = overlay_refs.check_res_dir(res)
    assert viol == [], f"un comentario no puede ser referencia: {viol}"


def test_color_privado_detectado():
    xml = (
        '<?xml version="1.0" encoding="utf-8"?>\n<resources>\n'
        '    <color name="evil">@color/materialColorSurfaceContainerHigh</color>\n'
        "</resources>\n"
    )
    res = make_res({"values/colors.xml": xml})
    viol = overlay_refs.check_res_dir(res)
    assert any("materialColorSurfaceContainerHigh" in v for v in viol), (
        f"color privado no detectado: {viol}"
    )


def test_android_color_fuera_de_lista_detectado():
    """system_accent1_100 es upstream (notification_scrim_base) pero NO de esta lista cerrada."""
    xml = (
        '<?xml version="1.0" encoding="utf-8"?>\n<resources>\n'
        '    <color name="evil">@android:color/system_accent1_100</color>\n'
        "</resources>\n"
    )
    res = make_res({"values/colors.xml": xml})
    viol = overlay_refs.check_res_dir(res)
    assert any("system_accent1_100" in v for v in viol), (
        f"@android: fuera de lista no detectado: {viol}"
    )


def test_attr_fuera_de_lista_detectado():
    xml = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<layer-list xmlns:android="http://schemas.android.com/apk/res/android"\n'
        '        android:color="?android:attr/colorBackground">\n'
        "    <item><shape><solid android:color=\"@android:color/transparent\" /></shape></item>\n"
        "</layer-list>\n"
    )
    res = make_res({"drawable/d.xml": xml})
    viol = overlay_refs.check_res_dir(res)
    assert any("colorBackground" in v for v in viol), (
        f"?android:attr fuera de lista no detectado: {viol}"
    )


def test_ref_local_y_cerradas_pasan():
    values = (
        '<?xml version="1.0" encoding="utf-8"?>\n<resources>\n'
        '    <color name="omarchy_local_color">@android:color/system_accent1_500</color>\n'
        '    <dimen name="omarchy_local_dimen">1dp</dimen>\n'
        "</resources>\n"
    )
    drawable = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<layer-list xmlns:android="http://schemas.android.com/apk/res/android"\n'
        '        android:color="?android:attr/colorControlHighlight">\n'
        "    <item><shape>\n"
        '        <solid android:color="@color/omarchy_local_color" />\n'
        '        <stroke android:width="@dimen/omarchy_local_dimen"'
        ' android:color="@android:color/transparent" />\n'
        "    </shape></item>\n"
        "    <item><shape>\n"
        '        <solid android:color="@android:color/system_surface_container_high_light" />\n'
        "    </shape></item>\n"
        "</layer-list>\n"
    )
    res = make_res({
        "values/colors.xml": values,
        "drawable/d.xml": drawable,
    })
    viol = overlay_refs.check_res_dir(res)
    assert viol == [], f"referencias legales marcadas como violación: {viol}"


def test_dimen_y_drawable_locales():
    bad = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<layer-list xmlns:android="http://schemas.android.com/apk/res/android">\n'
        "    <item><shape>\n"
        '        <stroke android:width="@dimen/nope" android:color="@drawable/nope" />\n'
        "    </shape></item>\n"
        "</layer-list>\n"
    )
    res = make_res({"drawable/d.xml": bad})
    viol = overlay_refs.check_res_dir(res)
    assert any("@dimen/nope" in v for v in viol), f"@dimen sin definir no detectado: {viol}"
    assert any("@drawable/nope" in v for v in viol), f"@drawable sin definir no detectado: {viol}"

    values = (
        '<?xml version="1.0" encoding="utf-8"?>\n<resources>\n'
        '    <dimen name="omarchy_d">1dp</dimen>\n</resources>\n'
    )
    icon = '<?xml version="1.0" encoding="utf-8"?>\n<shape xmlns:android="http://schemas.android.com/apk/res/android" />\n'
    good = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<layer-list xmlns:android="http://schemas.android.com/apk/res/android">\n'
        "    <item><shape>\n"
        '        <stroke android:width="@dimen/omarchy_d" android:color="@drawable/icon" />\n'
        "    </shape></item>\n"
        "</layer-list>\n"
    )
    res = make_res({
        "values/dimens.xml": values,
        "drawable/icon.xml": icon,
        "drawable/d.xml": good,
    })
    viol = overlay_refs.check_res_dir(res)
    assert viol == [], f"dimen/drawable locales no resueltos: {viol}"

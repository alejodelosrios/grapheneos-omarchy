# fonts/ — JetBrainsMono Nerd Font (variante NerdFont)

Fuentes del sistema instaladas en `/product/fonts/` (ver `omarchy.mk` y
`docs/research.md:176-178`, `SystemFonts.java` `OEM_FONT_DIR`). Las familias
`jetbrains-mono-nerd` / `jetbrains-mono-nerd-medium` las registra
`fonts/fonts_customization.xml` (`new-named-family`).

## Origen

- Release oficial: <https://github.com/ryanoasis/nerd-fonts/releases/tag/v3.5.1>
- Asset descargado: `JetBrainsMono.zip`
  (<https://github.com/ryanoasis/nerd-fonts/releases/download/v3.5.1/JetBrainsMono.zip>)
- Versión: **v3.5.1** (publicada 2026-08-21, según la API de GitHub)
- Variante: **NerdFont** (glifos de doble ancho), NO la variante `NerdFontMono`
  (`JetBrainsMonoNerdFontMono-*`), por decisión del issue #6.
- `fonts/OFL.txt` extraído del propio zip (`unzip -j`), nunca escrito de memoria.

## sha256 (de los archivos en este directorio)

| Archivo | sha256 |
|---|---|
| `JetBrainsMonoNerdFont-Regular.ttf` | `1c680e8cde9fcf8b88a5605ce8d1fb94dd3fb15841f7ca7bf4c55664855e5611` |
| `JetBrainsMonoNerdFont-Medium.ttf` | `c9405e11b36d071176e318263e7251e96e60f3804dfc5ac8b2806f1f8085b066` |
| `JetBrainsMonoNerdFont-Bold.ttf` | `e490660ad75e0b152c93b1604c2ea1a4ea675f1b8a3fe0d005b1998568f99f1f` |
| `OFL.txt` | `30f0c136e3c88e422d0791acd97238870f9054a9729bc34cf2ff0d4ed8cac4ad` |

Verificación: `sha256sum fonts/JetBrainsMonoNerdFont-*.ttf fonts/OFL.txt`

## Licencias

- **JetBrains Mono**: SIL Open Font License 1.1 — texto completo en `fonts/OFL.txt`
  («Copyright 2020 The JetBrains Mono Project Authors»).
- **Parche Nerd Fonts**: MIT (`docs/research.md:250`).

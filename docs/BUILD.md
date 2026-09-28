# BUILD — de `repo init` a release firmado

Todo en el **servidor de compilación** (`docs/HARDWARE.md`). Los comandos son los oficiales de
<https://grapheneos.org/build> más el hook de `vendor/omarchy`. `DEVICE=tegu` (Pixel 9a) como
ejemplo; `comet` (Pixel 9 Pro Fold) es el segundo objetivo.

## 1. Árbol de GrapheneOS

```bash
mkdir -p ~/grapheneos && cd ~/grapheneos
repo init -u https://github.com/GrapheneOS/platform_manifest.git -b refs/tags/2026091900   # stable
# repo init ... -b 17           # rama de desarrollo
# Opcional en CI: añadir --depth=1 al repo init (menos disco; sin historial para bisect)
mkdir -p .repo/local_manifests
curl -o .repo/local_manifests/omarchy.xml https://raw.githubusercontent.com/alejodelosrios/grapheneos-omarchy/main/manifests/omarchy.xml
repo sync -j$(nproc) --no-tags --no-clone-bundle
ls vendor/omarchy/omarchy.mk   # el hook está en el árbol
```

## 2. Kernel y vendor blobs (sin cambios respecto a GrapheneOS)

```bash
# prebuilts de kernel ya vienen en el manifest (device/google/<familia>-kernels/*)
yarn install --cwd vendor/adevtool/
source build/envsetup.sh
lunch sdk_phone64_x86_64-cur-user     # solo para construir aapt2 para adevtool
m aapt2
# Árbol de dispositivo generado por adevtool CON el hook de Omarchy:
vendor/adevtool/bin/run generate-all -d vendor/omarchy/adevtool/tegu.yml
grep -n omarchy device/google/tegu/tegu.mk   # -> include vendor/omarchy/omarchy.mk
```

`vendor/omarchy/adevtool/tegu.yml` hereda `vendor/adevtool/config/device/tegu.yml` y solo añade
`platform.extra_product_makefiles`. Si adevtool cambia esa clave, el fallback es una línea:
`echo '$(call inherit-product, vendor/omarchy/omarchy.mk)' >> device/google/tegu/tegu.mk`.

## 3. Build

```bash
source build/envsetup.sh
lunch tegu-cur-user          # userdebug para desarrollo: tegu-cur-userdebug
export BUILD_NUMBER=$(date -u +%Y%m%d%H)      # o el tag de GrapheneOS + sufijo propio
m vendorbootimage vendorkernelbootimage target-files-package    # Pixel 7+; Pixel 6: m vendorbootimage target-files-package
```

Comprobaciones antes de firmar:

```bash
ls $OUT/product/overlay/            # OmarchyFrameworkOverlay.apk ... OmarchyPaletteTokyoNight.apk
ls $OUT/product/priv-app/OmarchyTheme/
ls $OUT/product/fonts/ $OUT/product/etc/fonts_customization.xml $OUT/product/etc/omarchy/
unzip -l $OUT/obj/PACKAGING/target_files_intermediates/tegu-target_files.zip | grep -c omarchy
```

## 4. Claves (una vez por dispositivo; NUNCA en el repo)

```bash
script/generate-keys tegu            # make_key releasekey/platform/... + avb.pem + avb_pkmd.bin
script/encrypt-keys keys/tegu        # cifra con passphrase; decrypt-keys lo revierte
```

Es el mismo flujo de GrapheneOS: `script/generate-keys` llama a `development/tools/make_key`
por cada `signing_keys` de `script/common.sh` y genera la clave AVB (RSA-4096). Guardar
`keys/tegu` cifrado fuera del árbol (backup offline).

## 5. Release firmado + OTA

```bash
script/finalize.sh                        # copia otatools + target_files a releases/$BUILD_NUMBER/
script/generate-release.sh tegu $BUILD_NUMBER
ls releases/$BUILD_NUMBER/release-tegu-$BUILD_NUMBER/
#  tegu-ota_update-<N>.zip   tegu-install-<N>.zip (factory)   tegu-img-<N>.zip  + metadata (stable/beta)
```

`generate-release.sh` firma con `sign_target_files_apks` (APKs + APEX + `vbmeta` con `avb.pem`),
genera OTA con `ota_from_target_files`, y la metadata con `script/generate-metadata`. Los
overlays y `OmarchyTheme` se firman con las mismas claves que el resto de `product`
(`OmarchyTheme` usa `certificate: "platform"` → clave `platform` del `keys/tegu`).

Primera instalación: `fastboot` con la imagen de fábrica (`tegu-install-*.zip`) siguiendo
<https://grapheneos.org/install/cli>, bootloader desbloqueado, **flashear nuestra `avb_pkmd.bin`**
(`fastboot flash avb_custom_key`) y volver a bloquear. Las siguientes van por OTA.

Servidor OTA: copiar `tegu-ota_update-*.zip` + `tegu-stable` (metadata) a un hosting estático y
apuntar el `Updater` a esa URL (RRO sobre `app.seamlessupdate.client`, issue *M0 · Keys + OTA*).

## 6. Rebase mensual (procedimiento)

```bash
cd ~/grapheneos
repo init -u https://github.com/GrapheneOS/platform_manifest.git -b refs/tags/<NUEVO_TAG>
repo sync -j$(nproc) --no-tags --no-clone-bundle
vendor/adevtool/bin/run generate-all -d vendor/omarchy/adevtool/tegu.yml
source build/envsetup.sh && lunch tegu-cur-user && m target-files-package
```

Si falla, el 95 % es un recurso renombrado en un RRO: el error de aapt2 nombra el recurso; se
corrige en `vendor/omarchy` y se documenta en `docs/THEMING.md §Compat`. `vendor/omarchy` no tiene
nada que rebasar: es un proyecto aparte del manifest.

## 7. Desarrollo rápido sin rebuild de ROM (userdebug)

```bash
# compilar solo un overlay o la app
m OmarchyPaletteTokyoNight OmarchyTheme
adb root && adb remount
adb push $OUT/product/overlay/OmarchyPaletteTokyoNight.apk /product/overlay/
adb shell cmd overlay enable-exclusive --category org.omarchy.palette.tokyonight
adb shell settings put secure theme_customization_overlay_packages \
  '{"android.theme.customization.system_palette":"org.omarchy.palette.tokyonight","android.theme.customization.color_source":"preset"}'
adb shell cmd overlay list | grep omarchy
```

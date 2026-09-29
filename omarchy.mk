# vendor/omarchy/omarchy.mk — included via adevtool `platform.extra_product_makefiles`
# (see adevtool/tegu.yml). Nothing here touches a GrapheneOS-forked repo.

OMARCHY_DIR := vendor/omarchy

# Static, theme-independent skin (always on, immutable)
PRODUCT_PACKAGES += \
    OmarchyFrameworkOverlay \
    OmarchySystemUIOverlay \
    OmarchyShapeOverlay \
    OmarchyFontOverlay

# Switchable palettes: one mutable RRO per theme, exactly one enabled at a time
# (category android.theme.customization.system_palette, driven by OmarchyTheme)
PRODUCT_PACKAGES += \
    OmarchyPaletteCatppuccin \
    OmarchyPaletteEverforest \
    OmarchyPaletteGruvbox \
    OmarchyPaletteKanagawa \
    OmarchyPaletteNord \
    OmarchyPaletteTokyoNight

# Theme service + picker + QS tile + ContentProvider for third-party apps
PRODUCT_PACKAGES += OmarchyTheme

# Overlay default state (mutable/enabled) for the product partition
PRODUCT_COPY_FILES += \
    $(OMARCHY_DIR)/overlay/config/config.xml:$(TARGET_COPY_OUT_PRODUCT)/overlay/config/config.xml

# Fonts: /product/fonts + /product/etc/fonts_customization.xml (SystemFonts.java OEM_XML)
PRODUCT_COPY_FILES += \
    $(OMARCHY_DIR)/fonts/fonts_customization.xml:$(TARGET_COPY_OUT_PRODUCT)/etc/fonts_customization.xml \
    $(foreach f,$(wildcard $(OMARCHY_DIR)/fonts/*.ttf),$(f):$(TARGET_COPY_OUT_PRODUCT)/fonts/$(notdir $(f)))

# Theme catalog readable by OmarchyTheme (theme.toml + backgrounds), mirrors ~/.config/omarchy/themes
PRODUCT_COPY_FILES += \
    $(foreach f,$(wildcard $(OMARCHY_DIR)/themes/*/theme.toml $(OMARCHY_DIR)/themes/*/backgrounds/*),$(f):$(TARGET_COPY_OUT_PRODUCT)/etc/omarchy/$(patsubst $(OMARCHY_DIR)/themes/%,%,$(f)))

# Boot animation (BootAnimation.cpp: PRODUCT_BOOTANIMATION_DIR = /product/media/)
ifneq ($(wildcard $(OMARCHY_DIR)/bootanimation/bootanimation.zip),)
PRODUCT_COPY_FILES += \
    $(OMARCHY_DIR)/bootanimation/bootanimation.zip:$(TARGET_COPY_OUT_PRODUCT)/media/bootanimation.zip
endif

# Identity of the derivative (must NOT claim to be GrapheneOS — see docs/research.md §5)
PRODUCT_PRODUCT_PROPERTIES += \
    ro.omarchy.version=0.1.0 \
    ro.omarchy.theme.default=tokyo-night

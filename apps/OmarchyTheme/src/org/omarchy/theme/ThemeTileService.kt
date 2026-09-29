package org.omarchy.theme

import android.os.Handler
import android.os.Looper
import android.service.quicksettings.Tile
import android.service.quicksettings.TileService

private const val DEFAULT_LABEL = "Omarchy theme"

/**
 * QS tile: shows the current theme name, cycles to the next theme on tap. `TileService` is
 * public Android SDK API (no @SystemApi/@hide), declared for this service in
 * `AndroidManifest.xml:29-35` (BIND_QUICK_SETTINGS_TILE + QS_TILE intent-filter,
 * `.swarm/design/design-9-theme-switcher.md` row P6). `ThemeCatalog.get`/`ThemeSwitcher.current`/
 * `.next()` do file/binder I/O: never on the main thread (KDoc de `ThemeSwitcher`), so both
 * callbacks resolve the theme on a background `Thread` and only touch `qsTile` on the main
 * `Looper`.
 */
class ThemeTileService : TileService() {
    private val mainHandler = Handler(Looper.getMainLooper())

    override fun onStartListening() {
        super.onStartListening()
        Thread {
            val name = ThemeCatalog.get(ThemeSwitcher(this).current())?.name
            updateLabel(name)
        }.start()
    }

    override fun onClick() {
        super.onClick()
        Thread {
            val name = ThemeSwitcher(this).next()?.name
            updateLabel(name)
        }.start()
    }

    private fun updateLabel(name: String?) {
        mainHandler.post {
            qsTile?.let { tile ->
                tile.label = name ?: DEFAULT_LABEL
                tile.state = Tile.STATE_ACTIVE
                tile.updateTile()
            }
        }
    }
}

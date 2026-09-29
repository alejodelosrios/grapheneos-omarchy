package org.omarchy.theme

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent

/**
 * Re-applies the saved theme on boot. Needed because a JSON-empty first boot makes SystemUI enable
 * its default Monet FRRO and disable our palette overlay (D4: ThemeOverlayController.java:818-821 +
 * ThemeOverlayApplier.java:209-225), so `current()`'s palette must be re-applied once the system is up.
 */
class BootReceiver : BroadcastReceiver() {
    override fun onReceive(
        context: Context,
        intent: Intent,
    ) {
        // Exported receiver: BOOT_COMPLETED is a protected broadcast, so any other action here
        // would have to come from an explicit intent sent by a third party — ignore it.
        if (intent.action != Intent.ACTION_BOOT_COMPLETED) return

        val pending = goAsync()
        Thread {
            try {
                val s = ThemeSwitcher(context)
                val id = s.current()
                val pkg = ThemeCatalog.get(id)?.palettePackage
                if (pkg != null && s.appliedPalette() != pkg) s.set(id)
            } finally {
                pending.finish()
            }
        }.start()
    }
}

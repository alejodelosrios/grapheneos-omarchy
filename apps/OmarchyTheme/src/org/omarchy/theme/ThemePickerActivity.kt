package org.omarchy.theme

import android.app.Activity
import android.graphics.Color
import android.os.Bundle
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.widget.AbsListView
import android.widget.ArrayAdapter
import android.widget.Button
import android.widget.LinearLayout
import android.widget.ListView
import android.widget.TextView
import android.widget.Toast

/**
 * Picker UI only: launched from the launcher icon or QS_TILE_PREFERENCES. It never applies a
 * theme on its own — only the "Apply" tap calls ThemeSwitcher.set (safety condition, see
 * .swarm/design/design-9-theme-switcher.md, end of file).
 */
class ThemePickerActivity : Activity() {
    private lateinit var listView: ListView
    private lateinit var applyButton: Button
    private lateinit var adapter: ArrayAdapter<Theme>
    private lateinit var switcher: ThemeSwitcher
    private var currentId: String? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        switcher = ThemeSwitcher(this)

        adapter = ThemeAdapter(this)
        listView =
            ListView(this).apply {
                choiceMode = AbsListView.CHOICE_MODE_SINGLE
                setAdapter(adapter)
            }
        applyButton =
            Button(this).apply {
                text = "Apply"
                setOnClickListener { onApplyClicked() }
            }

        val root =
            LinearLayout(this).apply {
                orientation = LinearLayout.VERTICAL
                addView(
                    listView,
                    LinearLayout.LayoutParams(
                        LinearLayout.LayoutParams.MATCH_PARENT,
                        0,
                        1f,
                    ),
                )
                addView(
                    applyButton,
                    LinearLayout.LayoutParams(
                        LinearLayout.LayoutParams.MATCH_PARENT,
                        LinearLayout.LayoutParams.WRAP_CONTENT,
                    ),
                )
            }
        setContentView(root)

        Thread {
            val themes = ThemeCatalog.load()
            val current = switcher.current()
            runOnUiThread {
                currentId = current
                adapter.clear()
                adapter.addAll(themes)
                val index = themes.indexOfFirst { it.id == current }
                if (index >= 0) listView.setItemChecked(index, true)
            }
        }.start()
    }

    private fun onApplyClicked() {
        val position = listView.checkedItemPosition
        if (position == AbsListView.INVALID_POSITION) return
        val theme = adapter.getItem(position) ?: return

        applyButton.isEnabled = false
        Thread {
            val ok = switcher.set(theme.id)
            runOnUiThread {
                applyButton.isEnabled = true
                if (ok) {
                    currentId = theme.id
                    adapter.notifyDataSetChanged()
                }
                Toast
                    .makeText(
                        this,
                        if (ok) "Applied ${theme.name}" else "Failed to apply ${theme.name}",
                        Toast.LENGTH_SHORT,
                    ).show()
            }
        }.start()
    }

    private inner class ThemeAdapter(
        activity: Activity,
    ) : ArrayAdapter<Theme>(activity, 0) {
        override fun getView(
            position: Int,
            convertView: View?,
            parent: ViewGroup,
        ): View {
            val theme = getItem(position) ?: return LinearLayout(context)
            val row =
                LinearLayout(context).apply {
                    orientation = LinearLayout.HORIZONTAL
                    gravity = Gravity.CENTER_VERTICAL
                    val pad = (8 * resources.displayMetrics.density).toInt()
                    setPadding(pad, pad, pad, pad)
                }

            val label = if (theme.id == currentId) "• ${theme.name}" else theme.name
            row.addView(
                TextView(context).apply { text = label },
                LinearLayout.LayoutParams(
                    0,
                    LinearLayout.LayoutParams.WRAP_CONTENT,
                    1f,
                ),
            )

            val swatchSize = (24 * resources.displayMetrics.density).toInt()
            val swatchMargin = (4 * resources.displayMetrics.density).toInt()
            for (hex in listOf(theme.accent, theme.background, theme.foreground)) {
                val swatch =
                    View(context).apply {
                        setBackgroundColor(
                            try {
                                Color.parseColor(hex)
                            } catch (e: IllegalArgumentException) {
                                Color.GRAY
                            },
                        )
                    }
                val params = LinearLayout.LayoutParams(swatchSize, swatchSize)
                params.marginStart = swatchMargin
                row.addView(swatch, params)
            }

            return row
        }
    }
}

package org.omarchy.sample

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import org.omarchy.theme.sdk.OmarchyTheme
import org.omarchy.theme.sdk.compose.omarchyColorScheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MaterialTheme(colorScheme = omarchyColorScheme()) {
                sampleScreen()
            }
        }
    }
}

@Composable
private fun sampleScreen() {
    val ctx = LocalContext.current
    val theme by remember(ctx) { OmarchyTheme.flow(ctx) }.collectAsStateWithLifecycle(initialValue = null)
    val colorScheme = MaterialTheme.colorScheme

    Surface(modifier = Modifier.fillMaxSize(), color = colorScheme.background) {
        Column(modifier = Modifier.padding(24.dp)) {
            Text(text = theme?.name ?: "Material You", color = colorScheme.onBackground)
            Row(
                modifier = Modifier.fillMaxWidth().padding(top = 16.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                listOf(
                    colorScheme.primary,
                    colorScheme.background,
                    colorScheme.onBackground,
                    colorScheme.error,
                    colorScheme.secondary,
                    colorScheme.tertiary,
                ).forEach { swatch: Color ->
                    Surface(
                        modifier = Modifier.weight(1f).aspectRatio(1f),
                        color = swatch,
                    ) {}
                }
            }
        }
    }
}

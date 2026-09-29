plugins {
    alias(libs.plugins.android.library)
}

android {
    namespace = "org.omarchy.theme.sdk"
    compileSdk = libs.versions.compileSdk.get().toInt()

    defaultConfig {
        minSdk = libs.versions.minSdk.get().toInt()
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    testOptions {
        unitTests.isIncludeAndroidResources = true
        unitTests.all {
            // Robolectric 4.17 on JDK 17+: https://robolectric.org/getting-started/
            // ("Running with Java 17 and higher").
            it.jvmArgs(
                "--add-opens=java.base/java.lang=ALL-UNNAMED",
                "--add-opens=java.base/java.util=ALL-UNNAMED",
                "--add-opens=java.base/java.io=ALL-UNNAMED",
                "--add-opens=java.base/java.net=ALL-UNNAMED",
                "--add-opens=java.base/java.security=ALL-UNNAMED",
                // SDK 37 on JDK 21: AndroidInterceptors$FileDescriptorInterceptor reaches
                // jdk.internal.access.SharedSecrets, which java.base does not export to the
                // unnamed module by default -> IllegalAccessException at
                // AndroidInterceptors.java:88 / Reflection.java:394. Confirmed root cause and
                // fix in robolectric/robolectric#11434 ("SDK 37 throws IllegalAccessException")
                // and in Robolectric's own build config (jvmArgs list), see
                // https://github.com/robolectric/robolectric/blob/26d5dc6063e1c87919d1f85d4ee6d4250241c624/build-logic/convention/src/main/java/org/robolectric/gradle/TestTaskConfiguration.kt#L58-L79
                "--add-opens=java.base/jdk.internal.access=ALL-UNNAMED",
            )
            it.testLogging {
                exceptionFormat = org.gradle.api.tasks.testing.logging.TestExceptionFormat.FULL
                events("failed")
            }
        }
    }
}

// AGP 9.4 built-in Kotlin (org.jetbrains.kotlin.android not applied):
// https://developer.android.com/build/migrate-to-built-in-kotlin
kotlin {
    compilerOptions {
        jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17)
    }
}

dependencies {
    implementation(libs.androidx.core.ktx)
    implementation(libs.kotlinx.coroutines.android)

    testImplementation(libs.junit)
    testImplementation(libs.robolectric)
    testImplementation(libs.androidx.test.core)
}

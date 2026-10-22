import java.io.FileInputStream
import java.util.Properties

plugins {
    id("com.android.application")
    // START: FlutterFire Configuration
    id("com.google.gms.google-services")
    // END: FlutterFire Configuration
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
}

// Configuración de firma de release (checklist de producción, punto 1).
// `key.properties` NO se versiona (ver android/.gitignore); si no existe
// en esta máquina (p. ej. un checkout nuevo sin el keystore), el build
// release cae de vuelta al keystore de debug para no romper
// `flutter run --release` en otros entornos de desarrollo.
val keystoreProperties = Properties()
val keystorePropertiesFile = rootProject.file("key.properties")
val hasReleaseKeystore = keystorePropertiesFile.exists()
if (hasReleaseKeystore) {
    keystoreProperties.load(FileInputStream(keystorePropertiesFile))
}

android {
    namespace = "cl.ogb.seguimientoglucosa.app"
    compileSdk = flutter.compileSdkVersion
    ndkVersion = flutter.ndkVersion

    compileOptions {
        // Habilita el desugaring de la biblioteca core de Java, exigido por
        // `flutter_local_notifications` (>=10) para programar notificaciones
        // con compatibilidad hacia atrás (roadmap punto 17, Fase B).
        isCoreLibraryDesugaringEnabled = true
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    defaultConfig {
        applicationId = "cl.ogb.seguimientoglucosa.app"
        // You can update the following values to match your application needs.
        // For more information, see: https://flutter.dev/to/review-gradle-config.
        // minSdk 26 (en vez de flutter.minSdkVersion) porque lo exige el
        // plugin `health` (Health Connect/HealthKit, roadmap punto 15).
        minSdk = 26
        targetSdk = flutter.targetSdkVersion
        versionCode = flutter.versionCode
        versionName = flutter.versionName
        // Exigido junto con el desugaring de arriba.
        multiDexEnabled = true
    }

    signingConfigs {
        if (hasReleaseKeystore) {
            create("release") {
                storeFile = file(keystoreProperties.getProperty("storeFile"))
                storePassword = keystoreProperties.getProperty("storePassword")
                keyAlias = keystoreProperties.getProperty("keyAlias")
                keyPassword = keystoreProperties.getProperty("keyPassword")
            }
        }
    }

    buildTypes {
        release {
            // Usa el keystore de release real (android/key.properties,
            // no versionado) cuando esté disponible en la máquina; si
            // no, cae de vuelta al keystore de debug para no romper
            // `flutter run --release` en checkouts sin el keystore.
            signingConfig = if (hasReleaseKeystore) {
                signingConfigs.getByName("release")
            } else {
                signingConfigs.getByName("debug")
            }
        }
    }
}

kotlin {
    compilerOptions {
        jvmTarget = org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17
    }
}

flutter {
    source = "../.."
}

dependencies {
    // Requerida por `isCoreLibraryDesugaringEnabled` de arriba.
    coreLibraryDesugaring("com.android.tools:desugar_jdk_libs:2.1.4")
}

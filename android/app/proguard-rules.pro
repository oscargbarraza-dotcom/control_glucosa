# Reglas ProGuard/R8 propias del proyecto (checklist de producción,
# punto 9).
#
# El build `release` ya habilita minifyEnabled/shrinkResources
# automáticamente a través del Flutter Gradle Plugin (sin que este
# archivo tenga que activarlo explícitamente); ver comentario en
# android/app/build.gradle.kts. Ese plugin agrega además, por cada
# dependencia Android de los plugins Flutter usados (firebase_auth,
# cloud_firestore, firebase_core, health, flutter_local_notifications,
# google_sign_in, sqflite, url_launcher, flutter_timezone,
# device_info_plus), las reglas "consumer" que cada librería publica por
# su cuenta (`exportReleaseConsumerProguardFiles`), que es lo que de
# hecho evita que R8 rompa esas dependencias. Ninguna de ellas requiere
# hoy una regla `-keep` adicional en este archivo (confirmado con
# `flutter build apk --release`: sin warnings de "Missing class" ni
# reglas faltantes).
#
# Este archivo queda como punto de extensión para el día en que se
# agregue una librería que sí la necesite (por ejemplo, alguna que use
# reflexión directa sobre clases Kotlin/Java propias de este proyecto,
# cosa que hoy no ocurre: toda la serialización hacia Firestore pasa por
# Map<String, Object?> genéricos desde Dart, nunca por POJOs Android
# anotados).

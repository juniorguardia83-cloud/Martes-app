[app]
title = Martes
package.name = martes
package.domain = com.juniorguardia83
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 0.1.0
requirements = python3,kivy,requests,pyjnius
orientation = portrait
fullscreen = 0

# Permisos requeridos para consultar el servidor y abrir aplicaciones.
android.permissions = INTERNET, QUERY_ALL_PACKAGES
android.api = 35
android.minapi = 23
android.archs = arm64-v8a, armeabi-v7a
android.accept_sdk_license = True
android.allow_backup = True
android.debug_artifact = apk
android.release_artifact = aab

[buildozer]
log_level = 2
warn_on_root = 1

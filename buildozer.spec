[app]
title = Martes
package.name = martes
package.domain = com.juniorguardia83
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
source.exclude_dirs = tests,bin,.github,.git,.buildozer,__pycache__
version = 0.3.0
requirements = python3==3.11.5,hostpython3==3.11.5,kivy==2.3.0,pyjnius
orientation = portrait
fullscreen = 0

# INTERNET: hablar con Ollama y Wikipedia.
# QUERY_ALL_PACKAGES: ver qué apps hay instaladas para poder abrirlas.
android.permissions = INTERNET, QUERY_ALL_PACKAGES

# Versiones estables y probadas con python-for-android.
android.api = 33
android.minapi = 21
android.ndk = 25b
android.ndk_api = 21
android.archs = arm64-v8a
android.accept_sdk_license = True
android.allow_backup = True
android.debug_artifact = apk

# python-for-android estable (usa Python 3.11 y es compatible con Kivy 2.3.0).
p4a.branch = v2024.01.21

[buildozer]
log_level = 2
warn_on_root = 0

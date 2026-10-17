"""Funciones que solo existen dentro de Android.

En la PC (o en las pruebas) este módulo se desactiva solo: ANDROID_AVAILABLE
queda en False y las funciones devuelven valores vacíos.
"""
import unicodedata

try:
    from jnius import autoclass

    PythonActivity = autoclass("org.kivy.android.PythonActivity")
    PackageManager = autoclass("android.content.pm.PackageManager")
    ANDROID_AVAILABLE = True
except Exception:
    autoclass = None
    PythonActivity = None
    PackageManager = None
    ANDROID_AVAILABLE = False


def normalizar(texto):
    """Minúsculas y sin acentos, para comparar 'cámara' con 'camara'."""
    sin_acentos = unicodedata.normalize("NFD", texto)
    sin_acentos = "".join(c for c in sin_acentos if unicodedata.category(c) != "Mn")
    return sin_acentos.lower().strip()


def pedir_permisos():
    if not ANDROID_AVAILABLE:
        return
    try:
        from android.permissions import Permission, request_permissions

        request_permissions([Permission.INTERNET])
    except Exception:
        pass


def obtener_apps_instaladas():
    """Devuelve {nombre_visible: paquete} de las apps instaladas."""
    if not ANDROID_AVAILABLE:
        return {}
    try:
        contexto = PythonActivity.mActivity
        administrador = contexto.getPackageManager()
        aplicaciones = administrador.getInstalledApplications(
            PackageManager.GET_META_DATA
        )
        resultado = {}
        for aplicacion in aplicaciones.toArray():
            nombre = str(administrador.getApplicationLabel(aplicacion))
            resultado[nombre] = str(aplicacion.packageName)
        return resultado
    except Exception:
        return {}


def buscar_app(nombre_app, apps_dict):
    """Busca primero coincidencia exacta y luego parcial. Devuelve (nombre, paquete)."""
    buscado = normalizar(nombre_app)
    if not buscado:
        return None
    parcial = None
    for nombre, paquete in apps_dict.items():
        candidato = normalizar(nombre)
        if candidato == buscado:
            return nombre, paquete
        if parcial is None and buscado in candidato:
            parcial = (nombre, paquete)
    return parcial


def abrir_app(nombre_app, apps_dict):
    if not ANDROID_AVAILABLE:
        return "Abrir apps solo funciona dentro del teléfono."
    encontrada = buscar_app(nombre_app, apps_dict)
    if not encontrada:
        return f"No encontré una app llamada {nombre_app}."
    nombre, paquete = encontrada
    try:
        contexto = PythonActivity.mActivity
        intento = contexto.getPackageManager().getLaunchIntentForPackage(paquete)
        if intento:
            contexto.startActivity(intento)
            return f"Abriendo {nombre}..."
        return f"{nombre} no se puede abrir directamente."
    except Exception as error:
        return f"No pude abrir {nombre}: {error}"


def http_get_java(url, cabeceras, timeout):
    """Respaldo para HTTPS: usa la red de Android, que ya conoce los certificados."""
    if not ANDROID_AVAILABLE:
        raise OSError("Respaldo de red no disponible fuera de Android")
    URL = autoclass("java.net.URL")
    conexion = URL(url).openConnection()
    conexion.setConnectTimeout(int(timeout * 1000))
    conexion.setReadTimeout(int(timeout * 1000))
    for clave, valor in cabeceras.items():
        conexion.setRequestProperty(clave, valor)
    codigo = conexion.getResponseCode()
    if codigo >= 400:
        raise OSError(f"HTTP {codigo}")
    Scanner = autoclass("java.util.Scanner")
    lector = Scanner(conexion.getInputStream(), "UTF-8").useDelimiter("\\A")
    return str(lector.next()) if lector.hasNext() else ""

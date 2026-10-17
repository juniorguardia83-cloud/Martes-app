"""Lógica de Martes sin pantalla: memoria, red, Wikipedia y el modelo (Ollama).

No importa Kivy, así se puede probar en cualquier computadora.
Usa solo la librería estándar de Python (nada de 'requests').
"""
import http.client
import json
import os
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request

import androide

# Ollama corriendo en el mismo teléfono (Termux) escucha en 127.0.0.1.
# Si Ollama está en otro equipo, escribe en la app: url http://IP:11434
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"
MODEL_NAME = "martes"

WIKI_API = "https://es.wikipedia.org/w/api.php"
WIKI_RESUMEN = "https://es.wikipedia.org/api/rest_v1/page/summary/"
WIKI_HEADERS = {"User-Agent": "MartesApp/0.3 (asistente personal)"}

PERSONALIDAD = (
    "Eres Martes, el asistente virtual personal de tu dueño. "
    "Hablas en español, con cercanía y un toque de humor, sin ser pesado. "
    "Respondes corto y claro. Si no sabes algo, lo dices en vez de inventar. "
    "Tomas la iniciativa: si ves una mejor opción, la propones. "
    "Usa lo que sabes del usuario cuando ayude, sin repetirlo todo el tiempo."
)

MAX_MENSAJES_GUARDADOS = 500
MENSAJES_EN_CONTEXTO = 12
TURNOS_EN_CONTEXTO = 6
MAX_PALABRAS_CONSULTA = 12

PREFIJOS_FACTUALES = (
    "que es", "qué es", "quien es", "quién es", "quien fue", "quién fue",
    "que fue", "qué fue", "que son", "qué son", "cual es", "cuál es",
    "cuando fue", "cuándo fue", "donde queda", "dónde queda", "donde esta",
    "dónde está", "cuantos", "cuántos", "cuantas", "cuántas", "busca",
)

ERRORES_RED = (OSError, ValueError, http.client.HTTPException)


# ---------------------------------------------------------------------------
# Memoria
# ---------------------------------------------------------------------------

class Memoria:
    """Guarda automáticamente todo lo que dice el usuario en un archivo JSON."""

    def __init__(self, carpeta):
        os.makedirs(carpeta, exist_ok=True)
        self.ruta = os.path.join(carpeta, "memoria_martes.json")
        self.datos = {"url": DEFAULT_OLLAMA_URL, "mensajes": [], "turnos": []}
        self.cargar()

    def cargar(self):
        try:
            with open(self.ruta, "r", encoding="utf-8") as archivo:
                guardado = json.load(archivo)
            if isinstance(guardado, dict):
                self.datos.update(guardado)
        except (OSError, ValueError):
            pass

    def guardar(self):
        try:
            with open(self.ruta, "w", encoding="utf-8") as archivo:
                json.dump(self.datos, archivo, ensure_ascii=False)
        except OSError:
            pass

    @property
    def url(self):
        return self.datos.get("url") or DEFAULT_OLLAMA_URL

    @url.setter
    def url(self, valor):
        self.datos["url"] = valor
        self.guardar()

    def recordar_usuario(self, texto):
        self.datos["mensajes"].append({"t": int(time.time()), "texto": texto})
        self.datos["mensajes"] = self.datos["mensajes"][-MAX_MENSAJES_GUARDADOS:]
        self.guardar()

    def registrar_turno(self, rol, texto):
        self.datos["turnos"].append({"rol": rol, "texto": texto})
        self.datos["turnos"] = self.datos["turnos"][-(TURNOS_EN_CONTEXTO * 2):]
        self.guardar()

    def contexto_usuario(self):
        recientes = self.datos["mensajes"][-MENSAJES_EN_CONTEXTO:]
        return [m["texto"] for m in recientes]

    def olvidar_todo(self):
        url = self.url
        self.datos = {"url": url, "mensajes": [], "turnos": []}
        self.guardar()


# ---------------------------------------------------------------------------
# Red (solo librería estándar)
# ---------------------------------------------------------------------------

def _contexto_ssl():
    """En Android Python no trae certificados: usamos los del sistema."""
    certificados = "/system/etc/security/cacerts"
    try:
        if os.path.isdir(certificados):
            return ssl.create_default_context(capath=certificados)
    except Exception:
        pass
    return ssl.create_default_context()


def _http(url, datos=None, cabeceras=None, timeout=15):
    """Devuelve el texto de la respuesta. Lanza OSError (o similar) si falla."""
    cuerpo = None if datos is None else json.dumps(datos).encode("utf-8")
    cabeceras = dict(cabeceras or {})
    if cuerpo is not None:
        cabeceras["Content-Type"] = "application/json"
    peticion = urllib.request.Request(url, data=cuerpo, headers=cabeceras)
    es_https = url.lower().startswith("https")
    contexto = _contexto_ssl() if es_https else None
    try:
        with urllib.request.urlopen(peticion, timeout=timeout, context=contexto) as r:
            return r.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as error:
        problema_ssl = isinstance(getattr(error, "reason", None), ssl.SSLError)
        if es_https and cuerpo is None and problema_ssl and androide.ANDROID_AVAILABLE:
            return androide.http_get_java(url, cabeceras, timeout)
        raise


def http_get_json(url, cabeceras=None, timeout=15, params=None):
    if params:
        url = url + "?" + urllib.parse.urlencode(params)
    return json.loads(_http(url, cabeceras=cabeceras, timeout=timeout))


def http_post_json(url, datos, timeout=120):
    return json.loads(_http(url, datos=datos, timeout=timeout))


# ---------------------------------------------------------------------------
# Wikipedia
# ---------------------------------------------------------------------------

def es_consulta_factual(texto):
    t = texto.lower().strip().lstrip("¿")
    if len(t.split()) > MAX_PALABRAS_CONSULTA:
        return False
    return t.startswith(PREFIJOS_FACTUALES)


def limpiar_consulta(texto):
    t = texto.strip().lstrip("¿").rstrip("?!. ")
    patron = (
        r"^(busca(me)?( en wikipedia)?|que es|qué es|que son|qué son|quien es|"
        r"quién es|quien fue|quién fue|que fue|qué fue|cual es|cuál es|"
        r"cuando fue|cuándo fue|donde queda|dónde queda|donde esta|dónde está|"
        r"cuantos|cuántos|cuantas|cuántas)\s+"
    )
    t = re.sub(patron, "", t, flags=re.IGNORECASE)
    t = re.sub(r"^(el|la|los|las|un|una|de|del)\s+", "", t, flags=re.IGNORECASE)
    return t.strip()


def buscar_wikipedia(consulta):
    """Devuelve (titulo, resumen) o None si no encuentra nada."""
    if not consulta:
        return None
    try:
        resultado = http_get_json(
            WIKI_API,
            WIKI_HEADERS,
            10,
            {
                "action": "opensearch",
                "search": consulta,
                "limit": 1,
                "namespace": 0,
                "format": "json",
            },
        )
        titulos = resultado[1]
        if not titulos:
            return None
        titulo = titulos[0]
        datos = http_get_json(
            WIKI_RESUMEN + urllib.parse.quote(titulo.replace(" ", "_"), safe=""),
            WIKI_HEADERS,
            10,
        )
        extracto = datos.get("extract", "").strip()
        return (titulo, extracto) if extracto else None
    except (*ERRORES_RED, IndexError, KeyError, TypeError, AttributeError):
        return None


# ---------------------------------------------------------------------------
# Martes (modelo)
# ---------------------------------------------------------------------------

def construir_mensajes(memoria, texto, wiki=None):
    sistema = PERSONALIDAD
    recuerdos = memoria.contexto_usuario()
    if recuerdos:
        lista = "\n".join(f"- {r}" for r in recuerdos)
        sistema += "\n\nCosas que el usuario te dijo antes:\n" + lista
    if wiki:
        titulo, extracto = wiki
        sistema += (
            f"\n\nInformación de Wikipedia sobre «{titulo}»:\n{extracto}\n"
            "Responde usando esa información, con tus palabras y breve. "
            "Si no tiene relación con la pregunta, ignórala."
        )

    mensajes = [{"role": "system", "content": sistema}]
    for turno in memoria.datos["turnos"]:
        mensajes.append({"role": turno["rol"], "content": turno["texto"]})
    mensajes.append({"role": "user", "content": texto})
    return mensajes


def consultar_ollama(memoria, texto, wiki=None):
    url = f"{memoria.url.rstrip('/')}/api/chat"
    payload = {
        "model": MODEL_NAME,
        "messages": construir_mensajes(memoria, texto, wiki),
        "stream": False,
    }
    datos = http_post_json(url, payload, timeout=180)
    contenido = datos.get("message", {}).get("content", "").strip()
    return contenido or "No tengo respuesta para eso."


def cerebro_disponible(memoria):
    """True si el modelo (Ollama) responde en la dirección configurada."""
    try:
        http_get_json(f"{memoria.url.rstrip('/')}/api/tags", timeout=3)
        return True
    except ERRORES_RED:
        return False


def preguntar_a_martes(memoria, texto):
    wiki = None
    if es_consulta_factual(texto):
        wiki = buscar_wikipedia(limpiar_consulta(texto))

    try:
        respuesta = consultar_ollama(memoria, texto, wiki)
    except (*ERRORES_RED, AttributeError):
        if wiki:
            titulo, extracto = wiki
            respuesta = f"{extracto}\n(Wikipedia: {titulo})"
        else:
            return (
                "No pude hablar con mi cerebro (Ollama). Revisa que esté "
                f"encendido en {memoria.url}. Puedes cambiar la dirección "
                "escribiendo: url http://127.0.0.1:11434"
            )

    memoria.registrar_turno("user", texto)
    memoria.registrar_turno("assistant", respuesta)
    return respuesta

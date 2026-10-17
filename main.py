import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor

import traceback

try:
    import requests

    RequestError = requests.RequestException
    REQUESTS_ERROR = None
except Exception:
    requests = None
    RequestError = Exception
    REQUESTS_ERROR = traceback.format_exc()

from kivy.app import App
from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput


# Ollama corriendo en el mismo teléfono (Termux) escucha en 127.0.0.1.
# Si Ollama está en otro equipo, escribe en la app: url http://IP:11434
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"
MODEL_NAME = "martes"

WIKI_API = "https://es.wikipedia.org/w/api.php"
WIKI_RESUMEN = "https://es.wikipedia.org/api/rest_v1/page/summary/"
WIKI_HEADERS = {"User-Agent": "MartesApp/0.2 (asistente personal)"}

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

PREFIJOS_FACTUALES = (
    "que es", "qué es", "quien es", "quién es", "quien fue", "quién fue",
    "que fue", "qué fue", "que son", "qué son", "cual es", "cuál es",
    "cuando", "cuándo", "donde queda", "dónde queda", "donde esta",
    "dónde está", "cuantos", "cuántos", "cuantas", "cuántas", "busca",
)


try:
    from jnius import autoclass
    from android.permissions import request_permissions, Permission

    PythonActivity = autoclass("org.kivy.android.PythonActivity")
    PackageManager = autoclass("android.content.pm.PackageManager")
    ANDROID_AVAILABLE = True
except Exception:
    ANDROID_AVAILABLE = False


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
# Wikipedia
# ---------------------------------------------------------------------------

def es_consulta_factual(texto):
    t = texto.lower().strip().lstrip("¿")
    return t.startswith(PREFIJOS_FACTUALES)


def limpiar_consulta(texto):
    t = texto.strip().lstrip("¿").rstrip("?!. ")
    patron = (
        r"^(busca(me)?( en wikipedia)?|que es|qué es|que son|qué son|quien es|"
        r"quién es|quien fue|quién fue|que fue|qué fue|cual es|cuál es|"
        r"cuando|cuándo|donde queda|dónde queda|donde esta|dónde está|"
        r"cuantos|cuántos|cuantas|cuántas)\s+"
    )
    t = re.sub(patron, "", t, flags=re.IGNORECASE)
    t = re.sub(r"^(el|la|los|las|un|una|de|del)\s+", "", t, flags=re.IGNORECASE)
    return t.strip()


def buscar_wikipedia(consulta):
    """Devuelve (titulo, resumen) o None si no encuentra nada."""
    if not consulta or requests is None:
        return None
    try:
        busqueda = requests.get(
            WIKI_API,
            params={
                "action": "opensearch",
                "search": consulta,
                "limit": 1,
                "namespace": 0,
                "format": "json",
            },
            headers=WIKI_HEADERS,
            timeout=10,
        )
        busqueda.raise_for_status()
        titulos = busqueda.json()[1]
        if not titulos:
            return None
        titulo = titulos[0]
        resumen = requests.get(
            WIKI_RESUMEN + requests.utils.quote(titulo.replace(" ", "_"), safe=""),
            headers=WIKI_HEADERS,
            timeout=10,
        )
        resumen.raise_for_status()
        extracto = resumen.json().get("extract", "").strip()
        if not extracto:
            return None
        return titulo, extracto
    except (RequestError, ValueError, IndexError):
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
            "Responde usando esa información, con tus palabras y breve."
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
    respuesta = requests.post(url, json=payload, timeout=120)
    respuesta.raise_for_status()
    contenido = respuesta.json().get("message", {}).get("content", "").strip()
    return contenido or "No tengo respuesta para eso."


def preguntar_a_martes(memoria, texto):
    if requests is None:
        return (
            "No pude cargar el módulo de internet (requests). Detalle:\n"
            + (REQUESTS_ERROR or "")[-600:]
        )

    wiki = None
    if es_consulta_factual(texto):
        wiki = buscar_wikipedia(limpiar_consulta(texto))

    try:
        respuesta = consultar_ollama(memoria, texto, wiki)
    except RequestError:
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


# ---------------------------------------------------------------------------
# Apps de Android
# ---------------------------------------------------------------------------

def obtener_apps_instaladas():
    """Devuelve {nombre_visible: paquete} cuando se ejecuta en Android."""
    if not ANDROID_AVAILABLE:
        return {}

    try:
        context = PythonActivity.mActivity
        package_manager = context.getPackageManager()
        aplicaciones = package_manager.getInstalledApplications(
            PackageManager.GET_META_DATA
        )
        resultado = {}
        for aplicacion in aplicaciones.toArray():
            nombre = str(package_manager.getApplicationLabel(aplicacion))
            resultado[nombre.lower()] = str(aplicacion.packageName)
        return resultado
    except Exception:
        return {}


def abrir_app(nombre_app, apps_dict):
    if not ANDROID_AVAILABLE:
        return "Martes: Abrir apps solo funciona dentro del teléfono."
    for nombre, paquete in apps_dict.items():
        if nombre_app.lower() in nombre:
            try:
                context = PythonActivity.mActivity
                intent = context.getPackageManager().getLaunchIntentForPackage(paquete)
                if intent:
                    context.startActivity(intent)
                    return f"Martes: Abriendo {nombre}..."
            except Exception as error:
                return f"Martes: No pude abrir {nombre}: {error}"
    return f"Martes: No encontré una app llamada {nombre_app}."


# ---------------------------------------------------------------------------
# Interfaz
# ---------------------------------------------------------------------------

class MartesApp(App):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.apps_dict = {}
        self.memoria = None

    def build(self):
        self.title = "Martes"
        try:
            return self._construir_interfaz()
        except Exception:
            return self._pantalla_error(traceback.format_exc())

    def _pantalla_error(self, detalle):
        """Muestra el error en pantalla en vez de cerrar la app."""
        caja = BoxLayout(orientation="vertical", padding=12, spacing=8)
        caja.add_widget(
            Label(
                text="Martes tuvo un error al iniciar.\nToma captura de esta pantalla.",
                size_hint_y=None,
                height=80,
            )
        )
        caja.add_widget(TextInput(text=detalle, readonly=True))
        return caja

    def _construir_interfaz(self):
        self.memoria = Memoria(self.user_data_dir)
        self.apps_dict = obtener_apps_instaladas()

        root = BoxLayout(orientation="vertical", padding=12, spacing=8)

        header = BoxLayout(size_hint_y=None, height=48, spacing=8)
        header.add_widget(Label(text="Martes", font_size=22, bold=True))
        self.estado = Label(text="Listo", halign="right")
        header.add_widget(self.estado)
        root.add_widget(header)

        self.historial = Label(
            text=(
                "Martes está listo.\n"
                "Escríbeme algo, pregunta cosas ('qué es un volcán'), "
                "o di 'abre cámara'.\n"
                + (
                    f"\n[Aviso] Falló el módulo de internet:\n{REQUESTS_ERROR[-500:]}\n"
                    if REQUESTS_ERROR
                    else ""
                )
            ),
            size_hint_y=None,
            halign="left",
            valign="top",
        )
        self.historial.bind(
            width=lambda _w, ancho: setattr(self.historial, "text_size", (ancho, None)),
            texture_size=lambda _w, tam: setattr(self.historial, "height", tam[1]),
        )
        self.scroll = ScrollView()
        self.scroll.add_widget(self.historial)
        root.add_widget(self.scroll)

        self.entrada = TextInput(
            hint_text="Escríbele a Martes...",
            multiline=False,
            size_hint_y=None,
            height=52,
        )
        self.entrada.bind(on_text_validate=self.enviar)
        root.add_widget(self.entrada)

        controles = BoxLayout(size_hint_y=None, height=52, spacing=8)
        boton = Button(text="Enviar")
        boton.bind(on_release=self.enviar)
        controles.add_widget(boton)
        limpiar = Button(text="Limpiar")
        limpiar.bind(on_release=self.limpiar)
        controles.add_widget(limpiar)
        root.add_widget(controles)

        return root

    def on_start(self):
        if ANDROID_AVAILABLE:
            try:
                request_permissions([Permission.INTERNET])
            except Exception:
                pass

    def enviar(self, *_args):
        try:
            self._enviar_interno()
        except Exception:
            self.agregar_mensaje("Martes: Algo falló:\n" + traceback.format_exc()[-700:])

    def _enviar_interno(self):
        texto = self.entrada.text.strip()
        if not texto:
            return

        self.entrada.text = ""
        self.agregar_mensaje(f"Tú: {texto}")
        minuscula = texto.lower()

        # Comandos locales (no se guardan como recuerdos).
        if minuscula.startswith(("abre ", "abrir ")):
            nombre = texto.split(" ", 1)[1].strip()
            self.agregar_mensaje(abrir_app(nombre, self.apps_dict))
            return

        if minuscula.startswith("url "):
            nueva = texto.split(" ", 1)[1].strip()
            self.memoria.url = nueva
            self.agregar_mensaje(f"Martes: Listo, ahora uso {nueva}")
            return

        if minuscula in ("olvida todo", "borra tu memoria"):
            self.memoria.olvidar_todo()
            self.agregar_mensaje("Martes: Memoria borrada.")
            return

        # Todo lo demás se recuerda automáticamente.
        self.memoria.recordar_usuario(texto)
        self.estado.text = "Pensando..."
        futuro = self.executor.submit(preguntar_a_martes, self.memoria, texto)
        futuro.add_done_callback(self._respuesta_recibida)

    def _respuesta_recibida(self, futuro):
        try:
            respuesta = futuro.result()
        except Exception as error:
            respuesta = f"Algo falló: {error}"
        Clock.schedule_once(lambda _dt: self._mostrar_respuesta(respuesta))

    def _mostrar_respuesta(self, respuesta):
        self.estado.text = "Listo"
        self.agregar_mensaje(f"Martes: {respuesta}")

    def agregar_mensaje(self, mensaje):
        self.historial.text += f"\n{mensaje}\n"
        Clock.schedule_once(lambda _dt: setattr(self.scroll, "scroll_y", 0), 0.1)

    def limpiar(self, *_args):
        self.historial.text = "Martes está listo.\n"

    def on_stop(self):
        self.executor.shutdown(wait=False)


if __name__ == "__main__":
    MartesApp().run()

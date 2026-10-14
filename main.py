from concurrent.futures import ThreadPoolExecutor

import requests
from kivy.app import App
from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput


DEFAULT_OLLAMA_URL = "http://192.168.1.100:11434"
MODEL_NAME = "martes"


try:
    from jnius import autoclass
    from android.permissions import request_permissions, Permission

    PythonActivity = autoclass("org.kivy.android.PythonActivity")
    PackageManager = autoclass("android.content.pm.PackageManager")
    ANDROID_AVAILABLE = True
except ImportError:
    ANDROID_AVAILABLE = False


class MartesApp(App):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.apps_dict = {}

    def build(self):
        self.title = "Martes"
        self.apps_dict = obtener_apps_instaladas()

        root = BoxLayout(orientation="vertical", padding=12, spacing=8)

        header = BoxLayout(size_hint_y=None, height=48, spacing=8)
        header.add_widget(Label(text="Martes", font_size=22, bold=True))
        self.estado = Label(text="Listo", halign="right")
        header.add_widget(self.estado)
        root.add_widget(header)

        self.historial = Label(
            text="Martes está listo.\nEscribe una pregunta o usa ‘abre cámara’.\n",
            size_hint_y=None,
            halign="left",
            valign="top",
        )
        self.historial.bind(texture_size=self.historial.setter("size"))
        scroll = ScrollView()
        scroll.add_widget(self.historial)
        root.add_widget(scroll)

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
                request_permissions([Permission.INTERNET, Permission.QUERY_ALL_PACKAGES])
            except Exception:
                pass

    def enviar(self, *_args):
        texto = self.entrada.text.strip()
        if not texto:
            return

        self.entrada.text = ""
        self.agregar_mensaje(f"Tú: {texto}")

        if texto.lower().startswith(("abre ", "abrir ")):
            nombre = texto.split(" ", 1)[1].strip()
            self.agregar_mensaje(abrir_app(nombre, self.apps_dict))
            return

        self.estado.text = "Consultando..."
        futuro = self.executor.submit(preguntar_a_martes, texto)
        futuro.add_done_callback(self._respuesta_recibida)

    def _respuesta_recibida(self, futuro):
        try:
            respuesta = futuro.result()
        except Exception as error:
            respuesta = (
                "No pude conectarme al servidor de Martes. "
                "Revisa que Ollama esté encendido y que DEFAULT_OLLAMA_URL "
                f"apunte a la IP correcta. Detalle: {error}"
            )
        Clock.schedule_once(lambda _dt: self._mostrar_respuesta(respuesta))

    def _mostrar_respuesta(self, respuesta):
        self.estado.text = "Listo"
        self.agregar_mensaje(f"Martes: {respuesta}")

    def agregar_mensaje(self, mensaje):
        self.historial.text += f"\n{mensaje}\n"

    def limpiar(self, *_args):
        self.historial.text = "Martes está listo.\n"

    def on_stop(self):
        self.executor.shutdown(wait=False)


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


def preguntar_a_martes(mensaje):
    """Consulta Ollama en un equipo accesible desde el teléfono por la red."""
    url = f"{DEFAULT_OLLAMA_URL.rstrip('/')}/api/generate"
    payload = {"model": MODEL_NAME, "prompt": mensaje, "stream": False}
    respuesta = requests.post(url, json=payload, timeout=30)
    respuesta.raise_for_status()
    datos = respuesta.json()
    return datos.get("response", "El servidor no devolvió una respuesta.").strip()


if __name__ == "__main__":
    MartesApp().run()

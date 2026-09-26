from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
import requests
from jnius import autoclass

OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
MODELO = "martes"

PackageManager = autoclass('android.content.pm.PackageManager')
PythonActivity = autoclass('org.kivy.android.PythonActivity')

def obtener_apps_instaladas():
    """Devuelve un diccionario {nombre_visible: paquete} de todas las apps instaladas."""
    context = PythonActivity.mActivity
    pm = context.getPackageManager()
    apps = pm.getInstalledApplications(PackageManager.GET_META_DATA)
    resultado = {}
    for app in apps.toArray():
        nombre = str(pm.getApplicationLabel(app))
        paquete = str(app.packageName)
        resultado[nombre.lower()] = paquete
    return resultado

def abrir_app(nombre_app, apps_dict):
    for nombre, paquete in apps_dict.items():
        if nombre_app.lower() in nombre:
            context = PythonActivity.mActivity
            intent = context.getPackageManager().getLaunchIntentForPackage(paquete)
            if intent:
                context.startActivity(intent)
                return f"Abriendo {nombre}..."
    return f"No encontré una app llamada {nombre_app}."

def preguntar_a_martes(mensaje):
    payload = {"model": MODELO, "prompt": mensaje, "stream": False}
    r = requests.post(OLLAMA_URL, json=payload)
    return r.json()["response"]

class MartesApp(App):
    def build(self):
        self.apps_dict = obtener_apps_instaladas()

        layout = BoxLayout(orientation='vertical', padding=10, spacing=10)

        self.historial = Label(text="Martes está listo.\n", size_hint_y=None)
        self.historial.bind(texture_size=self.historial.setter('size'))
        scroll = ScrollView()
        scroll.add_widget(self.historial)
        layout.add_widget(scroll)

        self.entrada = TextInput(hint_text="Escríbele a Martes...", size_hint_y=None, height=50)
        layout.add_widget(self.entrada)

        boton = Button(text="Enviar", size_hint_y=None, height=50)
        boton.bind(on_press=self.enviar)
        layout.add_widget(boton)

        return layout

    def enviar(self, instance):
        texto = self.entrada.text.strip()
        if not texto:
            return
        self.entrada.text = ""

        if texto.lower().startswith("abre ") or texto.lower().startswith("abrir "):
            app_nombre = texto.lower().replace("abre ", "").replace("abrir ", "").strip()
            respuesta = abrir_app(app_nombre, self.apps_dict)
        else:
            respuesta = preguntar_a_martes(texto)

        self.historial.text += f"\nTú: {texto}\nMartes: {respuesta}\n"

if __name__ == "__main__":
    MartesApp().run()

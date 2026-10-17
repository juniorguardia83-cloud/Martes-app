"""Abre la interfaz de Martes en una pantalla virtual y guarda capturas."""
import os
import sys

os.environ["KIVY_NO_ARGS"] = "1"
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from kivy.config import Config  # noqa: E402

Config.set("graphics", "width", "432")
Config.set("graphics", "height", "888")
Config.set("graphics", "resizable", "0")

from kivy.base import EventLoop  # noqa: E402
from kivy.core.window import Window  # noqa: E402
from kivy.uix.textinput import TextInput  # noqa: E402

import main  # noqa: E402

SALIDA = os.environ.get("PREVIEW_DIR", os.path.join(RAIZ, "preview_out"))
os.makedirs(SALIDA, exist_ok=True)


def avanzar(veces=25):
    for _ in range(veces):
        EventLoop.idle()


def captura(nombre):
    avanzar()
    ruta = os.path.join(SALIDA, nombre)
    Window.screenshot(name=ruta)
    # Window.screenshot agrega un contador al nombre: lo renombramos.
    base, ext = os.path.splitext(ruta)
    for archivo in sorted(os.listdir(SALIDA)):
        if archivo.startswith(os.path.basename(base)) and archivo != nombre:
            os.replace(os.path.join(SALIDA, archivo), ruta)
            break
    print("captura:", ruta)


print("TextInput.keyboard_suggestions:", hasattr(TextInput, "keyboard_suggestions"))
print("TextInput.input_type:", hasattr(TextInput, "input_type"))
print("TextInput.hint_text_color:", hasattr(TextInput, "hint_text_color"))
print("softinput_mode:", Window.softinput_mode)
assert Window.softinput_mode == "resize"

app = main.MartesApp()
raiz = app.build()
assert not isinstance(raiz.children[0], TextInput), "salió la pantalla de error"
Window.add_widget(raiz)
EventLoop.ensure_window()

print("suggestions en la entrada:", getattr(app.entrada, "keyboard_suggestions", "n/a"))
print("input_type en la entrada:", getattr(app.entrada, "input_type", "n/a"))

app._poner_estado("Cerebro conectado", main.VERDE)
app.agregar_mensaje("hola Martes, cómo estás?", True)
app.agregar_mensaje("¡Hola! Aquí estoy, listo para ayudarte. Dime qué necesitas.", False)
app.agregar_mensaje("qué es un volcán", True)
app.agregar_mensaje(
    "Un volcán es una abertura en la corteza terrestre por donde sale lava, "
    "ceniza y gases desde el interior del planeta. Hay volcanes activos, "
    "dormidos y extintos, y algunos forman islas enteras.",
    False,
)
app.agregar_mensaje("abre cámara", True)
app.agregar_mensaje("Abriendo Cámara...", False)
captura("1_chat.png")

# Simula el teclado: la ventana se encoge y el chat + barra deben seguir visibles.
Window.size = (432, 470)
avanzar()
captura("2_con_teclado.png")
entrada_y = app.entrada.to_window(*app.entrada.pos)[1]
print("entrada y (ventana pequeña):", entrada_y, "alto ventana:", Window.height)
assert 0 <= entrada_y < Window.height, "la barra de escribir quedó fuera de pantalla"

Window.size = (432, 888)
app._poner_estado("Sin cerebro", main.ROJO)
app._poner_estado_cerebro(False)
captura("3_sin_cerebro.png")
print("PREVIEW OK")

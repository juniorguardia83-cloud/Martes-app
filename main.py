import math
import traceback
from concurrent.futures import ThreadPoolExecutor

from kivy.animation import Animation
from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Ellipse, Rectangle, RoundedRectangle
from kivy.graphics.texture import Texture
from kivy.metrics import dp, sp
from kivy.properties import ListProperty, NumericProperty
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget

import androide
import cerebro

# Cuando sale el teclado, la ventana se encoge: el chat y la barra de escribir
# quedan siempre visibles encima del teclado.
Window.softinput_mode = "resize"

FONDO_ARRIBA = (0.07, 0.08, 0.20)
FONDO_ABAJO = (0.02, 0.02, 0.07)
ACENTO = (0.33, 0.80, 1.0, 1)
ACENTO_2 = (0.62, 0.42, 1.0, 1)
TEXTO = (0.93, 0.95, 1.0, 1)
TEXTO_SUAVE = (0.62, 0.67, 0.82, 1)
TEXTO_SOBRE_ACENTO = (0.02, 0.05, 0.15, 1)
BURBUJA_MARTES = (0.11, 0.13, 0.27, 0.94)
BURBUJA_USUARIO = (0.27, 0.34, 0.86, 0.96)
BARRA = (0.10, 0.12, 0.24, 0.96)
VELO = (1, 1, 1, 0.10)
VERDE = (0.30, 0.90, 0.60, 1)
AMBAR = (1.0, 0.75, 0.30, 1)
ROJO = (1.0, 0.40, 0.45, 1)

MAX_TEXTO_BURBUJA = 4000


def poner_si_existe(widget, **propiedades):
    """Asigna propiedades opcionales sin romper si esta versión de Kivy no las tiene."""
    for nombre, valor in propiedades.items():
        try:
            setattr(widget, nombre, valor)
        except Exception:
            pass


def fondo_redondeado(widget, color, radio):
    with widget.canvas.before:
        tinte = Color(*color)
        rectangulo = RoundedRectangle(pos=widget.pos, size=widget.size, radius=[radio])
    widget.bind(
        pos=lambda _w, valor: setattr(rectangulo, "pos", valor),
        size=lambda _w, valor: setattr(rectangulo, "size", valor),
    )
    return tinte


def ajustar_texto(etiqueta):
    etiqueta.bind(size=lambda w, tam: setattr(w, "text_size", tam))


# ---------------------------------------------------------------------------
# Widgets propios
# ---------------------------------------------------------------------------

class Fondo(Widget):
    """Degradado oscuro con dos brillos suaves que respiran lento."""

    pulso = NumericProperty(0)
    CAPAS = 7
    ALFA_CAPA = 0.028

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        textura = Texture.create(size=(1, 2), colorfmt="rgb")
        abajo = bytes(int(c * 255) for c in FONDO_ABAJO)
        arriba = bytes(int(c * 255) for c in FONDO_ARRIBA)
        textura.blit_buffer(abajo + arriba, colorfmt="rgb", bufferfmt="ubyte")
        textura.mag_filter = "linear"

        # Cada brillo: (color, centro_x, centro_y, radio) en proporciones de la pantalla.
        self._definiciones = [
            (ACENTO_2, 0.12, 0.88, 0.80),
            (ACENTO, 0.98, 0.22, 0.70),
        ]
        self._brillos = []
        with self.canvas:
            Color(1, 1, 1, 1)
            self._degradado = Rectangle(texture=textura, pos=self.pos, size=self.size)
            for definicion in self._definiciones:
                capas = []
                for _ in range(self.CAPAS):
                    tinte = Color(definicion[0][0], definicion[0][1], definicion[0][2], self.ALFA_CAPA)
                    circulo = Ellipse(pos=(0, 0), size=(1, 1))
                    capas.append((tinte, circulo))
                self._brillos.append(capas)
        self.bind(pos=self._acomodar, size=self._acomodar, pulso=self._respirar)
        self._acomodar()

        ciclo = Animation(pulso=1, duration=6, t="in_out_sine") + Animation(
            pulso=0, duration=6, t="in_out_sine"
        )
        ciclo.repeat = True
        ciclo.start(self)

    def _acomodar(self, *_args):
        self._degradado.pos = self.pos
        self._degradado.size = self.size
        ancho, alto = self.size
        for definicion, capas in zip(self._definiciones, self._brillos):
            _color, cx, cy, radio = definicion
            base = radio * ancho
            for indice, (_tinte, circulo) in enumerate(capas):
                r = base * (1 - 0.85 * indice / self.CAPAS)
                centro_x = self.x + cx * ancho
                centro_y = self.y + cy * alto
                circulo.pos = (centro_x - r, centro_y - r)
                circulo.size = (2 * r, 2 * r)

    def _respirar(self, *_args):
        factor = 0.75 + 0.5 * self.pulso
        for capas in self._brillos:
            for tinte, _circulo in capas:
                tinte.a = self.ALFA_CAPA * factor


class Punto(Widget):
    """Puntito de color que indica el estado."""

    color = ListProperty(AMBAR)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        with self.canvas:
            self._tinte = Color(*self.color)
            self._circulo = Ellipse(pos=self.pos, size=self.size)
        self.bind(pos=self._acomodar, size=self._acomodar, color=self._pintar)

    def _acomodar(self, *_args):
        self._circulo.pos = self.pos
        self._circulo.size = self.size

    def _pintar(self, _widget, valor):
        self._tinte.rgba = valor


class BotonRedondo(Button):
    def __init__(self, color_fondo=ACENTO, **kwargs):
        super().__init__(
            background_normal="",
            background_down="",
            background_color=(0, 0, 0, 0),
            **kwargs,
        )
        self._fondo = fondo_redondeado(self, color_fondo, dp(22))
        self._color_fondo = color_fondo
        self.bind(state=self._presionado)

    def _presionado(self, _widget, estado):
        c = self._color_fondo
        self._fondo.rgba = (c[0], c[1], c[2], c[3] * 0.65) if estado == "down" else c


def crear_burbuja(texto, es_usuario):
    """Fila con una burbuja de chat del tamaño justo del texto."""
    texto = texto[:MAX_TEXTO_BURBUJA]
    margen_x, margen_y = dp(14), dp(10)
    limite = Window.width * 0.80 - 2 * margen_x

    etiqueta = Label(
        text=texto,
        color=TEXTO,
        font_size=sp(16),
        halign="left",
        valign="top",
        size_hint=(None, None),
    )
    etiqueta.text_size = (None, None)
    etiqueta.texture_update()
    ancho = etiqueta.texture_size[0]
    if ancho > limite:
        etiqueta.text_size = (limite, None)
        etiqueta.texture_update()
        ancho = limite
    else:
        ancho = math.ceil(ancho) + 2
    alto = etiqueta.texture_size[1]
    etiqueta.size = (ancho, alto)
    etiqueta.text_size = (ancho, alto)

    burbuja = BoxLayout(
        size_hint=(None, None),
        padding=(margen_x, margen_y),
        size=(ancho + 2 * margen_x, alto + 2 * margen_y),
    )
    burbuja.add_widget(etiqueta)
    fondo_redondeado(burbuja, BURBUJA_USUARIO if es_usuario else BURBUJA_MARTES, dp(18))

    fila = AnchorLayout(
        anchor_x="right" if es_usuario else "left",
        size_hint_y=None,
        height=burbuja.height + dp(4),
        padding=(dp(10), 0),
    )
    fila.add_widget(burbuja)
    return fila


# ---------------------------------------------------------------------------
# Aplicación
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
        self.memoria = cerebro.Memoria(self.user_data_dir)
        self.apps_dict = androide.obtener_apps_instaladas()

        raiz = FloatLayout()
        raiz.add_widget(Fondo())
        contenido = BoxLayout(orientation="vertical", spacing=dp(4))
        raiz.add_widget(contenido)

        # --- Cabecera ---
        cabecera = BoxLayout(
            size_hint_y=None, height=dp(56), padding=(dp(16), dp(8)), spacing=dp(8)
        )
        titulo = Label(
            text="MARTES",
            bold=True,
            color=ACENTO,
            font_size=sp(20),
            halign="left",
            valign="middle",
            size_hint_x=None,
            width=dp(96),
        )
        ajustar_texto(titulo)
        cabecera.add_widget(titulo)

        caja_punto = AnchorLayout(size_hint_x=None, width=dp(12))
        self.punto = Punto(size_hint=(None, None), size=(dp(9), dp(9)))
        caja_punto.add_widget(self.punto)
        cabecera.add_widget(caja_punto)

        self.estado = Label(
            text="Conectando...",
            color=TEXTO_SUAVE,
            font_size=sp(13),
            halign="left",
            valign="middle",
        )
        ajustar_texto(self.estado)
        cabecera.add_widget(self.estado)

        caja_limpiar = AnchorLayout(size_hint_x=None, width=dp(84))
        limpiar = BotonRedondo(
            text="Limpiar",
            color_fondo=VELO,
            color=TEXTO,
            font_size=sp(13),
            size_hint=(None, None),
            size=(dp(80), dp(34)),
        )
        limpiar.bind(on_release=self.limpiar)
        caja_limpiar.add_widget(limpiar)
        cabecera.add_widget(caja_limpiar)
        contenido.add_widget(cabecera)

        # --- Chat ---
        self.scroll = ScrollView(
            do_scroll_x=False,
            bar_width=dp(3),
            bar_color=(1, 1, 1, 0.25),
            bar_inactive_color=(1, 1, 1, 0.08),
        )
        self.lista = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            spacing=dp(4),
            padding=(0, dp(8)),
        )
        self.lista.bind(minimum_height=self.lista.setter("height"))
        self.scroll.add_widget(self.lista)
        contenido.add_widget(self.scroll)

        # --- Barra para escribir ---
        barra = BoxLayout(
            size_hint_y=None, height=dp(62), padding=(dp(10), dp(8)), spacing=dp(8)
        )
        campo = BoxLayout(padding=(dp(6), 0))
        fondo_redondeado(campo, BARRA, dp(22))
        self.entrada = TextInput(
            hint_text="Escríbele a Martes...",
            multiline=False,
            background_color=(0, 0, 0, 0),
            foreground_color=TEXTO,
            font_size=sp(16),
            padding=(dp(12), dp(11), dp(12), dp(6)),
        )
        # Autocorrector y sugerencias del teclado activados.
        poner_si_existe(
            self.entrada,
            background_normal="",
            background_active="",
            hint_text_color=TEXTO_SUAVE,
            cursor_color=ACENTO,
            input_type="text",
            keyboard_suggestions=True,
            write_tab=False,
        )
        self.entrada.bind(on_text_validate=self.enviar)
        campo.add_widget(self.entrada)
        barra.add_widget(campo)

        boton = BotonRedondo(
            text="Enviar",
            bold=True,
            color=TEXTO_SOBRE_ACENTO,
            font_size=sp(15),
            size_hint=(None, 1),
            width=dp(84),
        )
        boton.bind(on_release=self.enviar)
        barra.add_widget(boton)
        contenido.add_widget(barra)

        self._mostrar_inicio()
        return raiz

    def _mostrar_inicio(self):
        turnos = self.memoria.datos.get("turnos", [])
        if turnos:
            for turno in turnos:
                self.agregar_mensaje(turno["texto"], turno["rol"] == "user")
        else:
            self.agregar_mensaje(
                "Hola, soy Martes. Escríbeme lo que necesites, pregúntame cosas "
                "(\"qué es un volcán\") o dime \"abre cámara\".",
                False,
            )

    # --- Estado ---
    def _poner_estado(self, texto, color):
        self.estado.text = texto
        self.punto.color = color

    def _poner_estado_cerebro(self, conectado):
        if conectado:
            self._poner_estado("Cerebro conectado", VERDE)
        else:
            self._poner_estado("Sin cerebro", ROJO)
            self.agregar_mensaje(
                "Todavía no tengo cerebro conectado. Abre Termux y escribe "
                "\"ollama serve\", o dime dónde está con: url http://IP:11434",
                False,
            )

    def on_start(self):
        androide.pedir_permisos()
        futuro = self.executor.submit(cerebro.cerebro_disponible, self.memoria)
        futuro.add_done_callback(self._cerebro_revisado)

    def _cerebro_revisado(self, futuro):
        try:
            conectado = futuro.result()
        except Exception:
            conectado = False
        Clock.schedule_once(lambda _dt: self._poner_estado_cerebro(conectado))

    # --- Chat ---
    def enviar(self, *_args):
        try:
            self._enviar_interno()
        except Exception:
            self.agregar_mensaje("Algo falló:\n" + traceback.format_exc()[-700:], False)

    def _enviar_interno(self):
        texto = self.entrada.text.strip()
        if not texto:
            return

        self.entrada.text = ""
        Clock.schedule_once(lambda _dt: setattr(self.entrada, "focus", True), 0.15)
        self.agregar_mensaje(texto, True)
        minuscula = texto.lower()

        # Comandos locales (no se guardan como recuerdos).
        if minuscula.startswith(("abre ", "abrir ")):
            nombre = texto.split(" ", 1)[1].strip()
            self.agregar_mensaje(androide.abrir_app(nombre, self.apps_dict), False)
            return

        if minuscula.startswith("url "):
            nueva = texto.split(" ", 1)[1].strip()
            self.memoria.url = nueva
            self.agregar_mensaje(f"Listo, ahora uso {nueva}", False)
            self._poner_estado("Conectando...", AMBAR)
            futuro = self.executor.submit(cerebro.cerebro_disponible, self.memoria)
            futuro.add_done_callback(self._cerebro_revisado)
            return

        if minuscula in ("olvida todo", "borra tu memoria"):
            self.memoria.olvidar_todo()
            self.agregar_mensaje("Memoria borrada.", False)
            return

        # Todo lo demás se recuerda automáticamente.
        self.memoria.recordar_usuario(texto)
        self._poner_estado("Pensando...", AMBAR)
        futuro = self.executor.submit(cerebro.preguntar_a_martes, self.memoria, texto)
        futuro.add_done_callback(self._respuesta_recibida)

    def _respuesta_recibida(self, futuro):
        try:
            respuesta = futuro.result()
        except Exception as error:
            respuesta = f"Algo falló: {error}"
        Clock.schedule_once(lambda _dt: self._mostrar_respuesta(respuesta))

    def _mostrar_respuesta(self, respuesta):
        self._poner_estado("Listo", VERDE)
        self.agregar_mensaje(respuesta, False)

    def agregar_mensaje(self, texto, es_usuario):
        self.lista.add_widget(crear_burbuja(texto, es_usuario))
        Clock.schedule_once(lambda _dt: setattr(self.scroll, "scroll_y", 0), 0.1)

    def limpiar(self, *_args):
        self.lista.clear_widgets()

    def on_stop(self):
        self.executor.shutdown(wait=False)


if __name__ == "__main__":
    MartesApp().run()

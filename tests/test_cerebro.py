import json
import os
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

import androide  # noqa: E402
import cerebro as c  # noqa: E402

RECIBIDOS = []


class FalsoOllama(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _responder(self, datos):
        cuerpo = json.dumps(datos).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def do_GET(self):
        if self.path == "/api/tags":
            self._responder({"models": [{"name": "martes"}]})
        else:
            self.send_error(404)

    def do_POST(self):
        largo = int(self.headers.get("Content-Length", 0))
        payload = json.loads(self.rfile.read(largo))
        RECIBIDOS.append(payload)
        ultimo = payload["messages"][-1]["content"]
        self._responder({"message": {"content": f"Eco: {ultimo}"}})


def servidor():
    http = HTTPServer(("127.0.0.1", 0), FalsoOllama)
    hilo = threading.Thread(target=http.serve_forever, daemon=True)
    hilo.start()
    return http, f"http://127.0.0.1:{http.server_address[1]}"


def probar_texto():
    assert c.es_consulta_factual("¿Qué es un volcán?")
    assert c.es_consulta_factual("busca Machu Picchu")
    assert not c.es_consulta_factual("hola cómo estás")
    assert not c.es_consulta_factual("cuando tengo hambre me pongo de mal humor y no pienso")
    assert c.limpiar_consulta("¿Qué es un volcán?") == "volcán"
    assert c.limpiar_consulta("quién fue Simón Bolívar") == "Simón Bolívar"
    assert c.limpiar_consulta("busca en wikipedia Machu Picchu") == "Machu Picchu"


def probar_apps():
    apps = {"Cámara": "com.cam", "WhatsApp": "com.whatsapp", "Cámara 360": "com.cam360"}
    assert androide.buscar_app("camara", apps) == ("Cámara", "com.cam")
    assert androide.buscar_app("whats", apps) == ("WhatsApp", "com.whatsapp")
    assert androide.buscar_app("tiktok", apps) is None
    assert androide.abrir_app("camara", apps).startswith("Abrir apps solo")


def probar_memoria():
    with tempfile.TemporaryDirectory() as d:
        mem = c.Memoria(d)
        mem.recordar_usuario("me llamo Junior")
        mem.registrar_turno("user", "hola")
        mem.registrar_turno("assistant", "hola Junior")
        mem2 = c.Memoria(d)
        assert mem2.contexto_usuario() == ["me llamo Junior"]
        assert len(mem2.datos["turnos"]) == 2
        mem2.url = "http://10.0.0.5:11434"
        assert c.Memoria(d).url == "http://10.0.0.5:11434"
        msgs = c.construir_mensajes(mem2, "qué es un volcán", ("Volcán", "Un volcán es..."))
        assert msgs[0]["role"] == "system"
        assert "me llamo Junior" in msgs[0]["content"] and "Volcán" in msgs[0]["content"]
        assert msgs[-1] == {"role": "user", "content": "qué es un volcán"}
        mem2.olvidar_todo()
        otra = c.Memoria(d)
        assert otra.contexto_usuario() == [] and otra.url == "http://10.0.0.5:11434"


def probar_red_real():
    http, url = servidor()
    try:
        with tempfile.TemporaryDirectory() as d:
            mem = c.Memoria(d)
            mem.url = url
            assert c.cerebro_disponible(mem) is True
            respuesta = c.preguntar_a_martes(mem, "hola Martes")
            assert respuesta == "Eco: hola Martes", respuesta
            assert RECIBIDOS[-1]["model"] == "martes" and RECIBIDOS[-1]["stream"] is False
            assert len(mem.datos["turnos"]) == 2

            # Con Wikipedia simulada (no depende de internet)
            original = c.http_get_json

            def falso_get(direccion, cabeceras=None, timeout=15, params=None):
                if "wikipedia" in direccion:
                    if "api.php" in direccion:
                        return ["volcán", ["Volcán"], [""], [""]]
                    return {"extract": "Un volcán es una abertura en la corteza terrestre."}
                return original(direccion, cabeceras, timeout, params)

            c.http_get_json = falso_get
            try:
                r = c.preguntar_a_martes(mem, "qué es un volcán")
                assert r.startswith("Eco:")
                sistema = RECIBIDOS[-1]["messages"][0]["content"]
                assert "abertura en la corteza" in sistema and "me llamo" not in sistema.lower()
            finally:
                c.http_get_json = original
    finally:
        http.shutdown()
        http.server_close()

    # Servidor apagado
    with tempfile.TemporaryDirectory() as d:
        mem = c.Memoria(d)
        mem.url = url  # ya está cerrado
        assert c.cerebro_disponible(mem) is False
        assert "Ollama" in c.preguntar_a_martes(mem, "hola")

        # Ollama caído + Wikipedia disponible -> responde con Wikipedia
        original = c.http_get_json

        def falso_get(direccion, cabeceras=None, timeout=15, params=None):
            if "wikipedia" in direccion:
                if "api.php" in direccion:
                    return ["volcán", ["Volcán"], [""], [""]]
                return {"extract": "Un volcán es una abertura."}
            return original(direccion, cabeceras, timeout, params)

        c.http_get_json = falso_get
        try:
            r = c.preguntar_a_martes(mem, "qué es un volcán")
            assert "abertura" in r and "Wikipedia: Volcán" in r, r
        finally:
            c.http_get_json = original


if __name__ == "__main__":
    probar_texto()
    probar_apps()
    probar_memoria()
    probar_red_real()
    print("TODO OK (lógica)")

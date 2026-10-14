# Martes

Primera versión de una app Android hecha con Kivy. Martes puede:

- Enviar preguntas a un modelo Ollama accesible por la red local.
- Abrir aplicaciones instaladas con comandos como `abre cámara`.
- Mantener el historial de conversación en pantalla.
- Compilar un APK automáticamente con GitHub Actions.

## Conexión con Ollama

El teléfono no puede usar `127.0.0.1` para llegar al Ollama de otra computadora: esa dirección apunta al propio teléfono. Cambia `DEFAULT_OLLAMA_URL` en `main.py` por la IP local del equipo donde corre Ollama, por ejemplo:

```python
DEFAULT_OLLAMA_URL = "http://192.168.1.100:11434"
```

En el equipo servidor, Ollama debe escuchar en la red local, por ejemplo con `OLLAMA_HOST=0.0.0.0:11434`, y el firewall debe permitir el puerto 11434. El teléfono y el equipo deben estar en la misma red Wi-Fi.

## Compilación

Cada push a `main` inicia el workflow **Build APK**. El APK de depuración aparece en la sección **Actions > Build APK > Artifacts** del repositorio.

También puede compilarse localmente con:

```bash
buildozer -v android debug
```

> Para usar Martes desde Internet y no solamente desde la red Wi-Fi, lo recomendable es crear un backend HTTPS autenticado. No conviene exponer Ollama directamente a Internet.

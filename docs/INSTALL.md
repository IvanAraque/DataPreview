# Guía de Instalación

Esta guía te lleva desde una máquina vacía hasta DataPreview funcionando. Está escrita para Windows aunque la mayoría de pasos sirven igual en macOS o Linux.

## 1. Instalar Python

1. Descarga **Python 3.11 o superior** desde [python.org](https://www.python.org/downloads/).
2. Ejecuta el instalador.
3. **Importante (Windows)**: en la primera pantalla marca la casilla **"Add Python to PATH"** antes de pulsar "Install Now".

## 2. Clonar el repositorio

Abre PowerShell (o Símbolo del sistema) y muévete a donde quieras guardar el proyecto:

```powershell
cd C:\Users\TU_USUARIO\Documents
git clone https://github.com/TU_USUARIO/DataPreview.git
cd DataPreview
```

## 3. Crear y activar un entorno virtual

Un entorno virtual aísla las dependencias para que no choquen con otros proyectos.

```powershell
python -m venv .venv
.venv\Scripts\activate
```

(En macOS/Linux: `source .venv/bin/activate`)

Cuando esté activo verás `(.venv)` al principio del prompt.

## 4. Instalar dependencias

```powershell
pip install -r requirements.txt
```

Tarda un par de minutos la primera vez (PySide6 y pyarrow son grandes).

## 5. Ejecutar la app

```powershell
python src/app.py
```

Listo. La app abrirá la pantalla de arrastre — suelta un CSV / XLSX / JSON / Parquet y dale a **Analizar**.

---

## 6. (Opcional) Activar el Asistente IA

DataPreview funciona **sin IA**: la pestaña Asistente IA queda oculta y las recomendaciones del Preview, Limpieza y Custom usan heurísticas. Si quieres activar las funciones inteligentes (recomendaciones priorizadas, análisis por gráfico, detección de problemas de limpieza, chat sobre tus datos), necesitas un servidor local de **Ollama**.

1. Descarga e instala Ollama desde [ollama.com](https://ollama.com/download).
2. Abre una terminal y descarga un modelo (el que usa la app por defecto):
   ```powershell
   ollama pull qwen3:30b
   ```
   Si tu equipo no aguanta ese modelo, sirven también `qwen3:8b`, `llama3.2`, `phi3` u otros que cubran cierta calidad. Si cambias de modelo, edita la línea `self.ai_analyzer = AIAnalyzer(model="qwen3:30b")` en `src/ui/main_window.py`.
3. Asegúrate de que Ollama está corriendo en el puerto por defecto `localhost:11434`. Lo verás en la bandeja del sistema o con:
   ```powershell
   curl http://localhost:11434/api/tags
   ```
4. Reabre la app. En la home verás el indicador "● IA disponible" en verde.

No se envía nada a internet: todas las inferencias ocurren en tu máquina.

---

## 7. (Opcional) Generar el ejecutable `.exe`

Si prefieres un ejecutable que se abra con doble click sin consola:

```powershell
build.bat
```

El script limpia builds anteriores, activa el venv y lanza PyInstaller en modo `--windowed --onefile`. El ejecutable resultante queda en `dist\DataPreview.exe`. Puedes moverlo donde quieras.

**Nota**: el `.exe` no incluye Ollama. Si quieres usar la IA con el ejecutable, Ollama debe estar instalado y corriendo en la máquina destino.

---

## Problemas comunes

- **`pip install` falla con error de compilación**: actualiza pip (`python -m pip install --upgrade pip`) y vuelve a intentar. La mayoría de paquetes traen wheels precompilados, así que no debería ser necesario tener compilador.
- **Al abrir la app la pestaña Asistente IA no aparece**: Ollama no está corriendo o el modelo no se pudo cargar. Comprueba con el `curl` del paso 6.
- **El gráfico de Custom tarda en aparecer la primera vez**: es normal, QtWebEngine inicializa el motor de Chromium la primera vez que se usa.
- **El selector de tamaño en Preview no cambia el tamaño**: actualiza al último commit. Era un bug ya arreglado.

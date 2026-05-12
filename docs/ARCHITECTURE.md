# Arquitectura de DataPreview

## Resumen

DataPreview es una aplicación de escritorio (PySide6 / Qt6) para hacer análisis exploratorio (EDA) de un dataset local. Cuenta con pestañas para entender el dataset (Contexto), detectar problemas (Limpieza), explorar visualmente (Preview), construir gráficos a medida (Custom) y conversar sobre los datos con un modelo de lenguaje local (Asistente IA).

Los principios que rigen el código:

- **No bloquear el hilo de UI**: cualquier operación que pueda tardar (lectura, perfilado, render Plotly, inferencia LLM) corre en un hilo de fondo. La UI se entera vía señales Qt con `Qt.QueuedConnection`.
- **Degradación elegante**: si la IA no está disponible, todas las pestañas siguen funcionando con heurísticas. Si una recomendación AI tarda demasiado, hay watchdogs que caen al fallback automáticamente.
- **Modular por dominio**: `data/` solo sabe de pandas/polars, `charts/` solo sabe de visualización, `ui/` solo sabe de widgets, `core/` orquesta entre dominios.

## Estructura del código

```
src/
├── app.py                  # Entry point (QApplication + tema + MainWindow)
├── settings/
│   └── config.py           # Persistencia de preferencias (tema)
├── i18n/
│   └── translations.py     # Cadenas de UI
├── data/
│   ├── reader.py           # Lectura por chunks de CSV/XLSX/JSON/Parquet
│   ├── profiler.py         # Estadísticas por columna + samples
│   ├── cleaner.py          # Reglas heurísticas (nulos, outliers, cardinalidad)
│   └── ai_analyzer.py      # Cliente Ollama (charts, cleaning, explain, chat)
├── core/
│   └── data_worker.py      # Wrappers QObject de reader/profiler en threads
├── charts/
│   ├── selector.py         # Heurística para elegir gráficos relevantes
│   └── renderer.py         # PyQtGraph: hist, bar, scatter, line
└── ui/
    ├── main_window.py      # Ventana principal, HomeView, orquestación de flujos
    ├── theme.py            # Hojas de estilo claro/oscuro
    ├── context_tab.py      # Cards resumen + tabla de columnas + diccionario
    ├── cleaning_tab.py     # Árbol de recomendaciones (heurísticas + IA)
    ├── preview_tab.py      # Grid de paneles + alternativas + selector tamaño
    ├── advanced_tab.py     # Constructor manual con Plotly + QWebEngineView
    └── ai_tab.py           # Chat markdown con estilo theme-aware
```

## Flujo de carga de un dataset

1. **Selección de archivo (UI)**.
   `HomeView` recibe el path por drag&drop o por click en el área de arrastre (clicable, sustituye al antiguo botón). Opcionalmente el usuario añade un diccionario / descripción de los datos. Indicador "● IA disponible / no disponible" en la esquina inferior derecha.

2. **Lectura por chunks (data + core)**.
   `DataLoaderManager` lanza un `threading.Thread` que invoca `reader.read_dataset(...)`. Para CSV usa `polars.read_csv_batched`, estima total de filas a partir del primer MB del archivo y emite `progress_updated(percent, eta)` periódicamente. Mientras carga se ve la barra de progreso en pantalla.

3. **Perfilado (data + core)**.
   Cuando termina la lectura, `ProfilerManager` lanza otro hilo que ejecuta `profile_dataset` (min, max, n_unique, nulos, samples) y `generate_recommendations` (heurística de limpieza). El resultado llega vía la señal `profile_ready(dict, list)`.

4. **Pintado inmediato de las pestañas ligeras**.
   En `_on_profile_ready` se llena Contexto (cards + tabla + descripción del diccionario si la había) y Limpieza (recomendaciones heurísticas), se preparan los combos del Custom (sin renderizar Plotly aún) y se cambia a la vista de tabs. El usuario ya puede navegar.

5. **Petición de recomendaciones a la IA** (si Ollama está disponible).
   En paralelo arranca:
   - `recommend_charts(profile, context_text, count=10)`: 10 gráficos en JSON, los 6 primeros se mostrarán como principales y el resto como alternativas. Watchdog de 5 minutos; si falla se cae a `select_charts` heurístico (también pide 10 para que haya alternativas en modo auto).
   - `recommend_cleaning(profile, samples, context_text)`: análisis EDA con tipos/formatos/anomalías que se añaden al árbol de Limpieza con badge `[IA]`.
   - `generate_initial_report(profile, context_text)`: reporte conversacional inicial en streaming que aparece en la pestaña Asistente IA.

6. **Render del Preview**.
   Cuando llegan los specs de gráficos (o salta el watchdog), `PreviewTab.update_data` los pinta uno a uno con `QTimer.singleShot` (no bloquea la UI). Cada `ChartPanel` arranca con la descripción que vino del AI; tras pintarse todos, MainWindow dispara un `explain_chart` por cada panel con un `request_id` único — los paneles muestran "Analizando con IA…" hasta que llega su observación.

7. **Pestaña Custom (render lazy)**.
   `AdvancedTab.update_data` solo puebla los combos. El render real de Plotly + carga en `QWebEngineView` se dispara la primera vez que el usuario abre la pestaña (`showEvent`) o cuando pulsa Renderizar. La generación del HTML + `to_html(include_plotlyjs=True)` (Plotly embebido, sin CDN) corre en un `threading.Thread`; mientras se ve un spinner dentro del WebView. Tras el render, MainWindow pide a la IA un `explain_chart` con `request_id="custom"`.

## Pestañas

### Contexto
Cuatro tarjetas con métricas clave (filas, columnas, memoria, número de tipos distintos) + sección plegable con el diccionario de los datos si se aportó + tabla de columnas redimensionable e iconos por tipo de dato (numérico, fecha, booleano, texto).

### Limpieza
Árbol agrupado por columna con dos fuentes de recomendaciones combinadas:
- **Heurísticas** (`cleaner.py`): porcentaje de nulos, outliers IQR, cardinalidad anómala.
- **IA** (`ai_analyzer.recommend_cleaning`): tipos incorrectos (fechas como string, etc.), formatos heterogéneos, categorías casi duplicadas, sentinelas de null, columnas casi vacías. Las recomendaciones IA llevan badge `[IA]`. Estado de carga visible en la cabecera mientras la IA piensa.

### Preview
Grid 2×N (envuelto en `QScrollArea`, con selector de tamaño Compacto/Normal/Grande que usa `setFixedHeight` en el área del gráfico) de `ChartPanel`. Cada panel:
- Selector de **tipo** (Histograma/Barras/Dispersión/Línea), **X**, **Y** (Y solo si el tipo es bidimensional). Tipo y variables se auto-acomodan entre sí: si cambias X a una columna incompatible, el tipo cambia al más sensato, y viceversa.
- Gráfico renderizado con `pyqtgraph` (`charts/renderer.py`).
- Bloque IA con descripción + observaciones, colores theme-aware.
- Botón "⇄" que abre menú con alternativas (resto de specs del AI). Al elegir una, swap inmediato; el panel reemplazado vuelve al carrusel.
- Al cambiar variables / tipo / hacer swap, se vuelve a pedir explain_chart al AI (request_id con secuencial para descartar respuestas obsoletas).

Si la IA no contesta dentro del watchdog, `select_charts` genera hasta 10 specs heurísticos para que también haya alternativas en modo auto.

### Custom
Constructor manual: combo de tipo, combos X/Y, botón Renderizar. Render en hilo de fondo (Plotly genera la figura → escribe HTML temporal → carga en WebEngine). Bloque de análisis IA debajo con descripción + observaciones. La `QWebEnginePage` se reemplaza por una `SilentWebPage` que sobreescribe `createWindow` y `javaScriptAlert/Confirm/Prompt` para evitar popups.

### Asistente IA
Chat clásico contra Ollama. El streaming de chunks se **batchea**: en lugar de re-parsear el markdown completo por cada chunk (lo que congelaba la UI con respuestas largas), un `QTimer` flushea el contenido cada 150 ms. Estilo del documento con `defaultStyleSheet`: titulares en color de acento, blockquote con barra lateral, code con fondo.

## Integración con la IA

Toda la comunicación con Ollama vive en `data/ai_analyzer.py` como una sola clase `AIAnalyzer(QObject)`. Conecta con `http://localhost:11434/api/chat` y expone:

| Método                    | Endpoint                 | Stream | Formato       | Uso                         |
| ------------------------- | ------------------------ | ------ | ------------- | --------------------------- |
| `check_connection()`      | `/api/tags`              | -      | -             | Detecta Ollama al arrancar  |
| `recommend_charts(...)`   | `/api/chat`              | False  | `format=json` | Specs para Preview          |
| `recommend_cleaning(...)` | `/api/chat`              | False  | `format=json` | Recomendaciones de limpieza |
| `explain_chart(...)`      | `/api/chat`              | False  | `format=json` | Descripción + observaciones |
| `generate_initial_report` | `/api/chat`              | True   | -             | Reporte inicial conversado  |
| `send_chat_message(...)`  | `/api/chat`              | True   | -             | Mensajes del usuario        |

Cada operación corre en su propio `threading.Thread` y emite señales Qt (todas conectadas con `Qt.QueuedConnection`). Los timeouts urllib son de 600 s para tolerar la cola de Ollama cuando hay varias peticiones encadenadas. Todos los prompts indican explícitamente al modelo que responda en español.

Los `request_id` permiten enrutar respuestas (de `explain_chart`) al panel correcto en el Preview y descartar respuestas obsoletas cuando el usuario cambia variables varias veces seguidas.

## Persistencia y configuración

`src/settings/config.py` guarda preferencias del usuario (tema) en un JSON dentro de `%APPDATA%/DataPreview/` en Windows (o `~/.config/DataPreview/` en Linux/macOS). Se aplica antes de mostrar la primera ventana.

## Diseño defensivo

- **Cancelación de carga**: si el usuario abre otro archivo mientras uno se está cargando, `DataLoaderManager` activa un flag de cancelación que el reader consulta entre chunks.
- **Render incremental del Preview**: los `ChartPanel` se crean uno por uno con `QTimer.singleShot(20, ...)` entre cada uno, así nunca se bloquea la UI durante segundos creando widgets de pyqtgraph.
- **Lazy load del Custom**: el WebEngine no se inicia hasta que el usuario abre la pestaña.
- **Throttle del chat IA**: chunks de streaming se acumulan en buffer y solo se refresca el markdown cada 150 ms.
- **Fallback automático**: cualquier fallo de IA cae a la heurística sin que el usuario tenga que hacer nada.

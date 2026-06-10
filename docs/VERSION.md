# Historial de versiones

Changelog de DataPreview. (Lo más reciente arriba).

---

## [0.2] - 2026-06-10

### Añadido

#### Generación de informe
- Botón **Generar informe** que compila el análisis del dataset (resumen de contexto, problemas de limpieza detectados y gráficos con sus observaciones) en un documento.
- Opción de **descargar como HTML** standalone, visualizable en cualquier navegador sin necesidad de tener la app.

### Contexto
Hasta ahora todo el análisis vivía dentro de la app; con el informe el resultado del EDA se puede guardar y compartir fuera de DataPreview.


## [0.1] - 2026-05-12

### Añadido

#### Carga de datos
- Soporte de CSV, XLSX, JSON y Parquet.
- Lectura por chunks con barra de progreso y estimación de tiempo restante.
- Área de arrastre clicable (drag & drop o click para seleccionar) con indicador de IA disponible/no disponible.
- Carga opcional de un diccionario / descripción de los datos que aporta contexto adicional a la IA.

#### Pestaña Contexto
- Tarjetas de resumen: filas, columnas, memoria y número de tipos distintos.
- Sección plegable con la descripción del dataset si se aportó diccionario.
- Tabla de columnas redimensionable con iconos por tipo de dato (numérico, fecha, booleano, texto) y estadísticas (nulos, únicos, min, max).

#### Pestaña Limpieza
- Detección heurística automática de problemas: porcentaje de nulos, outliers por IQR, cardinalidad anómala.
- Recomendaciones de la IA (si está disponible) sobre tipos incorrectos, formatos heterogéneos, categorías casi duplicadas, sentinelas de null y columnas casi vacías.
- Vista de árbol agrupada por columna con badge `[IA]` para distinguir el origen.

#### Pestaña Preview
- Grid de hasta 6 gráficos recomendados, con la IA priorizando los más relevantes para el análisis cuando está disponible, o usando una heurística que mezcla líneas temporales, scatters entre numéricas, frecuencias de categóricas e histogramas.
- Cada panel con descripción del gráfico y observaciones sobre los datos generadas por la IA.
- Selector de **tipo + X + Y** por panel con auto-acomodación: cambiar las variables actualiza el tipo de gráfico para evitar combinaciones imposibles.
- Carrusel de **alternativas swappables** debajo del grid; un click cambia un panel por una alternativa y la sustituida vuelve al carrusel.
- Scroll vertical y selector de tamaño (Compacto / Normal / Grande).

#### Pestaña Custom
- Constructor manual con todos los tipos de gráficos: Scatter, Línea, Barras, Histograma, Boxplot y Heatmap de correlación.
- Render con Plotly + WebEngine en hilo de fondo, con spinner mientras genera el HTML.
- Análisis de la IA debajo del gráfico (descripción + observaciones) tras cada render.

#### Asistente IA (opcional)
- Cliente local contra Ollama (`http://localhost:11434`), sin conexión a internet.
- Reporte inicial automático tras cargar el dataset.
- Chat libre sobre los datos con respuestas en streaming.
- Markdown estilizado: titulares destacados, blockquote con barra lateral, code con fondo, palabras clave en color de acento.
- Todos los prompts en español. La app funciona igual sin IA, degradando limpio a las heurísticas.

#### General
- Temas claro y oscuro, con colores theme-aware en bloques de análisis y gráficos.
- Persistencia de preferencias en `%APPDATA%/DataPreview/`.
- Build script (`build.bat`) para generar un `.exe` standalone con PyInstaller.

### Contexto
Primera release pública. El foco fue combinar análisis exploratorio clásico (heurísticas, estadísticas, gráficos automáticos) con un asistente de IA local opcional, manteniendo la UI siempre responsiva (ningún hilo de fondo bloquea la interacción) y degradando con gracia cuando la IA no está disponible.

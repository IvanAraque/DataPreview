import json
import urllib.request
import urllib.error
import threading
from PySide6.QtCore import QObject, Signal

class AIAnalyzer(QObject):
    report_ready = Signal(str)
    chunk_received = Signal(str)
    error_occurred = Signal(str)
    charts_recommended = Signal(list)
    charts_error = Signal(str)
    # request_id permite enrutar la respuesta al panel correcto (Custom o panels del Preview)
    chart_explanation_ready = Signal(str, str, str)  # request_id, description, observations
    chart_explanation_error = Signal(str, str)       # request_id, error_msg
    # Recomendaciones de limpieza generadas por la IA
    cleaning_recommendations_ready = Signal(list)
    cleaning_recommendations_error = Signal(str)
    # Generación del informe completo (memoria de análisis)
    report_sections_ready = Signal(dict)
    report_sections_error = Signal(str)

    def __init__(self, model="phi3"): # Default to phi3 or llama3
        super().__init__()
        self.model = model
        self.url = "http://localhost:11434/api/chat"
        self._thread = None
        self._chart_thread = None
        self._explain_thread = None
        self._cleaning_thread = None
        self._report_thread = None
        self._messages = []
        
    def check_connection(self) -> bool:
        try:
            req = urllib.request.Request("http://localhost:11434/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=2) as response:
                return response.status == 200
        except:
            return False
            
    def generate_initial_report(self, profile: dict, context_text: str = ""):
        self._messages = [] # Reset history
        prompt = self._build_system_prompt(profile, context_text)
        self._messages.append({"role": "system", "content": prompt})
        self._messages.append({"role": "user", "content": "Genera un reporte inicial en Markdown analizando este dataset. Destaca qué gráficos recomiendas ver y si ves anomalías que limpiar. Sé conciso y profesional."})
        
        self._start_generation()
        
    def send_chat_message(self, message: str):
        self._messages.append({"role": "user", "content": message})
        self._start_generation()
        
    def _start_generation(self):
        if self._thread and self._thread.is_alive():
            return # Already generating
            
        self._thread = threading.Thread(target=self._run_inference)
        self._thread.daemon = True
        self._thread.start()
        
    def _run_inference(self):
        data = {
            "model": self.model,
            "messages": self._messages,
            "stream": True
        }
        req = urllib.request.Request(self.url, data=json.dumps(data).encode('utf-8'), method="POST")
        req.add_header('Content-Type', 'application/json')
        
        full_response = ""
        try:
            with urllib.request.urlopen(req) as response:
                for line in response:
                    if line:
                        chunk = json.loads(line)
                        if "message" in chunk and "content" in chunk["message"]:
                            content = chunk["message"]["content"]
                            full_response += content
                            self.chunk_received.emit(content)
                            
            self._messages.append({"role": "assistant", "content": full_response})
            self.report_ready.emit(full_response)
        except Exception as e:
            self.error_occurred.emit(f"Error de conexión con Ollama. Asegúrate de que está instalado y corriendo en local.\nDetalle: {str(e)}")

    def recommend_charts(self, profile: dict, context_text: str = "", avoid: list = None, count: int = 10):
        """
        Pide a la IA recomendaciones de gráficos en JSON. No bloquea: corre en
        un hilo y emite charts_recommended(list) o charts_error(str).
        Por defecto pide hasta 10 (6 principales + alternativos).
        Si hay un hilo previo vivo se permite igualmente; quien escuche filtra
        las specs antiguas comprobando las columnas vigentes.
        """
        self._chart_thread = threading.Thread(
            target=self._run_chart_recommendation,
            args=(profile, context_text or "", avoid or [], int(count)),
            daemon=True,
        )
        self._chart_thread.start()

    def _run_chart_recommendation(self, profile: dict, context_text: str, avoid: list, count: int):
        try:
            prompt = self._build_chart_prompt(profile, context_text, avoid, count)
            data = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "format": "json",
            }
            req = urllib.request.Request(
                self.url,
                data=json.dumps(data).encode("utf-8"),
                method="POST",
            )
            req.add_header("Content-Type", "application/json")

            with urllib.request.urlopen(req, timeout=600) as response:
                payload = json.loads(response.read().decode("utf-8"))

            content = payload.get("message", {}).get("content", "")
            parsed = json.loads(content) if content else {}

            # El modelo puede devolver {"charts":[...]} o directamente una lista.
            raw_charts = parsed.get("charts", parsed) if isinstance(parsed, dict) else parsed
            if not isinstance(raw_charts, list):
                self.charts_error.emit("Respuesta de la IA no es una lista de gráficos.")
                return

            valid_types = {"hist", "bar", "scatter", "line"}
            available_cols = {c.get("name") for c in profile.get("columns", [])}
            cleaned = []
            for item in raw_charts:
                if not isinstance(item, dict):
                    continue
                ctype = str(item.get("type", "")).lower().strip()
                if ctype not in valid_types:
                    continue
                x = item.get("x")
                if x not in available_cols:
                    continue
                spec = {"type": ctype, "x": x, "explanation": str(item.get("explanation", "")).strip()}
                if ctype in ("scatter", "line"):
                    y = item.get("y")
                    if y not in available_cols:
                        continue
                    spec["y"] = y
                else:
                    spec["y"] = "count" if ctype == "bar" else "frequency"
                cleaned.append(spec)

            self.charts_recommended.emit(cleaned[:count])
        except Exception as e:
            self.charts_error.emit(str(e))

    def _build_chart_prompt(self, profile: dict, context_text: str, avoid: list, count: int = 10) -> str:
        cols_lines = []
        for col in profile.get("columns", []):
            cols_lines.append(
                f"- {col.get('name')} (tipo {col.get('type')}, nulos {col.get('nulls')}, "
                f"unicos {col.get('unique', '?')}, min {col.get('min', '?')}, max {col.get('max', '?')})"
            )
        cols_block = "\n".join(cols_lines) if cols_lines else "(sin columnas)"

        avoid_block = ""
        if avoid:
            avoid_block = "\nEVITA repetir estas recomendaciones (el usuario quiere otras distintas):\n"
            for a in avoid:
                avoid_block += f"- type={a.get('type')} x={a.get('x')} y={a.get('y','')}\n"

        ctx_block = ""
        if context_text:
            ctx_block = "\nContexto adicional proporcionado por el usuario:\n" + context_text[:1500]

        return (
            f"Eres un analista de datos senior. Recomienda hasta {count} visualizaciones "
            "para entender este dataset de forma PROFUNDA y ACCIONABLE.\n\n"
            "PRIORIZACION (muy importante):\n"
            "1) Ordena la lista de MAS IMPORTANTE a menos importante para el analisis.\n"
            "2) Prefiere visualizaciones ANALITICAS y COMPLEJAS sobre las triviales:\n"
            "   - Relaciones entre 2 variables clave (scatter).\n"
            "   - Evolucion temporal de una metrica (line con fecha en X).\n"
            "   - Comparacion entre categorias (bar de una metrica agrupada).\n"
            "   - Distribuciones SOLO si son particularmente reveladoras (sesgo, outliers).\n"
            "3) Una grafica simple de una sola columna solo es valida si esa columna es "
            "central al negocio o si su distribucion es no trivial.\n"
            "4) Mezcla complejidades: las PRIMERAS 6 son las principales (mostradas), el resto "
            "se ofrecen como alternativas. Las primeras DEBEN ser las mas importantes.\n\n"
            f"Dataset: {profile.get('rows', 0)} filas, {profile.get('cols', 0)} columnas.\n"
            f"Columnas:\n{cols_block}\n"
            f"{ctx_block}"
            f"{avoid_block}\n"
            "Tipos validos:\n"
            "- hist: histograma de una columna numerica. Campos: type, x, explanation.\n"
            "- bar: barras de frecuencia de una categorica. Campos: type, x, explanation.\n"
            "- scatter: dispersion. Campos: type, x, y, explanation. x e y numericas distintas.\n"
            "- line: linea. Campos: type, x, y, explanation. x suele ser fecha o variable ordenable.\n\n"
            "IDIOMA: Las 'explanation' DEBEN estar escritas EXCLUSIVAMENTE en ESPAÑOL de España, "
            "aunque los nombres de columnas esten en ingles.\n\n"
            "Responde EXCLUSIVAMENTE con JSON valido sin texto adicional, asi:\n"
            '{"charts":[{"type":"scatter","x":"ingreso","y":"gasto","explanation":"Relacion clave..."},'
            '{"type":"line","x":"fecha","y":"ventas","explanation":"Evolucion mensual..."}]}\n'
            "Reglas: usa solo nombres EXACTOS de la lista de columnas. La explicacion debe ser una "
            "frase clara y CONCRETA en espanol (1-2 frases) explicando QUE se ve y POR QUE es util."
        )

    # ------------------------------------------------------------------
    # Recomendaciones de LIMPIEZA (EDA)
    # ------------------------------------------------------------------

    def recommend_cleaning(self, profile: dict, samples: dict = None, context_text: str = ""):
        """
        Pide a la IA un análisis EDA de limpieza: detección de tipos incorrectos,
        formatos heterogéneos, anomalías, columnas que parecen otra cosa, etc.
        Emite cleaning_recommendations_ready(list) o cleaning_recommendations_error(str).
        `samples` es un dict opcional {columna: [valores ejemplo]} para que la IA
        deduzca formatos.
        """
        t = threading.Thread(
            target=self._run_cleaning_recommendation,
            args=(profile or {}, samples or {}, context_text or ""),
            daemon=True,
        )
        self._cleaning_thread = t
        t.start()

    def _run_cleaning_recommendation(self, profile: dict, samples: dict, context_text: str):
        try:
            prompt = self._build_cleaning_prompt(profile, samples, context_text)
            data = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "format": "json",
            }
            req = urllib.request.Request(
                self.url,
                data=json.dumps(data).encode("utf-8"),
                method="POST",
            )
            req.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(req, timeout=600) as response:
                payload = json.loads(response.read().decode("utf-8"))

            content = payload.get("message", {}).get("content", "")
            parsed = json.loads(content) if content else {}
            raw = parsed.get("recommendations", parsed) if isinstance(parsed, dict) else parsed
            if not isinstance(raw, list):
                self.cleaning_recommendations_error.emit("Respuesta IA no es una lista de recomendaciones.")
                return

            available_cols = {c.get("name") for c in profile.get("columns", [])}
            cleaned = []
            for item in raw:
                if not isinstance(item, dict):
                    continue
                col = item.get("column") or item.get("columna")
                problem = item.get("problem") or item.get("problema")
                suggestion = item.get("suggestion") or item.get("sugerencia")
                severity = (item.get("severity") or item.get("severidad") or "Media").capitalize()
                if severity not in ("Alta", "Media", "Baja"):
                    severity = "Media"
                if not col or col not in available_cols:
                    continue
                if not problem or not suggestion:
                    continue
                cleaned.append({
                    "columna": col,
                    "problema": str(problem).strip(),
                    "sugerencia": str(suggestion).strip(),
                    "severidad": severity,
                    "origen": "ia",
                })

            self.cleaning_recommendations_ready.emit(cleaned)
        except Exception as e:
            self.cleaning_recommendations_error.emit(str(e))

    def _build_cleaning_prompt(self, profile: dict, samples: dict, context_text: str) -> str:
        cols_lines = []
        for col in profile.get("columns", []):
            name = col.get("name")
            line = (
                f"- {name}: tipo {col.get('type')}, nulos {col.get('nulls')}, "
                f"unicos {col.get('unique', '?')}, min {col.get('min', '?')}, max {col.get('max', '?')}"
            )
            sv = samples.get(name) if isinstance(samples, dict) else None
            if sv:
                preview = ", ".join(str(v)[:30] for v in sv[:5])
                line += f", ejemplos: [{preview}]"
            cols_lines.append(line)
        cols_block = "\n".join(cols_lines) if cols_lines else "(sin columnas)"

        ctx_block = ""
        if context_text:
            ctx_block = "\nContexto adicional del usuario:\n" + context_text[:1500]

        return (
            "Eres un analista de datos experto haciendo EDA (analisis exploratorio). "
            "Revisa el siguiente dataset y detecta PROBLEMAS DE LIMPIEZA / CALIDAD que un "
            "analista no deberia pasar por alto.\n\n"
            f"Dataset: {profile.get('rows', 0)} filas, {profile.get('cols', 0)} columnas.\n"
            f"Columnas:\n{cols_block}\n"
            f"{ctx_block}\n\n"
            "Tipos de problemas a considerar (no te limites a estos):\n"
            "- Columnas con tipo INCORRECTO: fechas guardadas como Utf8/String, numeros "
            "como string, booleanos como int...\n"
            "- FORMATOS heterogeneos: e.g. fechas en formatos mezclados, mayusculas/minusculas "
            "inconsistentes, espacios extras, separadores diferentes.\n"
            "- Categorias que parecen ser la misma con grafias distintas (ej 'USA' vs 'U.S.A').\n"
            "- Columnas casi vacias (muchos nulos) o con varianza nula.\n"
            "- Outliers extremos (basate en min/max relativos a la distribucion esperada).\n"
            "- Identificadores que deberian ser categoria/string (no numeric).\n"
            "- Codificaciones extranas (e.g. -1 o 9999 como sentinel de null).\n"
            "- Columnas redundantes o derivadas que aporten poco.\n\n"
            "IDIOMA: Responde EXCLUSIVAMENTE en ESPAÑOL.\n\n"
            "Responde EXCLUSIVAMENTE con JSON valido, sin texto extra:\n"
            '{"recommendations":[{'
            '"column":"nombre_columna_exacto",'
            '"severity":"Alta|Media|Baja",'
            '"problem":"Descripcion concisa del problema",'
            '"suggestion":"Que accion concreta tomar (cast a fecha, parsear formato X, '
            "etc) en una frase\""
            "}]}\n"
            "Reglas: usa SOLO nombres EXACTOS de la lista. No inventes valores que no esten. "
            "Si no hay problemas claros, devuelve {\"recommendations\":[]}."
        )

    # ------------------------------------------------------------------
    # Generación del INFORME completo (memoria de análisis)
    # ------------------------------------------------------------------

    def generate_report(self, profile: dict, samples: dict = None,
                        context_text: str = "", chart_summaries: list = None,
                        cleaning_summary: list = None, dataset_name: str = ""):
        """
        Pide a la IA la prosa del informe en un único call. Devuelve por la
        señal report_sections_ready(dict) un diccionario con: title_suggestion,
        abstract, introduction, intro_eda, cleaning_section y conclusions.
        Todas escritas en primera persona del plural, sin tono robótico ni
        listas con bullets.
        """
        t = threading.Thread(
            target=self._run_report_generation,
            args=(
                profile or {},
                samples or {},
                context_text or "",
                chart_summaries or [],
                cleaning_summary or [],
                dataset_name or "",
            ),
            daemon=True,
        )
        self._report_thread = t
        t.start()

    def _run_report_generation(self, profile, samples, context_text,
                               chart_summaries, cleaning_summary, dataset_name):
        try:
            prompt = self._build_report_prompt(
                profile, samples, context_text,
                chart_summaries, cleaning_summary, dataset_name,
            )
            data = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "format": "json",
            }
            req = urllib.request.Request(
                self.url,
                data=json.dumps(data).encode("utf-8"),
                method="POST",
            )
            req.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(req, timeout=900) as response:
                payload = json.loads(response.read().decode("utf-8"))

            content = payload.get("message", {}).get("content", "")
            parsed = json.loads(content) if content else {}
            if not isinstance(parsed, dict):
                self.report_sections_error.emit("Respuesta IA no es un objeto JSON.")
                return

            # Normalizar campos esperados
            out = {
                "title_suggestion": str(parsed.get("title_suggestion", "")).strip(),
                "abstract": str(parsed.get("abstract", "")).strip(),
                "introduction": str(parsed.get("introduction", "")).strip(),
                "intro_eda": str(parsed.get("intro_eda", "")).strip(),
                "cleaning_section": str(parsed.get("cleaning_section", "")).strip(),
                "conclusions": str(parsed.get("conclusions", "")).strip(),
            }
            self.report_sections_ready.emit(out)
        except Exception as e:
            self.report_sections_error.emit(str(e))

    def _build_report_prompt(self, profile, samples, context_text,
                             chart_summaries, cleaning_summary, dataset_name):
        cols_lines = []
        for col in profile.get("columns", []):
            name = col.get("name")
            line = (
                f"- {name}: tipo {col.get('type')}, nulos {col.get('nulls')}, "
                f"unicos {col.get('unique', '?')}, min {col.get('min', '?')}, "
                f"max {col.get('max', '?')}"
            )
            sv = samples.get(name) if isinstance(samples, dict) else None
            if sv:
                preview = ", ".join(str(v)[:30] for v in sv[:5])
                line += f", ejemplos: [{preview}]"
            cols_lines.append(line)
        cols_block = "\n".join(cols_lines) if cols_lines else "(sin columnas)"

        chart_lines = []
        for i, c in enumerate(chart_summaries or [], start=1):
            t = c.get("type", "?")
            x = c.get("x", "")
            y = c.get("y", "")
            desc = c.get("description", "")
            obs = c.get("observations", "")
            chart_lines.append(
                f"{i}. [{t}] X={x}" + (f", Y={y}" if y and y not in ("count", "frequency") else "")
                + (f"\n   Descripcion: {desc}" if desc else "")
                + (f"\n   Observaciones: {obs}" if obs else "")
            )
        charts_block = "\n".join(chart_lines) if chart_lines else "(sin graficos disponibles)"

        cleaning_lines = []
        for r in (cleaning_summary or [])[:30]:
            cleaning_lines.append(
                f"- [{r.get('severidad', '?')}] {r.get('columna', '?')}: "
                f"{r.get('problema', '')} → {r.get('sugerencia', '')}"
            )
        cleaning_block = "\n".join(cleaning_lines) if cleaning_lines else "(sin problemas reportados)"

        ctx_block = ""
        if context_text:
            ctx_block = "\nContexto adicional aportado por el usuario:\n" + context_text[:2000]

        ds_block = ""
        if dataset_name:
            ds_block = f"\nNombre del fichero: {dataset_name}"

        return (
            "Eres un analista de datos profesional escribiendo una MEMORIA de análisis "
            "para un cliente real. Te basas EXCLUSIVAMENTE en los hechos que te paso a "
            "continuación; NO inventas cifras ni hallazgos que no estén en los datos.\n\n"

            "ESTILO OBLIGATORIO:\n"
            "- Escribe en ESPAÑOL de España.\n"
            "- Usa primera persona del plural ('hemos analizado', 'se observa', 'podemos ver').\n"
            "- Tono profesional pero natural y humano. NADA de tono robótico ni frases "
            "tipo 'En este informe se procederá a...'.\n"
            "- Párrafos largos y bien hilados. NADA de listas con bullets ni de "
            "encabezados internos. Solo prosa.\n"
            "- NUNCA menciones que eres una IA, un modelo de lenguaje, ChatGPT, GPT, "
            "Claude, Qwen ni ningún sistema automático. NUNCA digas que el texto fue "
            "generado o asistido por IA.\n"
            "- NUNCA digas 'como analista de datos' ni 'en este informe explicaremos'. "
            "Ve directo al grano.\n"
            "- Evita muletillas tipo 'cabe destacar', 'es importante señalar', 'en "
            "primer lugar', 'en conclusión'. Usa conectores variados.\n"
            "- Si un dato no está en lo que te paso, no lo inventes: omítelo.\n\n"

            f"DATASET:{ds_block}\n"
            f"Tiene {profile.get('rows', 0)} filas y {profile.get('cols', 0)} columnas.\n"
            f"Columnas:\n{cols_block}\n"
            f"{ctx_block}\n\n"

            "GRAFICOS QUE SE INCLUYEN EN EL INFORME (cada uno con su descripcion y "
            "observaciones; usalos para articular el analisis exploratorio):\n"
            f"{charts_block}\n\n"

            "PROBLEMAS DE CALIDAD DE DATOS DETECTADOS:\n"
            f"{cleaning_block}\n\n"

            "Genera el JSON con estos campos (cada uno son párrafos en prosa pura):\n"
            "- title_suggestion: titulo del informe en una sola línea (ej. 'Analisis del "
            "dataset de ...'). MAX 12 palabras.\n"
            "- abstract: resumen del análisis en 4-6 frases. Menciona el tamaño del "
            "dataset, qué se ha analizado y los hallazgos principales.\n"
            "- introduction: 2 párrafos contextualizando los datos: qué representan, "
            "qué objetivo tiene el análisis, qué se va a ver en el informe.\n"
            "- intro_eda: 1 párrafo introduciendo la sección de análisis exploratorio "
            "(qué tipo de visualizaciones se van a comentar).\n"
            "- cleaning_section: 2 párrafos sobre la calidad de los datos, problemas "
            "detectados y recomendaciones de limpieza.\n"
            "- conclusions: 3-4 párrafos cerrando el análisis. Incluye insights "
            "de negocio/decisión (qué se podría hacer con esto), limitaciones del "
            "análisis y posibles siguientes pasos.\n\n"

            "Responde EXCLUSIVAMENTE con JSON válido, sin texto adicional fuera del "
            "JSON. Ejemplo de estructura:\n"
            '{"title_suggestion":"...","abstract":"...","introduction":"...",'
            '"intro_eda":"...","cleaning_section":"...","conclusions":"..."}'
        )

    def explain_chart(self, chart_def: dict, profile: dict, context_text: str = "", request_id: str = ""):
        """
        Pide a la IA una explicación de un gráfico concreto: qué muestra y qué
        se observa en los datos. Emite chart_explanation_ready(request_id, description, observations)
        o chart_explanation_error(request_id, msg).
        Permite múltiples peticiones concurrentes (Ollama las encola por modelo).
        """
        t = threading.Thread(
            target=self._run_chart_explanation,
            args=(dict(chart_def or {}), profile or {}, context_text or "", str(request_id or "")),
            daemon=True,
        )
        # Mantenemos referencia a la última (suficiente para liveness checks externos)
        self._explain_thread = t
        t.start()

    def _run_chart_explanation(self, chart_def: dict, profile: dict, context_text: str, request_id: str):
        try:
            prompt = self._build_explain_prompt(chart_def, profile, context_text)
            data = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "format": "json",
            }
            req = urllib.request.Request(
                self.url,
                data=json.dumps(data).encode("utf-8"),
                method="POST",
            )
            req.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(req, timeout=600) as response:
                payload = json.loads(response.read().decode("utf-8"))
            content = payload.get("message", {}).get("content", "")
            parsed = json.loads(content) if content else {}
            description = str(parsed.get("description", "")).strip()
            observations = str(parsed.get("observations", "")).strip()
            self.chart_explanation_ready.emit(request_id, description, observations)
        except Exception as e:
            self.chart_explanation_error.emit(request_id, str(e))

    def _build_explain_prompt(self, chart_def: dict, profile: dict, context_text: str) -> str:
        ctype = chart_def.get("type", "?")
        x = chart_def.get("x", "?")
        y = chart_def.get("y", "")
        type_label_map = {
            "Dispersión (Scatter)": "scatter",
            "Línea": "line",
            "Barras": "bar",
            "Histograma": "hist",
            "Cajas (Boxplot)": "box",
            "Correlación (Heatmap)": "heatmap",
        }
        # El advanced_tab usa etiquetas con espacio; las normalizamos
        ctype_norm = type_label_map.get(ctype, ctype)

        # Tomar info de las columnas implicadas
        cols_info = []
        wanted = {c for c in (x, y) if c}
        for col in profile.get("columns", []):
            if col.get("name") in wanted:
                cols_info.append(
                    f"- {col.get('name')}: tipo {col.get('type')}, nulos {col.get('nulls')}, "
                    f"unicos {col.get('unique', '?')}, min {col.get('min', '?')}, max {col.get('max', '?')}"
                )
        cols_block = "\n".join(cols_info) if cols_info else "(sin estadisticas)"

        ctx_block = ""
        if context_text:
            ctx_block = "\nContexto adicional del usuario:\n" + context_text[:1200]

        return (
            "Eres un analista de datos. Analiza el siguiente grafico y describe (a) que "
            "tipo de grafico es y para que sirve, y (b) que se observa en los datos.\n\n"
            f"Grafico: tipo={ctype_norm}, x={x}, y={y}\n"
            f"Estadisticas de las columnas:\n{cols_block}\n"
            f"{ctx_block}\n\n"
            "IDIOMA: Responde EXCLUSIVAMENTE en ESPAÑOL. Tanto 'description' como "
            "'observations' DEBEN estar escritas en español de España, sin mezclar palabras "
            "en ingles aunque los nombres de columnas esten en ingles.\n\n"
            "Responde EXCLUSIVAMENTE con JSON valido sin texto adicional:\n"
            '{"description":"Descripcion breve del grafico en espanol (1-2 frases)",'
            '"observations":"Que se observa en los datos en espanol: tendencias, valores notables, '
            "rangos, posibles outliers, etc (2-3 frases, basate en min/max/nulos/unicos)\"}\n"
            "Importante: NO inventes datos que no esten en las estadisticas. Si no hay "
            "info suficiente para observaciones, di que se necesitarian mas datos."
        )

    def _build_system_prompt(self, profile: dict, context_text: str) -> str:
        prompt = "Eres un analista de datos experto.\n"
        prompt += f"Dataset con {profile.get('rows', 0)} filas y {profile.get('cols', 0)} columnas.\n"
        prompt += "Columnas:\n"
        for col in profile.get('columns', []):
            prompt += f"- {col.get('name')}: Tipo {col.get('type')}, {col.get('nulls')} nulos, {col.get('unique')} únicos.\n"
            
        if context_text:
            prompt += "\n--- CONTEXTO ADICIONAL DEL USUARIO ---\n"
            prompt += context_text[:2000] # Limit size just in case
            prompt += "\n--------------------------------------\n"
            
        prompt += "\nTu objetivo es analizar esta estructura y ayudar al usuario a entender los datos."
        return prompt

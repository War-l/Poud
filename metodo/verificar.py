"""Verificador del método: comprueba un expediente contra las reglas de cada fase.

Uso:
    python3 -m metodo.verificar RUTA/expediente.yaml --fase {enfoque,plan,produccion,final}

Termina con código 1 si hay errores. Cada regla tiene un código (ENF-01, CON-07…) que
TRAZABILIDAD.md enlaza con el pilar de las fuentes del que procede.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

from .expediente import LATERALES, Expediente, cargar, como_lista, contrario

FASES = ["enfoque", "plan", "produccion", "final"]
FUNCIONES = ["captar", "contexto", "explicar", "demostrar", "preguntar", "aplicar", "cerrar"]
TAMANOS = ["GPG", "PG", "PE", "PA", "PM", "PMC", "PP", "PPP", "PD"]
CANALES = ["visual", "dialogo", "texto", "narracion"]
TIPOS_OBRA = ["parabola", "documental", "explicativo", "testimonio"]
NIVELES = ["leche", "alimento_solido"]
PESOS = ["piedra_angular", "principal", "secundario"]
ESTADOS_PROTOTIPO = ["pendiente", "enviado", "aprobado", "omitido_por_usuario"]
REGLAS_COMPOSICION = ["tercios", "centrada", "simetrica", "libre"]
VERBOS_OBSERVABLES = {
    "distinguir", "identificar", "reconocer", "explicar", "describir", "aplicar", "comparar",
    "decidir", "justificar", "nombrar", "senalar", "ordenar", "clasificar", "resolver",
    "demostrar", "evaluar", "formular", "predecir", "relacionar", "argumentar", "elegir",
    "enumerar", "ejemplificar", "contrastar", "responder", "actuar", "examinar", "escuchar",
    "preguntar", "diferenciar", "detectar", "corregir",
}
VERBOS_NO_OBSERVABLES = {
    "entender", "comprender", "saber", "conocer", "aprender", "apreciar", "sentir",
    "reflexionar", "darse", "captar", "interiorizar", "asimilar", "concienciarse", "tomar",
}
REVISION_MANUAL = {
    "REV-01": "Cada plano se entiende sin diálogos ni rótulos (hoja de planos).",
    "REV-02": "Cada personaje conserva rasgos y vestuario de la biblia (hoja por personaje).",
    "REV-03": "Cada corte marcado tiene veredicto con dos testigos.",
    "REV-04": "La idea central se ve en una acción.",
    "REV-05": "Nada se luce sin servir al mensaje (vanidad).",
    "REV-06": "Luz, paleta y composición coherentes con el estilo aprobado y la biblia.",
    "REV-07": "Sonido medido (sonoridad, picos) y ningún efecto contradice la imagen.",
    "REV-08": "Mensaje y diálogos del usuario intactos, salvo cambios aprobados.",
    "REV-09": "Representación veraz: los símbolos remiten a lo representado; lo divino no se muestra con una figura.",
}
LUFS_MIN, LUFS_MAX, PICO_MAX = -18.0, -14.0, -1.0
RATIO_OBJETIVO, RATIO_MAX = 1.0, 1.1


def sin_tildes(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def texto(v) -> bool:
    return isinstance(v, str) and bool(v.strip())


def palabras(s: str) -> int:
    return len(re.findall(r"\w+", s or ""))


class Verificador:
    def __init__(self, ex: Expediente, fase: str):
        self.ex, self.d, self.fase = ex, ex.d, fase
        self.errores, self.avisos = [], []
        self.n_fase = FASES.index(fase)

    # ── registro ─────────────────────────────────────────────────────────────────────
    def error(self, cod, msg, donde=""):
        self.errores.append((cod, donde, msg))

    def aviso(self, cod, msg, donde=""):
        self.avisos.append((cod, donde, msg))

    def desde(self, fase):
        return self.n_fase >= FASES.index(fase)

    def seccion(self, nombre, cod="GEN-01"):
        v = self.d.get(nombre)
        if not isinstance(v, dict):
            self.error(cod, f"Falta la sección «{nombre}».")
            return {}
        return v

    # ── ejecución ────────────────────────────────────────────────────────────────────
    def ejecutar(self):
        self.r_general()
        rec = self.seccion("recepcion")
        origen = rec.get("origen")
        if origen not in ("tema", "guion_usuario"):
            self.error("GEN-01", "recepcion.origen debe ser «tema» o «guion_usuario».")
        self.r_recepcion(rec)
        if origen == "tema":
            self.r_enfoque_tema()
        elif origen == "guion_usuario":
            self.r_enfoque_guion()
        if not self.desde("plan"):
            return self
        self.r_ensenanza()
        self.r_creacion()
        self.r_escenas()
        self.r_planos()
        self.r_continuidad()
        self.r_ajustes()
        if self.desde("produccion"):
            self.r_prototipo()
        if self.desde("final"):
            self.r_entrega()
        return self

    # ── GEN ──────────────────────────────────────────────────────────────────────────
    def r_general(self):
        d = self.d
        if not texto(d.get("titulo")):
            self.error("GEN-01", "Falta «titulo».")
        if self.desde("plan"):
            for k in ("duracion_s", "fps", "resolucion"):
                if not d.get(k):
                    self.error("GEN-01", f"Falta «{k}».")
            res = d.get("resolucion")
            if res and not (isinstance(res, list) and len(res) == 2):
                self.error("GEN-01", "«resolucion» debe ser [ancho, alto].")
            for nombre, lista in (("escenas", self.ex.escenas_lista), ("planos", self.ex.planos)):
                ids = [x.get("id") for x in lista]
                if not lista:
                    self.error("GEN-01", f"Falta la lista «{nombre}».")
                dup = {i for i in ids if ids.count(i) > 1}
                if dup or None in ids:
                    self.error("GEN-02", f"Identificadores de {nombre} vacíos o repetidos: {sorted(map(str, dup)) or 'id vacío'}.")

    def r_recepcion(self, rec):
        if not texto(rec.get("pedido")):
            self.error("GEN-01", "recepcion.pedido: escribe qué se pide, con las palabras del usuario.")
        if self.desde("plan"):
            inv = rec.get("inventario") or {}
            if not (como_lista(inv.get("reutiliza")) or como_lista(inv.get("construye"))):
                self.error("CRE-04", "recepcion.inventario: inspecciona antes de proponer (qué se reutiliza y qué se construye).")

    # ── ENF ──────────────────────────────────────────────────────────────────────────
    def _supuestos(self, en, obligatorio):
        if not como_lista(en.get("supuestos")):
            (self.error if obligatorio else self.aviso)(
                "ENF-10", "Declara al menos un supuesto o sesgo propio (limpiar el instrumento de observación).")

    def _fuentes_verificadas(self, fuentes, donde, minimo=2):
        ok = []
        for f in como_lista(fuentes):
            if not isinstance(f, dict):
                continue
            if f.get("verificada") is True and texto(f.get("referencia")):
                ok.append(f)
                if not texto(f.get("aporta")):
                    self.error("ENF-06", f"La fuente «{f.get('referencia')}» no dice qué afirma o respalda («aporta»).", donde)
        refs = {sin_tildes(f["referencia"]).lower().strip() for f in ok}
        if len(refs) < minimo:
            self.error("ENF-06", f"Se necesitan al menos {minimo} fuentes independientes verificadas (dos o tres testigos); "
                                  f"hay {len(refs)}.", donde)
        for f in ok:
            for nc in como_lista(f.get("no_confirmado")):
                ref = " ".join(f["referencia"].split())[:60]
                self.aviso("ENF-06", f"Dato no confirmado en «{ref}…»: {nc.rstrip('.')}. No puede presentarse como hecho.", donde)
        return ok

    def r_enfoque_tema(self):
        en = self.seccion("enfoque")
        if not texto(en.get("tema")):
            self.error("ENF-01", "enfoque.tema vacío.")
        self._supuestos(en, obligatorio=True)
        pre = en.get("preguntas") or {}
        for k in ("origen", "significado", "naturaleza", "consecuencia"):
            v = pre.get(k)
            if not texto(v):
                self.error("ENF-01", f"Falta la pregunta fundamental de «{k}».")
            elif not v.strip().endswith("?"):
                self.aviso("ENF-01", f"La pregunta de «{k}» no está formulada como pregunta.")
        de = en.get("delimitacion") or {}
        for k in ("dentro", "fuera"):
            if not como_lista(de.get(k)):
                self.error("ENF-02", f"Delimitación: la lista «{k}» está vacía (traza los linderos).")
        hall = [h for h in como_lista(en.get("hallazgos")) if isinstance(h, dict)]
        if not hall:
            self.error("ENF-03", "No hay hallazgos jerarquizados.")
        else:
            pa = [h for h in hall if h.get("peso") == "piedra_angular"]
            if len(pa) != 1:
                self.error("ENF-03", f"Debe haber exactamente una piedra angular entre los hallazgos; hay {len(pa)}.")
            malos = [h.get("peso") for h in hall if h.get("peso") not in PESOS]
            if malos:
                self.error("ENF-03", f"Pesos no válidos {malos}; usa {PESOS}.")
            orden = [PESOS.index(h.get("peso")) for h in hall if h.get("peso") in PESOS]
            if orden != sorted(orden):
                self.aviso("ENF-03", "Los hallazgos no están ordenados por peso (piedra angular → principal → secundario).")
        enf = [e for e in como_lista(en.get("enfoques")) if isinstance(e, dict)]
        if len(enf) < 3:
            self.error("ENF-04", f"Genera al menos 3 enfoques alternativos; hay {len(enf)}.")
        puntos = self._criterios(enf, "ENF-04", "enfoques")
        eleg = en.get("elegido")
        ids = [e.get("id") for e in enf]
        if eleg not in ids:
            self.error("ENF-05", f"enfoque.elegido «{eleg}» no es ninguno de {ids}.")
        else:
            if not texto(en.get("justificacion")):
                self.error("ENF-05", "Falta la justificación de la elección.")
            if puntos and puntos.get(eleg, 0) < max(puntos.values()):
                self.aviso("ENF-05", f"El enfoque elegido ({eleg}) no es el de mayor puntuación; la justificación debe explicarlo.")
        ver = en.get("verificacion") or {}
        self._fuentes_verificadas(ver.get("fuentes"), "enfoque.verificacion")
        if not como_lista(ver.get("contraejemplos")):
            self.error("ENF-07", "Busca contraejemplos o excepciones (contrastar explicaciones).")
        if not como_lista(ver.get("limitaciones")):
            self.error("ENF-07", "Declara las limitaciones de la evidencia.")
        v = ver.get("veredicto")
        if v not in ("aprobar", "reformular", "descartar"):
            self.error("ENF-08", "verificacion.veredicto debe ser aprobar, reformular o descartar.")
        elif v == "descartar":
            if self.desde("plan"):
                self.error("ENF-08", "El enfoque fue descartado en la verificación: no puede pasar a producción.")
            else:
                self.aviso("ENF-08", "Veredicto: descartar. Vuelve a seleccionar otro enfoque.")
        elif v == "reformular":
            final = ver.get("enfoque_final")
            original = next((e.get("texto") for e in enf if e.get("id") == eleg), None)
            if not texto(final):
                self.error("ENF-08", "Veredicto reformular sin «enfoque_final».")
            elif final.strip() == (original or "").strip():
                self.error("ENF-08", "Veredicto reformular, pero enfoque_final es idéntico al enfoque elegido.")

    def _criterios(self, items, cod, nombre):
        """Mismos criterios para todos (pesas justas). Devuelve {id: puntuación total}."""
        claves = None
        puntos = {}
        for e in items:
            c = e.get("criterios")
            if not isinstance(c, dict) or not c:
                self.error(cod, f"{nombre}: «{e.get('id')}» no tiene criterios evaluados.")
                continue
            if not texto(e.get("texto")):
                self.error(cod, f"{nombre}: «{e.get('id')}» no tiene texto.")
            if claves is None:
                claves = set(c)
            elif set(c) != claves:
                self.error(cod, f"{nombre}: «{e.get('id')}» se evalúa con criterios distintos ({sorted(c)} vs {sorted(claves)}): "
                                "todos deben pesarse con la misma balanza.")
            try:
                puntos[e.get("id")] = sum(float(x) for x in c.values())
            except (TypeError, ValueError):
                self.error(cod, f"{nombre}: «{e.get('id')}» tiene puntuaciones no numéricas.")
        return puntos

    def r_enfoque_guion(self):
        en = self.seccion("enfoque")
        g = en.get("guion")
        if not texto(g):
            self.error("ENF-09", "enfoque.guion: guarda el guion íntegro del usuario junto al expediente.")
        elif not (self.ex.carpeta / g).exists():
            self.error("ENF-09", f"No existe el guion «{g}» (ruta relativa al expediente).")
        if en.get("tipo_obra") not in TIPOS_OBRA:
            self.error("ENF-09", f"enfoque.tipo_obra debe ser uno de {TIPOS_OBRA}.")
        self._supuestos(en, obligatorio=False)
        for i, a in enumerate(como_lista(en.get("afirmaciones"))):
            if not isinstance(a, dict) or not texto(a.get("texto")):
                self.error("ENF-09", f"Afirmación {i + 1} sin texto.")
                continue
            if a.get("tipo") in ("ficcion", "opinion"):
                continue
            self._fuentes_verificadas(a.get("fuentes"), f"afirmación «{a['texto'][:40]}…»")
        for c in como_lista(en.get("cambios_guion")):
            if not isinstance(c, dict) or not texto(c.get("descripcion")):
                self.error("ENF-09", "Cada cambio al guion necesita «descripcion».")
                continue
            if c.get("aprobado_usuario") is not True:
                msg = f"Cambio al guion pendiente de aprobación del usuario: {c['descripcion']}"
                (self.error if self.desde("produccion") else self.aviso)("ENF-09", msg)

    # ── ENS ──────────────────────────────────────────────────────────────────────────
    def r_ensenanza(self):
        es = self.seccion("ensenanza")
        for k in ("publico", "idioma"):
            if not texto(es.get(k)):
                self.error("ENS-01", f"ensenanza.{k} vacío (habla en la lengua del oyente).")
        if es.get("nivel") not in NIVELES:
            self.error("ENS-01", f"ensenanza.nivel debe ser {NIVELES}.")
        obj = es.get("objetivo") or ""
        m = re.match(r"\s*el espectador podra\s+(\w+)", sin_tildes(obj).lower())
        if not m:
            self.error("ENS-02", "El objetivo debe empezar por «El espectador podrá» + verbo observable.")
        else:
            verbo = m.group(1)
            if verbo in VERBOS_NO_OBSERVABLES:
                self.error("ENS-02", f"«{verbo}» no es observable: no se puede comprobar. Usa p. ej. distinguir, explicar, aplicar, decidir.")
            elif verbo not in VERBOS_OBSERVABLES:
                self.aviso("ENS-02", f"Comprueba que «{verbo}» describa una conducta observable.")
        idea = es.get("idea_central")
        if not texto(idea):
            self.error("ENS-03", "Falta la idea central.")
        elif palabras(idea) > 30:
            self.error("ENS-03", f"La idea central tiene {palabras(idea)} palabras; máximo 30 (una sola piedra angular).")
        pc = es.get("pregunta_central")
        if not texto(pc) or not pc.strip().endswith("?"):
            self.error("ENS-03", "Falta la pregunta central (formulada como pregunta).")
        if not texto(es.get("hilo_conductor")):
            self.error("NAR-08", "Falta el hilo conductor.")
        # secuencia didáctica
        cubiertas = {}
        for p in self.ex.planos:
            for f in como_lista(p.get("funcion_didactica")):
                if f not in FUNCIONES:
                    self.error("ENS-04", f"Función didáctica desconocida «{f}»; usa {FUNCIONES}.", p.get("id"))
                cubiertas.setdefault(f, []).append(p)
        omis = es.get("omisiones") or {}
        for f in FUNCIONES:
            if f in cubiertas:
                if f in omis:
                    self.aviso("ENS-04", f"«{f}» está cubierta y a la vez declarada como omitida.")
            elif not texto(omis.get(f)):
                self.error("ENS-04", f"La función «{f}» no está en ningún plano ni hay motivo de omisión.")
        if "captar" in cubiertas:
            lim = min(0.1 * self.ex.duracion, 8.0)
            t0 = min(self.ex.inicio(p) for p in cubiertas["captar"])
            if t0 > lim + 1e-9:
                self.error("ENS-05", f"La atención se capta a los {t0:.1f} s; debe ocurrir en los primeros {lim:.1f} s.")
        if self.ex.planos and "cerrar" not in como_lista(self.ex.planos[-1].get("funcion_didactica")):
            self.error("ENS-10", "El último plano debe cumplir la función «cerrar».")
        dem_vis = [p for p in cubiertas.get("demostrar", []) if p.get("canal") == "visual"]
        if not dem_vis:
            self.error("ENS-06", "Mostrar, no solo decir: ningún plano demuestra la idea con canal visual.")
        # conceptos y gradualidad
        conceptos = {c.get("id"): c for c in como_lista(es.get("conceptos")) if isinstance(c, dict)}
        pos = {}
        for i, p in enumerate(self.ex.planos):
            for j, cid in enumerate(como_lista(p.get("introduce"))):
                if cid not in conceptos:
                    self.error("ENS-07", f"Introduce el concepto desconocido «{cid}».", p.get("id"))
                elif cid in pos:
                    self.aviso("ENS-07", f"El concepto «{cid}» se introduce más de una vez (la primera cuenta).", p.get("id"))
                else:
                    pos[cid] = (i, j)
        for cid, c in conceptos.items():
            if not texto(c.get("texto")):
                self.error("ENS-07", f"Concepto «{cid}» sin texto.")
            if cid not in pos:
                self.error("ENS-07", f"El concepto «{cid}» nunca se introduce en un plano.")
                continue
            for r in como_lista(c.get("requiere")):
                if r not in conceptos:
                    self.error("ENS-07", f"«{cid}» requiere un concepto inexistente «{r}».")
                elif r in pos and pos[r] >= pos[cid]:
                    self.error("ENS-07", f"Gradualidad: «{cid}» aparece antes que «{r}», en el que se apoya.",
                               self.ex.planos[pos[cid][0]].get("id"))
        cc = es.get("concepto_central")
        if cc:
            if cc not in pos:
                self.error("ENS-06", f"El concepto central «{cc}» no se introduce en ningún plano.")
            else:
                p = self.ex.planos[pos[cc][0]]
                if "demostrar" not in como_lista(p.get("funcion_didactica")) or p.get("canal") != "visual":
                    self.error("ENS-06", f"El concepto central «{cc}» se introduce en {p.get('id')}, que no lo demuestra visualmente.")
        # símbolos
        for s in como_lista(es.get("simbolos")):
            if not isinstance(s, dict):
                continue
            sid = s.get("id")
            if not texto(s.get("significa")):
                self.error("ENS-08", f"El símbolo «{sid}» no declara qué significa (un símbolo remite a algo).")
            a, b = s.get("siembra"), s.get("cosecha")
            if a not in self.ex.indice or b not in self.ex.indice:
                self.error("ENS-08", f"El símbolo «{sid}» necesita siembra y cosecha en planos existentes ({a} → {b}).")
            elif self.ex.indice[a] >= self.ex.indice[b]:
                self.error("ENS-08", f"El símbolo «{sid}» se cosecha ({b}) antes o a la vez que se siembra ({a}).")
        # comprobación
        comp = [c for c in como_lista(es.get("comprobacion")) if isinstance(c, dict)]
        if len(comp) < 2:
            self.error("ENS-09", f"Hacen falta al menos 2 preguntas de comprobación; hay {len(comp)}.")
        if comp and not any(c.get("canal") == "visual" for c in comp):
            self.error("ENS-09", "Al menos una pregunta de comprobación debe responderse con la imagen (canal visual).")
        for c in comp:
            if not texto(c.get("pregunta")) or not c["pregunta"].strip().endswith("?"):
                self.error("ENS-09", "Pregunta de comprobación vacía o sin formular como pregunta.")
            if not texto(c.get("respuesta")):
                self.error("ENS-09", f"La pregunta «{c.get('pregunta')}» no tiene respuesta esperada.")
            for pid in como_lista(c.get("planos")) or [None]:
                if pid not in self.ex.indice:
                    self.error("ENS-09", f"La pregunta «{c.get('pregunta')}» se apoya en un plano inexistente: {pid}.")

    # ── CRE ──────────────────────────────────────────────────────────────────────────
    def r_creacion(self):
        cr = self.seccion("creacion")
        ideas = [i for i in como_lista(cr.get("ideas")) if isinstance(i, dict)]
        if len(ideas) < 3:
            self.error("CRE-01", f"Genera al menos 3 ideas de representación; hay {len(ideas)}.")
        puntos = self._criterios(ideas, "CRE-01", "ideas")
        el = cr.get("elegida")
        if el not in [i.get("id") for i in ideas]:
            self.error("CRE-01", f"creacion.elegida «{el}» no es ninguna de las ideas.")
        elif not texto(cr.get("justificacion")):
            self.error("CRE-01", "Falta la justificación de la idea elegida.")
        elif puntos and puntos.get(el, 0) < max(puntos.values()):
            self.aviso("CRE-01", f"La idea elegida ({el}) no es la de mayor puntuación; justifícalo.")
        est = cr.get("estilo") or {}
        for k in ("paleta", "luz"):
            if not texto(est.get(k)):
                self.error("CRE-02", f"creacion.estilo.{k} vacío: el plano del estilo se define antes de producir.")
        for ef in como_lista(est.get("efectos")):
            if not isinstance(ef, dict) or not texto(ef.get("aporta")):
                nombre = ef.get("nombre") if isinstance(ef, dict) else ef
                self.error("CRE-02", f"El efecto «{nombre}» no declara qué aporta al mensaje (filtro de vanidad).")
        self._coste(cr.get("coste") or {}, "CRE-03", "estimado")

    def _coste(self, c, cod, etiqueta, ms=None):
        ms = ms if ms is not None else c.get("ms_fotograma")
        if ms is None:
            self.error(cod, "Calcula el costo: falta ms_fotograma.")
            return
        frames = round(self.ex.duracion * self.ex.fps)
        total = frames * float(ms) / 1000 + float(c.get("precomputo_s") or 0) + float(c.get("audio_s") or 0)
        if self.ex.duracion <= 0:
            return
        ratio = total / self.ex.duracion
        msg = (f"Render {etiqueta}: {frames} fotogramas × {float(ms):.1f} ms + precómputo y audio = {total:.1f} s "
               f"para {self.ex.duracion:.1f} s de vídeo ({ratio:.2f}×).")
        if ratio > RATIO_MAX:
            self.error(cod, msg + f" Supera el máximo de {RATIO_MAX}×: simplifica el diseño antes de producir.")
        elif ratio > RATIO_OBJETIVO:
            self.aviso(cod, msg + " Cabe en el máximo, pero supera la duración del vídeo.")

    # ── NAR: escenas ─────────────────────────────────────────────────────────────────
    def r_escenas(self):
        personajes = self.ex.biblia.get("personajes") or {}
        lugares = self.ex.biblia.get("lugares") or {}
        paletas = self.ex.biblia.get("paletas") or {}
        usadas = {p.get("escena") for p in self.ex.planos}
        for k, e in enumerate(self.ex.escenas_lista):
            eid = e.get("id")
            for campo in ("lugar", "momento", "funcion", "conecta"):
                if not texto(e.get(campo)):
                    cod = "NAR-08" if campo in ("funcion", "conecta") else "GEN-01"
                    self.error(cod, f"La escena no declara «{campo}».", eid)
            if e.get("lugar") and e.get("lugar") not in lugares:
                self.error("GEN-03", f"Lugar «{e.get('lugar')}» no definido en biblia.lugares.", eid)
            tr = e.get("transicion") or {}
            if not texto(tr.get("tipo")):
                self.error("NAR-08", "Falta el tipo de transición de entrada.", eid)
            if k > 0 and not texto(tr.get("puente")):
                self.error("NAR-08", "La transición no tiene puente (sonoro o visual): las escenas se unen por coyunturas, no a saltos.", eid)
            if eid not in usadas:
                self.error("NAR-08", "La escena no tiene ningún plano.", eid)
            pres = como_lista(e.get("personajes"))
            for p in pres:
                if p not in personajes:
                    self.error("GEN-03", f"Personaje «{p}» no definido en la biblia.", eid)
            ves = e.get("vestuario") or {}
            for p in pres:
                if p not in ves:
                    self.error("CON-05", f"No se declara el vestuario de «{p}».", eid)
                elif ves[p] not in ((personajes.get(p) or {}).get("vestuario") or {}):
                    self.error("CON-05", f"Vestuario «{ves[p]}» de «{p}» no existe en la biblia.", eid)
            eje = como_lista(e.get("eje"))
            if eje and (len(eje) != 2 or any(x not in pres and x not in (self.ex.biblia.get("objetos") or {}) for x in eje)):
                self.error("CON-01", f"El eje de acción debe ser dos sujetos presentes: {eje}.", eid)
            if len(pres) >= 2 and not eje:
                self.error("CON-01", "Hay dos o más personajes y no se declara el eje de acción.", eid)
            if e.get("paleta") and e.get("paleta") not in paletas:
                self.aviso("CON-09", f"Paleta «{e.get('paleta')}» no definida en la biblia.", eid)
            luz = e.get("luz") or {}
            for campo in ("hora", "clima", "clave"):
                if not texto(luz.get(campo)):
                    self.error("CON-08", f"La luz de la escena no declara «{campo}».", eid)
        # continuidad entre escenas consecutivas continuas
        for a, b in zip(self.ex.escenas_lista, self.ex.escenas_lista[1:]):
            if not self.ex.escenas_continuas(a, b):
                continue
            if (a.get("vestuario") or {}) != (b.get("vestuario") or {}) and not texto(b.get("cambio_vestuario")):
                self.error("CON-05", f"{a.get('id')} y {b.get('id')} son continuas pero el vestuario cambia sin motivo declarado.", b.get("id"))
            la, lb = a.get("luz") or {}, b.get("luz") or {}
            if any(la.get(k) != lb.get(k) for k in ("hora", "clima", "clave")) and not texto(b.get("cambio_luz")):
                self.error("CON-08", f"{a.get('id')} y {b.get('id')} son continuas pero la luz cambia sin motivo declarado.", b.get("id"))
            if not (set(como_lista(a.get("personajes"))) <= set(como_lista(b.get("personajes")))) and not texto(b.get("salidas")):
                self.aviso("CON-06", f"Alguien presente en {a.get('id')} desaparece en {b.get('id')} (continuas) sin declarar su salida.", b.get("id"))

    # ── NAR: planos ──────────────────────────────────────────────────────────────────
    def r_planos(self):
        ex = self.ex
        tol = 0.5 / ex.fps
        t_esperado = 0.0
        personajes = ex.biblia.get("personajes") or {}
        objetos = ex.biblia.get("objetos") or {}
        mismo_tamano = 1
        for i, p in enumerate(ex.planos):
            pid = p.get("id")
            esc = ex.escena_de(p)
            if not esc:
                self.error("GEN-03", f"Escena «{p.get('escena')}» inexistente.", pid)
            ini, dur = p.get("inicio"), p.get("duracion")
            if not isinstance(ini, (int, float)) or not isinstance(dur, (int, float)) or dur <= 0:
                self.error("NAR-01", "inicio y duración deben ser números (duración > 0).", pid)
                continue
            if abs(ini - t_esperado) > tol:
                tipo = "hueco" if ini > t_esperado else "solape"
                self.error("NAR-01", f"Línea de tiempo: {tipo} de {abs(ini - t_esperado):.3f} s (empieza en {ini}, se esperaba {t_esperado:.3f}).", pid)
            t_esperado = ini + dur
            if abs(dur * ex.fps - round(dur * ex.fps)) > 1e-6:
                self.aviso("NAR-01", f"La duración {dur} s no es un número entero de fotogramas a {ex.fps:g} fps.", pid)
            if dur < 1.0:
                self.error("NAR-02", f"Plano de {dur} s: por debajo de 1 s no se lee.", pid)
            elif dur < 1.5 and not texto(p.get("ritmo")):
                self.aviso("NAR-02", f"Plano corto ({dur} s); declara «ritmo» si es intencional.", pid)
            for campo in ("muestra", "funcion_narrativa", "sonido"):
                if not texto(p.get(campo)):
                    self.error("NAR-03", f"Falta «{campo}»: ningún plano sin función.", pid)
            if not como_lista(p.get("funcion_didactica")):
                self.error("NAR-03", "Falta «funcion_didactica».", pid)
            if p.get("canal") not in CANALES:
                self.error("NAR-03", f"canal debe ser uno de {CANALES}.", pid)
            if p.get("tamano") not in TAMANOS:
                self.error("NAR-03", f"tamano debe ser uno de {TAMANOS}.", pid)
            cam = p.get("camara") or {}
            if cam.get("lado") not in ("A", "B"):
                self.error("NAR-03", "camara.lado debe ser A o B (lado del eje de acción).", pid)
            for campo in ("angulo", "movimiento"):
                if not texto(cam.get(campo)):
                    self.error("NAR-03", f"camara.{campo} vacío.", pid)
            suj = p.get("sujetos") or {}
            pres = set(como_lista(esc.get("personajes")))
            for s, info in suj.items():
                if s not in pres and s not in objetos:
                    self.error("CON-06", f"«{s}» aparece en el plano pero no está presente en la escena {esc.get('id')} ni es un objeto de la biblia.", pid)
                if not isinstance(info, dict):
                    continue
                x = info.get("x")
                if x is not None and not (0 <= float(x) <= 1):
                    self.error("NAR-04", f"x de «{s}» fuera del encuadre (0–1).", pid)
            self._composicion(p, pid)
            self._dialogo(p, pid, pres)
            self._texto_pantalla(p, pid)
            # regla de 30° y variedad
            if i > 0:
                q = ex.planos[i - 1]
                mismo_tamano = mismo_tamano + 1 if q.get("tamano") == p.get("tamano") else 1
                if q.get("escena") == p.get("escena") and q.get("tamano") == p.get("tamano"):
                    cq = q.get("camara") or {}
                    pq = (q.get("composicion") or {}).get("principal")
                    pp = (p.get("composicion") or {}).get("principal")
                    if (cq.get("lado"), cq.get("angulo")) == (cam.get("lado"), cam.get("angulo")) and pq == pp \
                            and not texto(p.get("salto_intencional")):
                        self.error("NAR-09", f"Corte en salto: {q.get('id')} y {pid} tienen el mismo tamaño, lado, ángulo y sujeto "
                                             "(regla de 30°). Cambia el tamaño o el ángulo, o declara «salto_intencional».", pid)
                if mismo_tamano > 4:
                    self.aviso("NAR-10", f"Más de 4 planos seguidos de tamaño {p.get('tamano')}: ritmo monótono.", pid)
        if ex.planos and abs(t_esperado - ex.duracion) > tol:
            self.error("NAR-01", f"Los planos suman {t_esperado:.3f} s pero duracion_s es {ex.duracion} s.")

    def _composicion(self, p, pid):
        comp = p.get("composicion") or {}
        suj = p.get("sujetos") or {}
        regla, princ = comp.get("regla"), comp.get("principal")
        if regla not in REGLAS_COMPOSICION:
            self.error("NAR-04", f"composicion.regla debe ser uno de {REGLAS_COMPOSICION}.", pid)
        if not princ:
            self.error("NAR-04", "Falta el centro de interés (composicion.principal).", pid)
            return
        if princ not in suj:
            self.error("NAR-04", f"El principal «{princ}» no figura entre los sujetos del plano.", pid)
            return
        for s in como_lista(comp.get("secundarios")):
            if s not in suj and s not in (self.ex.biblia.get("objetos") or {}):
                self.error("NAR-04", f"Secundario «{s}» no figura entre los sujetos ni los objetos.", pid)
        if not texto(p.get("excluye")):
            self.aviso("NAR-04", "No se declara qué queda fuera del cuadro (encuadrar es también excluir).", pid)
        info = suj[princ] if isinstance(suj[princ], dict) else {}
        x, y = info.get("x"), info.get("y")
        if x is None:
            self.error("NAR-04", f"El principal «{princ}» no tiene posición x.", pid)
            return
        x = float(x)
        if regla == "tercios":
            if min(abs(x - 1 / 3), abs(x - 2 / 3)) > 0.08:
                self.error("NAR-04", f"Regla de tercios: el principal está en x={x:.2f}, lejos de 0,33/0,67.", pid)
            if y is not None and min(abs(float(y) - 1 / 3), abs(float(y) - 2 / 3)) > 0.08:
                self.error("NAR-04", f"Regla de tercios: el principal está en y={float(y):.2f}, lejos de 0,33/0,67.", pid)
        elif regla in ("centrada", "simetrica"):
            if abs(x - 0.5) > 0.06:
                self.error("NAR-04", f"Composición {regla}: el principal está en x={x:.2f}, no centrado.", pid)
        elif regla == "libre" and not texto(comp.get("motivo")):
            self.error("NAR-04", "Composición libre sin motivo.", pid)
        # aire en la dirección de mirada o movimiento
        for clave in ("mira", "mueve"):
            dirc = info.get(clave)
            if dirc == "derecha" and x > 0.62 or dirc == "izquierda" and x < 0.38:
                self.aviso("NAR-05", f"«{princ}» {clave} hacia la {dirc} pegado a ese borde (x={x:.2f}): falta aire.", pid)

    def _dialogo(self, p, pid, pres):
        lineas = [l for l in como_lista(p.get("dialogo")) if isinstance(l, dict)]
        if not lineas:
            return
        n = sum(palabras(l.get("texto", "")) for l in lineas)
        dur = float(p.get("duracion") or 1)
        vel = n / dur
        if vel > 3.3:
            self.error("NAR-06", f"Diálogo demasiado rápido: {n} palabras en {dur} s ({vel:.1f} palabras/s; recomendado ≤ 2,8, máximo 3,3).", pid)
        elif vel > 2.8:
            self.aviso("NAR-06", f"Diálogo rápido: {vel:.1f} palabras/s (recomendado ≤ 2,8).", pid)
        for l in lineas:
            q = l.get("quien")
            if q not in pres and q not in ("narrador", "voz_en_off"):
                self.error("NAR-06", f"Habla «{q}», que no está presente en la escena.", pid)

    def _texto_pantalla(self, p, pid):
        tp = p.get("texto_pantalla")
        if not tp:
            return
        if isinstance(tp, str):
            tp = {"texto": tp, "desde": 0}
        txt = tp.get("texto", "")
        disp = float(p.get("duracion") or 0) - float(tp.get("desde") or 0)
        nec = len(txt) / 15 + 1.0
        if disp < nec:
            self.error("NAR-07", f"El rótulo necesita {nec:.1f} s para leerse ({len(txt)} caracteres) y solo dispone de {disp:.1f} s.", pid)

    # ── CON ──────────────────────────────────────────────────────────────────────────
    def r_continuidad(self):
        ex = self.ex
        estados, incid = ex.simular()
        for cod, pid, msg in incid:
            self.error(cod, msg, pid)
        personajes = ex.biblia.get("personajes") or {}
        ultimo_lado = {}       # bloque → lado
        ultima_dir = {}        # (bloque, sujeto) → dirección lateral
        for i, p in enumerate(ex.planos):
            pid = p.get("id")
            st = estados[i]
            cam = p.get("camara") or {}
            lado = cam.get("lado")
            b = st["bloque"]
            # CON-01 eje de 180°
            if b in ultimo_lado and lado != ultimo_lado[b] and not texto(cam.get("cruce_eje")):
                self.error("CON-01", f"La cámara cruza el eje ({ultimo_lado[b]} → {lado}) en escenas continuas sin motivo "
                                     "(movimiento de cámara visible, plano neutro o nuevo eje).", pid)
            ultimo_lado[b] = lado
            suj = p.get("sujetos") or {}
            eje, izq = st["eje"], st["izquierda"]
            # CON-02 posiciones relativas
            if izq and len(eje) == 2 and all(isinstance(suj.get(m), dict) and suj[m].get("x") is not None for m in eje):
                der = eje[1] if izq == eje[0] else eje[0]
                if float(suj[izq]["x"]) >= float(suj[der]["x"]):
                    self.error("CON-02", f"Posiciones relativas: «{izq}» debería estar a la izquierda de «{der}» "
                                         f"(lado {lado}{', tras el cruce' if izq != (eje[0] if lado == 'A' else eje[1]) else ''}).", pid)
            for s, info in suj.items():
                if not isinstance(info, dict):
                    continue
                # CON-03 raccord de mirada
                obj = info.get("mira_a")
                if obj and info.get("mira") in LATERALES:
                    esperado = ex.direccion_hacia(pid, s, obj)
                    if esperado and info["mira"] != esperado:
                        self.error("CON-03", f"«{s}» mira a «{obj}» hacia la {info['mira']}, pero «{obj}» está a la {esperado} "
                                             "según el eje.", pid)
                # CON-04 dirección de movimiento
                mv = info.get("mueve")
                if isinstance(mv, str) and mv.startswith("hacia:"):
                    mv = ex.direccion_hacia(pid, s, mv.split(":", 1)[1])
                if mv in LATERALES:
                    clave = (b, s)
                    if clave in ultima_dir and ultima_dir[clave] != mv and not texto(info.get("cambio_direccion")):
                        self.error("CON-04", f"«{s}» se movía hacia la {ultima_dir[clave]} y ahora hacia la {mv} sin cambio de "
                                             "dirección mostrado.", pid)
                    viaje = (personajes.get(s) or {}).get("direccion_viaje")
                    if viaje in LATERALES:
                        esperado = viaje if lado == "A" else contrario(viaje)
                        if mv != esperado and not texto(info.get("cambio_direccion")):
                            self.error("CON-04", f"«{s}» viaja hacia la {esperado} (lado {lado}) y aquí se mueve hacia la {mv}.", pid)
                    ultima_dir[clave] = mv
            # CON-08 luz del plano
            luz = p.get("luz")
            if isinstance(luz, dict):
                le = ex.escena_de(p).get("luz") or {}
                if any(luz.get(k) not in (None, le.get(k)) for k in ("hora", "clima", "clave")) and not texto(p.get("cambio_luz")):
                    self.error("CON-08", "La luz del plano difiere de la de su escena sin «cambio_luz».", pid)

    # ── AJU / PRO / ENT ──────────────────────────────────────────────────────────────
    def r_ajustes(self):
        for a in como_lista(self.d.get("ajustes")):
            if not isinstance(a, dict):
                continue
            aid = a.get("id", "?")
            for campo in ("problema", "causa", "cambio"):
                if not texto(a.get(campo)):
                    self.error("AJU-01", f"El ajuste no registra «{campo}».", aid)
            if a.get("verificado") is not True:
                msg = "Ajuste sin verificar después del cambio."
                (self.error if self.desde("final") else self.aviso)("AJU-01", msg, aid)
            elif not texto(a.get("evidencia")):
                self.error("AJU-01", "Ajuste verificado sin evidencia.", aid)

    def r_prototipo(self):
        pr = self.seccion("prototipo", "PRO-01")
        est = pr.get("estado")
        if est not in ESTADOS_PROTOTIPO:
            self.error("PRO-01", f"prototipo.estado debe ser uno de {ESTADOS_PROTOTIPO}.")
        elif est == "omitido_por_usuario":
            if not texto(pr.get("cita")):
                self.error("PRO-01", "Prototipo omitido: cita las palabras del usuario que lo piden.")
        elif est != "aprobado":
            self.error("PRO-01", f"El prototipo está «{est}»: la producción completa espera la aprobación del usuario.")
        if est != "omitido_por_usuario":
            if pr.get("ms_fotograma_medido") is None:
                self.error("PRO-02", "Falta prototipo.ms_fotograma_medido (coste medido en un plano real).")
            else:
                self._coste((self.d.get("creacion") or {}).get("coste") or {}, "PRO-02", "medido en el prototipo",
                            ms=pr["ms_fotograma_medido"])

    def r_entrega(self):
        en = self.seccion("entrega", "ENT-01")
        rs = en.get("render_s")
        if not isinstance(rs, (int, float)):
            self.error("ENT-01", "entrega.render_s: mide el render completo de principio a fin.")
        elif self.ex.duracion > 0:
            r = rs / self.ex.duracion
            if r > RATIO_MAX:
                self.error("ENT-01", f"Render de {rs:.1f} s para {self.ex.duracion:.1f} s de vídeo ({r:.2f}×): supera {RATIO_MAX}×.")
            elif r > RATIO_OBJETIVO:
                self.aviso("ENT-01", f"Render de {r:.2f}×: dentro del máximo pero por encima de la duración.")
        rev = en.get("revision")
        datos = None
        if not texto(rev):
            self.error("ENT-02", "entrega.revision: ejecuta metodo.revisar y anota la ruta de revision.json.")
        else:
            ruta = self.ex.carpeta / rev
            if not ruta.exists():
                self.error("ENT-02", f"No existe {ruta}.")
            else:
                datos = json.loads(ruta.read_text(encoding="utf-8"))
        ver = en.get("veredictos") or {}
        if datos:
            for c in datos.get("cortes", []):
                if c.get("marcado") and not texto(ver.get(c["id"])):
                    self.error("ENT-02", f"El corte {c['id']} está marcado ({'; '.join(c.get('motivos', []))}) y no tiene veredicto.")
            t = datos.get("entrega") or {}
            res = self.d.get("resolucion") or [0, 0]
            if [t.get("ancho"), t.get("alto")] != list(res):
                self.error("ENT-03", f"Resolución {t.get('ancho')}×{t.get('alto')}; el plan dice {res[0]}×{res[1]}.")
            if t.get("fps") is None or abs(float(t["fps"]) - self.ex.fps) > 0.01:
                self.error("ENT-03", f"fps {t.get('fps')}; el plan dice {self.ex.fps:g}.")
            if t.get("duracion") is None or abs(float(t["duracion"]) - self.ex.duracion) > 1.5 / self.ex.fps:
                self.error("ENT-03", f"Duración {t.get('duracion')} s; el plan dice {self.ex.duracion} s.")
            lufs, pico = t.get("lufs"), t.get("pico_dbtp")
            if lufs is None or not (LUFS_MIN <= lufs <= LUFS_MAX):
                self.error("ENT-03", f"Sonoridad integrada {lufs} LUFS; debe estar entre {LUFS_MIN} y {LUFS_MAX}.")
            if pico is None or pico > PICO_MAX:
                self.error("ENT-03", f"Pico real {pico} dBTP; máximo {PICO_MAX}.")
        rm = en.get("revision_manual") or {}
        for cod, preg in REVISION_MANUAL.items():
            if not texto(rm.get(cod)):
                self.error("ENT-04", f"Falta la revisión manual {cod}: {preg}")


def verificar(ruta_o_expediente, fase="plan") -> Verificador:
    ex = ruta_o_expediente if isinstance(ruta_o_expediente, Expediente) else cargar(ruta_o_expediente)
    return Verificador(ex, fase).ejecutar()


def informe(v: Verificador) -> str:
    out = [f"Expediente: {v.d.get('titulo', '¿sin título?')}  ·  fase: {v.fase}"]
    for marca, lista in (("✗", v.errores), ("!", v.avisos)):
        for cod, donde, msg in lista:
            out.append(f"  {marca} {cod:7s} {('[' + str(donde) + '] ') if donde else ''}{msg}")
    estado = "PUERTA SUPERADA" if not v.errores else "NO SUPERADA"
    out.append(f"{len(v.errores)} errores, {len(v.avisos)} avisos → {estado}")
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Verifica un expediente contra el método.")
    ap.add_argument("expediente")
    ap.add_argument("--fase", choices=FASES, default="plan")
    args = ap.parse_args(argv)
    v = verificar(args.expediente, args.fase)
    print(informe(v))
    return 1 if v.errores else 0


if __name__ == "__main__":
    sys.exit(main())

"""Carga del expediente de un vídeo y utilidades para el código de producción.

El expediente (YAML) es la fuente única de verdad. El código que renderiza lee de aquí:

- los tiempos de cada plano;
- el lado de cámara y las direcciones en pantalla;
- el estado de los objetos.

Así el plan verificado y el vídeo no pueden divergir.
"""
from __future__ import annotations

import math
from pathlib import Path

import yaml

LATERALES = ("derecha", "izquierda")


def contrario(d):
    return {"derecha": "izquierda", "izquierda": "derecha"}.get(d, d)


def cargar(ruta) -> "Expediente":
    ruta = Path(ruta)
    with open(ruta, encoding="utf-8") as f:
        datos = yaml.safe_load(f) or {}
    return Expediente(datos, ruta)


def como_lista(v):
    if v is None:
        return []
    if isinstance(v, (list, tuple)):
        return list(v)
    return [v]


class Expediente:
    def __init__(self, datos: dict, ruta: Path | None = None):
        self.d = datos if isinstance(datos, dict) else {}
        self.ruta = Path(ruta) if ruta else None
        self.carpeta = self.ruta.parent if self.ruta else Path(".")
        self.fps = float(self.d.get("fps") or 24)
        self.duracion = float(self.d.get("duracion_s") or 0)
        self.escenas_lista = [e for e in como_lista(self.d.get("escenas")) if isinstance(e, dict)]
        self.escenas = {e.get("id"): e for e in self.escenas_lista}
        self.planos = [p for p in como_lista(self.d.get("planos")) if isinstance(p, dict)]
        self.indice = {p.get("id"): i for i, p in enumerate(self.planos)}
        self._sim = None

    # ── acceso básico ────────────────────────────────────────────────────────────────
    def seccion(self, nombre) -> dict:
        v = self.d.get(nombre)
        return v if isinstance(v, dict) else {}

    @property
    def biblia(self) -> dict:
        return self.seccion("biblia")

    def plano(self, pid) -> dict:
        return self.planos[self.indice[pid]]

    def escena_de(self, plano) -> dict:
        return self.escenas.get(plano.get("escena"), {})

    def inicio(self, plano) -> float:
        return float(plano.get("inicio") or 0)

    def fin(self, plano) -> float:
        return self.inicio(plano) + float(plano.get("duracion") or 0)

    def fotograma_de(self, t: float) -> int:
        """Primer fotograma que muestra el instante t.

        Convención (la misma del motor): el fotograma f muestra el instante f/fps, y un plano está
        activo desde el primer fotograma con f/fps ≥ inicio. Si los tiempos del expediente son
        múltiplos de 1/fps (aviso NAR-01), redondear y tomar el techo coinciden.
        """
        return math.ceil(t * self.fps - 1e-6)

    def fotogramas(self, plano):
        """Fotogramas [f0, f1) del plano."""
        if isinstance(plano, str):
            plano = self.plano(plano)
        return self.fotograma_de(self.inicio(plano)), self.fotograma_de(self.fin(plano))

    def plano_en(self, t: float) -> dict | None:
        for p in self.planos:
            if self.inicio(p) <= t < self.fin(p):
                return p
        return self.planos[-1] if self.planos and t >= self.fin(self.planos[-1]) else None

    # ── continuidad ──────────────────────────────────────────────────────────────────
    def escenas_continuas(self, a: dict, b: dict) -> bool:
        """Dos escenas son continuas si comparten lugar y momento (no hay salto de tiempo)."""
        if not a or not b:
            return False
        if a is b:
            return True
        return (a.get("lugar") is not None and a.get("lugar") == b.get("lugar")
                and a.get("momento") is not None and a.get("momento") == b.get("momento"))

    def continuo_con_anterior(self, i: int) -> bool:
        if i <= 0:
            return False
        return self.escenas_continuas(self.escena_de(self.planos[i - 1]), self.escena_de(self.planos[i]))

    def simular(self):
        """Recorre los planos en orden y calcula el estado del mundo al inicio de cada uno.

        Devuelve (estados, incidencias):

        - estados[i] = dict(objetos, izquierda, eje, bloque) al inicio del plano i, donde
          izquierda es el miembro del eje que ocupa el lado izquierdo de la pantalla;
        - incidencias = lista de (codigo, plano_id, mensaje) con los fallos de continuidad de
          objetos (CON-07). El verificador las reporta.
        """
        if self._sim is not None:
            return self._sim
        objetos_def = self.biblia.get("objetos") or {}
        mundo = {k: (v or {}).get("inicial") for k, v in objetos_def.items() if isinstance(v, dict)}
        permitidas = {}
        for k, v in objetos_def.items():
            pares = set()
            for tr in como_lista((v or {}).get("transiciones")):
                if isinstance(tr, (list, tuple)) and len(tr) >= 2:
                    pares.add((tr[0], tr[1]))
            permitidas[k] = pares
        estados, incid = [], []
        invertido = False
        bloque = -1
        for i, p in enumerate(self.planos):
            pid = p.get("id")
            esc = self.escena_de(p)
            continuo = self.continuo_con_anterior(i)
            if not continuo:
                bloque += 1
                invertido = False
                # cambios fuera de campo: solo en saltos de tiempo o lugar
                for c in como_lista(esc.get("cambios_fuera_de_campo")) if self._primer_plano_de_escena(i) else []:
                    if not isinstance(c, dict):
                        continue
                    o, a = c.get("objeto"), c.get("a")
                    if o not in mundo:
                        incid.append(("CON-07", pid, f"Cambio fuera de campo de un objeto que no está en la biblia: «{o}»."))
                        continue
                    if not c.get("motivo"):
                        incid.append(("CON-07", pid, f"El cambio fuera de campo de «{o}» no tiene motivo."))
                    mundo[o] = a
            elif self._primer_plano_de_escena(i) and esc.get("cambios_fuera_de_campo"):
                incid.append(("CON-07", pid, f"La escena {esc.get('id')} es continua con la anterior (mismo lugar y momento): "
                                             "no puede haber cambios de objetos fuera de campo."))
            eje = como_lista(esc.get("eje"))
            lado = (p.get("camara") or {}).get("lado", "A")
            izquierda = None
            if len(eje) == 2:
                base = eje[0] if lado == "A" else eje[1]
                otro = eje[1] if base == eje[0] else eje[0]
                izquierda = otro if invertido else base
            estados.append(dict(objetos=dict(mundo), izquierda=izquierda, eje=eje, bloque=bloque, lado=lado))
            # estados visibles declarados al inicio del plano
            for o, est in (p.get("objetos") or {}).items():
                if o not in mundo:
                    incid.append(("CON-07", pid, f"Objeto «{o}» no definido en la biblia."))
                elif mundo[o] != est:
                    incid.append(("CON-07", pid, f"«{o}» aparece como «{est}» pero su estado en este momento es «{mundo[o]}» "
                                                 "(reaparece o cambia sin causa)."))
            # eventos del plano, en orden temporal
            dur = float(p.get("duracion") or 0)
            evs = [e for e in como_lista(p.get("eventos")) if isinstance(e, dict) and "objeto" in e]
            for e in sorted(evs, key=lambda e: float(e.get("t", 0))):
                o, a = e.get("objeto"), e.get("a")
                t = float(e.get("t", 0))
                if not (0 <= t <= dur + 1e-9):
                    incid.append(("CON-07", pid, f"Evento de «{o}» en t={t} s, fuera del plano (0–{dur} s)."))
                if o not in mundo:
                    incid.append(("CON-07", pid, f"Evento sobre un objeto que no está en la biblia: «{o}»."))
                    continue
                de = e.get("de", mundo[o])
                if de != mundo[o]:
                    incid.append(("CON-07", pid, f"El evento «{e.get('causa', '')}» supone que «{o}» está «{de}», "
                                                 f"pero en ese momento está «{mundo[o]}»."))
                elif (mundo[o], a) not in permitidas.get(o, set()):
                    incid.append(("CON-07", pid, f"Transición no permitida para «{o}»: «{mundo[o]}» → «{a}» "
                                                 "(añádela a la biblia con su causa o corrige el evento)."))
                mundo[o] = a
            if (p.get("cruce") or {}).get("motivo"):
                invertido = not invertido
        self._sim = (estados, incid)
        return self._sim

    def _primer_plano_de_escena(self, i):
        return i == 0 or self.planos[i - 1].get("escena") != self.planos[i].get("escena")

    # ── utilidades para producción ─────────────────────────────────────────────────────
    def estado_objetos(self, t: float) -> dict:
        """Estado de cada objeto de la biblia en el instante t (s)."""
        estados, _ = self.simular()
        p = self.plano_en(t)
        if p is None:
            return {}
        i = self.indice[p.get("id")]
        mundo = dict(estados[i]["objetos"])
        tl = t - self.inicio(p)
        evs = [e for e in como_lista(p.get("eventos")) if isinstance(e, dict) and "objeto" in e]
        for e in sorted(evs, key=lambda e: float(e.get("t", 0))):
            if float(e.get("t", 0)) <= tl:
                mundo[e["objeto"]] = e.get("a")
        return mundo

    def lado_en_pantalla(self, pid: str, sujeto: str) -> str | None:
        """'izquierda' o 'derecha': lado de la pantalla que ocupa un miembro del eje en el plano."""
        estados, _ = self.simular()
        st = estados[self.indice[pid]]
        if sujeto not in st["eje"] or st["izquierda"] is None:
            return None
        return "izquierda" if sujeto == st["izquierda"] else "derecha"

    def direccion_hacia(self, pid: str, sujeto: str, objetivo: str) -> str | None:
        """Dirección en pantalla desde `sujeto` hacia `objetivo`, según el eje de acción.

        Si `sujeto` no es miembro del eje (p. ej. un objeto que rueda hacia un personaje), se
        toma el lado de pantalla del objetivo: hacia el miembro de la izquierda es 'izquierda'.
        """
        lo = self.lado_en_pantalla(pid, objetivo)
        if lo is None:
            return None
        ls = self.lado_en_pantalla(pid, sujeto)
        if ls is not None:
            return contrario(ls) if ls != lo else None
        return lo

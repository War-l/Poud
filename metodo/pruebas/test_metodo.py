"""Pruebas del método: cada regla debe detectar el error que le corresponde.

Se parte de expedientes correctos (los ejemplos). Cada prueba introduce un único error y comprueba
que aparece el código esperado: se aísla la falla y se comprueba que el instrumento la ve.

    python3 -m unittest discover -s metodo/pruebas -v
"""
import copy
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

from metodo.expediente import Expediente, cargar
from metodo.revisar import revisar
from metodo.verificar import Verificador

RAIZ = Path(__file__).resolve().parents[1]
DECISION = RAIZ / "ejemplos" / "la_decision" / "expediente.yaml"
ENVIDIA = RAIZ / "ejemplos" / "envidia" / "expediente.yaml"


def base(ruta):
    with open(ruta, encoding="utf-8") as f:
        return yaml.safe_load(f)


def verificar_dict(d, ruta, fase="plan"):
    return Verificador(Expediente(d, ruta), fase).ejecutar()


def codigos(v):
    return {c for c, _, _ in v.errores}


def plano(d, pid):
    return next(p for p in d["planos"] if p["id"] == pid)


def escena(d, eid):
    return next(e for e in d["escenas"] if e["id"] == eid)


class EjemplosCorrectos(unittest.TestCase):
    def test_la_decision_supera_la_puerta_A(self):
        v = verificar_dict(base(DECISION), DECISION)
        self.assertEqual(v.errores, [], v.errores)

    def test_la_decision_no_pasa_a_produccion_sin_prototipo_ni_aprobacion(self):
        v = verificar_dict(base(DECISION), DECISION, "produccion")
        self.assertIn("PRO-01", codigos(v))
        self.assertIn("ENF-09", codigos(v))     # el cambio al guion aún no está aprobado

    def test_envidia_supera_la_fase_de_enfoque(self):
        v = verificar_dict(base(ENVIDIA), ENVIDIA, "enfoque")
        self.assertEqual(v.errores, [], v.errores)
        self.assertTrue(any(c == "ENF-06" for c, _, _ in v.avisos), "el dato no confirmado debe avisarse")


class Continuidad(unittest.TestCase):
    def setUp(self):
        self.d = base(DECISION)

    def comprobar(self, codigo, fase="plan"):
        v = verificar_dict(self.d, DECISION, fase)
        self.assertIn(codigo, codigos(v), f"se esperaba {codigo}; errores: {v.errores}")
        return v

    def test_guion_literal_detecta_la_bolsa(self):
        # Escena 4 tal como dice el guion: «El hombre entrega la bolsa».
        p7 = plano(self.d, "P7")
        p7["objetos"] = {"bolsa": "sostenida_anciana"}
        p7["eventos"] = [{"t": 1.2, "objeto": "bolsa", "de": "en_mano_hombre", "a": "en_mano_anciana",
                          "causa": "el hombre entrega la bolsa"}]
        v = self.comprobar("CON-07")
        self.assertTrue(any("en_mano_hombre" in m for c, _, m in v.errores if c == "CON-07"))

    def test_objeto_que_reaparece(self):
        plano(self.d, "P8")["objetos"] = {"bolsa": "en_mano_anciana", "naranjas": "en_suelo"}
        self.comprobar("CON-07")

    def test_transicion_no_permitida(self):
        plano(self.d, "P4")["eventos"] = [{"t": 1.0, "objeto": "bolsa", "a": "en_mano_anciana"}]
        self.comprobar("CON-07")

    def test_cruce_del_eje_sin_motivo(self):
        plano(self.d, "P4")["camara"]["lado"] = "B"
        self.comprobar("CON-01")

    def test_cruce_del_eje_justificado_no_es_error_de_eje(self):
        plano(self.d, "P4")["camara"].update(lado="B", cruce_eje="movimiento de cámara visible que rodea a la anciana")
        p4 = plano(self.d, "P4")
        p4["sujetos"]["anciana"].update(x=0.36, mira="derecha")   # en el lado B ella queda a la izquierda
        for pid in ("P5", "P6", "P7", "P8"):                      # el resto sigue en el nuevo lado
            plano(self.d, pid)["camara"]["lado"] = "B"
        v = verificar_dict(self.d, DECISION)
        self.assertNotIn("CON-01", codigos(v), v.errores)

    def test_posiciones_relativas(self):
        p6 = plano(self.d, "P6")
        p6["sujetos"]["hombre"]["x"], p6["sujetos"]["anciana"]["x"] = 0.62, 0.40
        self.comprobar("CON-02")

    def test_raccord_de_mirada(self):
        plano(self.d, "P3")["sujetos"]["hombre"]["mira"] = "izquierda"
        self.comprobar("CON-03")

    def test_mirada_tras_el_cruce_cambia_de_lado(self):
        # Tras el cruce de P7, la anciana debe mirar a la derecha para ver al hombre.
        plano(self.d, "P8")["sujetos"]["anciana"]["mira"] = "izquierda"
        self.comprobar("CON-03")

    def test_direccion_de_movimiento(self):
        plano(self.d, "P2")["sujetos"]["hombre"]["mueve"] = "izquierda"
        self.comprobar("CON-04")

    def test_vestuario_inexistente(self):
        escena(self.d, "E3")["vestuario"]["hombre"] = "v2"
        self.comprobar("CON-05")

    def test_vestuario_cambia_en_escenas_continuas(self):
        self.d["biblia"]["personajes"]["hombre"]["vestuario"]["v2"] = "sin chaqueta"
        escena(self.d, "E3")["vestuario"]["hombre"] = "v2"
        self.comprobar("CON-05")

    def test_presencia(self):
        plano(self.d, "P3")["sujetos"]["ciclista"] = {"x": 0.8}
        self.comprobar("CON-06")

    def test_luz_que_cambia(self):
        escena(self.d, "E4")["luz"]["clave"] = "frontal"
        self.comprobar("CON-08")


class Narrativa(unittest.TestCase):
    def setUp(self):
        self.d = base(DECISION)

    def comprobar(self, codigo):
        v = verificar_dict(self.d, DECISION)
        self.assertIn(codigo, codigos(v), f"se esperaba {codigo}; errores: {v.errores}")

    def test_hueco_en_la_linea_de_tiempo(self):
        plano(self.d, "P5")["inicio"] = 15.0
        self.comprobar("NAR-01")

    def test_plano_demasiado_corto(self):
        p = plano(self.d, "P3")
        p["duracion"] = 0.5
        plano(self.d, "P4")["inicio"] = 10.5
        self.comprobar("NAR-02")

    def test_plano_sin_funcion(self):
        del plano(self.d, "P4")["funcion_narrativa"]
        self.comprobar("NAR-03")

    def test_regla_de_tercios(self):
        plano(self.d, "P3")["sujetos"]["hombre"]["x"] = 0.5
        self.comprobar("NAR-04")

    def test_dialogo_demasiado_rapido(self):
        plano(self.d, "P3")["dialogo"] = [{"quien": "hombre", "texto": " ".join(["palabra"] * 12)}]
        self.comprobar("NAR-06")

    def test_rotulo_que_no_se_puede_leer(self):
        plano(self.d, "P8")["texto_pantalla"]["desde"] = 5.0   # el error que el verificador encontró en el ejemplo
        self.comprobar("NAR-07")

    def test_transicion_sin_puente(self):
        escena(self.d, "E3")["transicion"]["puente"] = ""
        self.comprobar("NAR-08")

    def test_corte_en_salto(self):
        p4 = plano(self.d, "P4")
        p4["composicion"]["principal"] = "hombre"
        p4["sujetos"] = {"hombre": {"x": 0.36, "y": 0.34, "mira": "derecha", "mira_a": "anciana"}}
        self.comprobar("NAR-09")


class Ensenanza(unittest.TestCase):
    def setUp(self):
        self.d = base(DECISION)

    def comprobar(self, codigo):
        v = verificar_dict(self.d, DECISION)
        self.assertIn(codigo, codigos(v), f"se esperaba {codigo}; errores: {v.errores}")

    def test_objetivo_no_observable(self):
        self.d["ensenanza"]["objetivo"] = "El espectador podrá entender que las acciones importan."
        self.comprobar("ENS-02")

    def test_funcion_sin_cubrir_ni_justificar(self):
        self.d["ensenanza"]["omisiones"] = {}
        self.comprobar("ENS-04")

    def test_captar_tarde(self):
        plano(self.d, "P1")["funcion_didactica"] = ["contexto"]
        plano(self.d, "P2")["funcion_didactica"] = ["captar", "explicar"]
        self.comprobar("ENS-05")

    def test_mostrar_no_solo_decir(self):
        for pid in ("P6", "P7"):
            plano(self.d, pid)["canal"] = "dialogo"
        self.comprobar("ENS-06")

    def test_gradualidad(self):
        plano(self.d, "P2")["introduce"] = ["decision"]
        plano(self.d, "P5")["introduce"] = ["indiferencia"]
        self.comprobar("ENS-07")

    def test_simbolo_cosechado_antes_de_sembrarse(self):
        self.d["ensenanza"]["simbolos"][0]["cosecha"] = "P1"
        self.comprobar("ENS-08")

    def test_comprobacion_insuficiente(self):
        self.d["ensenanza"]["comprobacion"] = self.d["ensenanza"]["comprobacion"][:1]
        self.comprobar("ENS-09")

    def test_cierre(self):
        plano(self.d, "P8")["funcion_didactica"] = ["demostrar"]
        self.comprobar("ENS-10")


class Creacion(unittest.TestCase):
    def setUp(self):
        self.d = base(DECISION)

    def comprobar(self, codigo):
        v = verificar_dict(self.d, DECISION)
        self.assertIn(codigo, codigos(v), f"se esperaba {codigo}; errores: {v.errores}")

    def test_pocas_ideas(self):
        self.d["creacion"]["ideas"] = self.d["creacion"]["ideas"][:2]
        self.comprobar("CRE-01")

    def test_criterios_desiguales(self):
        self.d["creacion"]["ideas"][2]["criterios"] = {"belleza": 3}
        self.comprobar("CRE-01")

    def test_efecto_sin_aporte(self):
        self.d["creacion"]["estilo"]["efectos"].append({"nombre": "millones de partículas"})
        self.comprobar("CRE-02")

    def test_coste_por_encima_del_maximo(self):
        self.d["creacion"]["coste"]["ms_fotograma"] = 60
        self.comprobar("CRE-03")

    def test_sin_inventario(self):
        self.d["recepcion"]["inventario"] = {}
        self.comprobar("CRE-04")


class Enfoque(unittest.TestCase):
    def setUp(self):
        self.d = base(ENVIDIA)

    def comprobar(self, codigo):
        v = verificar_dict(self.d, ENVIDIA, "enfoque")
        self.assertIn(codigo, codigos(v), f"se esperaba {codigo}; errores: {v.errores}")

    def test_falta_una_pregunta_fundamental(self):
        del self.d["enfoque"]["preguntas"]["naturaleza"]
        self.comprobar("ENF-01")

    def test_sin_delimitar(self):
        self.d["enfoque"]["delimitacion"]["fuera"] = []
        self.comprobar("ENF-02")

    def test_dos_piedras_angulares(self):
        self.d["enfoque"]["hallazgos"][1]["peso"] = "piedra_angular"
        self.comprobar("ENF-03")

    def test_pesas_desiguales(self):
        self.d["enfoque"]["enfoques"][0]["criterios"] = {"fundamento": 3}
        self.comprobar("ENF-04")

    def test_un_solo_testigo(self):
        fu = self.d["enfoque"]["verificacion"]["fuentes"]
        for f in fu[1:]:
            f["verificada"] = False
        self.comprobar("ENF-06")

    def test_sin_contraejemplos(self):
        self.d["enfoque"]["verificacion"]["contraejemplos"] = []
        self.comprobar("ENF-07")

    def test_reformular_sin_cambiar(self):
        enf = self.d["enfoque"]
        enf["verificacion"]["enfoque_final"] = next(e["texto"] for e in enf["enfoques"] if e["id"] == enf["elegido"])
        self.comprobar("ENF-08")

    def test_descartado_no_pasa_a_plan(self):
        self.d["enfoque"]["verificacion"]["veredicto"] = "descartar"
        v = verificar_dict(self.d, ENVIDIA, "plan")
        self.assertIn("ENF-08", codigos(v))

    def test_sin_supuestos(self):
        self.d["enfoque"]["supuestos"] = []
        self.comprobar("ENF-10")


class Produccion(unittest.TestCase):
    """Utilidades que usa el código de producción."""

    def setUp(self):
        self.ex = cargar(DECISION)

    def test_estado_de_objetos_en_el_tiempo(self):
        self.assertEqual(self.ex.estado_objetos(1.0)["bolsa"], "en_mano_anciana")
        self.assertEqual(self.ex.estado_objetos(5.0)["bolsa"], "en_suelo")
        self.assertEqual(self.ex.estado_objetos(20.0)["bolsa"], "sostenida_anciana")
        self.assertEqual(self.ex.estado_objetos(27.5)["bolsa"], "en_mano_anciana")
        self.assertEqual(self.ex.estado_objetos(27.5)["ultima_naranja"], "en_bolsa")

    def test_direcciones_en_pantalla(self):
        self.assertEqual(self.ex.lado_en_pantalla("P1", "hombre"), "izquierda")
        self.assertEqual(self.ex.direccion_hacia("P3", "hombre", "anciana"), "derecha")
        self.assertEqual(self.ex.direccion_hacia("P2", "ultima_naranja", "hombre"), "izquierda")
        self.assertEqual(self.ex.lado_en_pantalla("P8", "anciana"), "izquierda")   # tras el cruce

    def test_fotogramas_exactos(self):
        self.assertEqual(self.ex.fotogramas("P2"), (144, 240))
        self.assertEqual(self.ex.plano_en(10.0)["id"], "P3")

    def test_convencion_del_motor_para_tiempos_no_alineados(self):
        # Hallado en la calibración: el motor cambia de plano en el primer fotograma con t ≥ inicio.
        self.assertEqual(self.ex.fotograma_de(16.92), 407)      # 16,92 × 24 = 406,08 → 407
        self.assertEqual(self.ex.fotograma_de(6.0), 144)        # alineado: sin cambio


class Medicion(unittest.TestCase):
    def test_bandas_negras_no_cuentan_como_sombras(self):
        import numpy as np
        from metodo.revisar import metricas, sin_bandas
        img = np.zeros((100, 160, 3), np.uint8)
        img[20:80] = (200, 120, 60)               # imagen naranja entre bandas negras
        self.assertEqual(sin_bandas(img).shape[0], 60)
        m = metricas(img)
        self.assertGreater(m["sombras"][1], 20)   # b* de la imagen, no el 0 de las bandas


class Entrega(unittest.TestCase):
    """Puerta C con una entrega simulada (revision.json escrito a mano)."""

    def preparar(self, **cambios):
        tmp = Path(tempfile.mkdtemp())
        (tmp / "guion.md").write_text("guion", encoding="utf-8")
        d = base(DECISION)
        d["enfoque"]["cambios_guion"][0]["aprobado_usuario"] = True
        d["prototipo"] = {"estado": "aprobado", "ms_fotograma_medido": 34}
        rev = {"entrega": {"ancho": 1920, "alto": 1080, "fps": 24.0, "duracion": 40.0, "lufs": -16.0, "pico_dbtp": -1.5},
               "cortes": [{"id": "P5>P6", "marcado": True, "motivos": ["salto de exposición"]}]}
        rev["entrega"].update(cambios.pop("tecnica", {}))
        (tmp / "revision").mkdir()
        (tmp / "revision" / "revision.json").write_text(json.dumps(rev), encoding="utf-8")
        d["entrega"] = {"archivo": "la_decision.mp4", "render_s": 37.0, "revision": "revision/revision.json",
                        "veredictos": {"P5>P6": "correcto: el PP en sombra es intencional (testigos: medición y hoja)"},
                        "revision_manual": {k: "ok: comprobado en la hoja" for k in
                                            ("REV-01", "REV-02", "REV-03", "REV-04", "REV-05", "REV-06", "REV-07", "REV-08", "REV-09")}}
        d["entrega"].update(cambios)
        return Verificador(Expediente(d, tmp / "expediente.yaml"), "final").ejecutar()

    def test_entrega_correcta_supera_la_puerta_C(self):
        v = self.preparar()
        self.assertEqual(v.errores, [], v.errores)

    def test_render_mas_lento_que_el_maximo(self):
        self.assertIn("ENT-01", codigos(self.preparar(render_s=45.0)))

    def test_corte_marcado_sin_veredicto(self):
        self.assertIn("ENT-02", codigos(self.preparar(veredictos={})))

    def test_sonoridad_fuera_de_rango(self):
        self.assertIn("ENT-03", codigos(self.preparar(tecnica={"lufs": -23.0})))

    def test_resolucion_distinta_del_plan(self):
        self.assertIn("ENT-03", codigos(self.preparar(tecnica={"ancho": 1280, "alto": 720})))

    def test_revision_manual_incompleta(self):
        self.assertIn("ENT-04", codigos(self.preparar(revision_manual={"REV-01": "ok"})))


class Revision(unittest.TestCase):
    """revisar.py sobre un vídeo sintético con un salto de luz deliberado."""

    COLORES = ["0xC08040", "0xC48848", "0x4070C0", "0x80C060"]

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.video = cls.tmp / "prueba.mp4"
        cmd = ["ffmpeg", "-v", "error", "-y"]
        for c in cls.COLORES:
            cmd += ["-f", "lavfi", "-i", f"color=c={c}:s=320x180:r=24:d=1"]
        cmd += ["-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=4",
                "-filter_complex", "[0][1][2][3]concat=n=4:v=1:a=0[v];[4]volume=-12dB[a]",
                "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(cls.video)]
        subprocess.run(cmd, check=True)

    def expediente(self, duraciones):
        t, planos = 0.0, []
        for i, dur in enumerate(duraciones):
            planos.append({"id": f"P{i + 1}", "escena": "E1" if i < 3 else "E2", "inicio": t, "duracion": dur,
                           "sujetos": {}})
            t += dur
        d = {"titulo": "prueba", "fps": 24, "duracion_s": t, "resolucion": [320, 180],
             "biblia": {"lugares": {"x": {}}},
             "escenas": [{"id": "E1", "lugar": "x", "momento": "m1"},
                         {"id": "E2", "lugar": "x", "momento": "m2", "transicion": {"tipo": "corte"}}],
             "planos": planos}
        ruta = self.tmp / f"exp_{'_'.join(map(str, duraciones))}.yaml"
        ruta.write_text(yaml.safe_dump(d, allow_unicode=True), encoding="utf-8")
        return ruta

    def test_salto_de_luz_en_escena_continua(self):
        datos = revisar(self.expediente([1, 1, 1, 1]), self.video, self.tmp / "rev1", render_s=3.5)
        marcados = {c["id"] for c in datos["cortes"] if c["marcado"]}
        self.assertEqual(marcados, {"P2>P3"}, json.dumps(datos["cortes"], indent=1, ensure_ascii=False)[:2000])
        t = datos["entrega"]
        self.assertEqual((t["ancho"], t["alto"], t["fps"]), (320, 180, 24.0))
        self.assertAlmostEqual(t["duracion"], 4.0, delta=0.05)
        self.assertIsNotNone(t["lufs"])
        self.assertTrue((self.tmp / "rev1" / "cortes.png").exists())
        self.assertTrue((self.tmp / "rev1" / "revision.json").exists())

    def test_corte_desfasado_respecto_al_expediente(self):
        datos = revisar(self.expediente([1, 1.5, 0.5, 1]), self.video, self.tmp / "rev2")
        c = next(c for c in datos["cortes"] if c["id"] == "P2>P3")
        self.assertTrue(c["marcado"])
        self.assertTrue(any("no destaca" in m for m in c["motivos"]))


if __name__ == "__main__":
    unittest.main()

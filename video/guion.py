"""Guion condensado de «El espejo cubierto» para un video de 60 s.

Cada escena define su decorado (`set`), el tiempo de acción antes del primer
diálogo (`pre`), el tiempo tras el último (`post`) y sus líneas:
(personaje, texto, pausa extra antes de la línea).
Las duraciones reales de cada línea salen del audio generado por tts.py.
"""

TITLE = "El espejo cubierto"
TOTAL = 60.0          # segundos
TITLE_DUR = 3.0       # cartela inicial
MIN_END = 2.2         # cartela «FIN» mínima
GAP = 0.22            # pausa por defecto entre líneas

SCENES = [
    {
        "id": 1, "name": "La moneda", "set": "coins", "pre": 2.0, "post": 0.5,
        "lines": [
            ("A", "Maestro, todavía hay personas buenas en el mundo.", 0),
            ("J", "¿Habéis visto? Soy el único que se ha detenido.", 0.9),
            ("M", "¿Habría hecho lo mismo si nadie lo hubiera visto?", 0.2),
        ],
    },
    {
        "id": 2, "name": "El hombre invisible", "set": "beggar", "pre": 1.2, "post": 0.5,
        "lines": [
            ("A", "¿Por qué nadie lo ayuda?", 0),
            ("M", "¿Y tú? ¿Cuánto tiempo llevas observándolos?", 0),
            ("A", "Yo… estaba esperando que alguien hiciera algo.", 0.2),
            ("M", "¿Y él ha recibido ayuda de tu deseo?", 0),
        ],
    },
    {
        "id": 3, "name": "La pregunta", "set": "fountain", "pre": 1.2, "post": 0.8,
        "lines": [
            ("A", "Ya está. Al menos yo hice algo.", 0),
            ("M", "¿Te molestaría que nadie supiera que lo ayudaste?", 0.2),
        ],
    },
    {
        "id": 4, "name": "El espejo", "set": "mirror", "pre": 1.4, "post": 0.8,
        "lines": [
            ("M", "Mírate bien. ¿Qué ves?", 0),
            ("A", "A alguien bueno.", 0.1),
            ("M", "¿Por qué necesitas que esa sea la respuesta?", 0.2),
        ],
    },
    {
        "id": 5, "name": "La vergüenza", "set": "sit", "pre": 1.0, "post": 1.3,
        "lines": [
            ("A", "Ayer, una parte de mí quería que tú me vieras.", 0),
            ("M", "No preguntes si eres bueno. Pregunta qué necesita él de ti.", 0.2),
        ],
    },
    {
        "id": 6, "name": "Lo que queda", "set": "dusk", "pre": 0.5, "post": 2.8,
        "lines": [
            ("M", "Quien sufre no necesita que nuestras intenciones sean puras.", 0),
            ("M", "El peligro está en necesitar creer que somos buenos.", 0.3),
        ],
    },
]

SPEAKERS = {
    # voz Piper, id de hablante, factor de tono, velocidad
    "M": {"name": "Maestro", "voice": "es_ES-davefx-medium", "sid": 0, "pitch": 0.90, "speed": 0.90},
    "A": {"name": "Alumno", "voice": "es_ES-sharvard-medium", "sid": 0, "pitch": 1.04, "speed": 0.97},
    "J": {"name": "Joven", "voice": "es_ES-sharvard-medium", "sid": 0, "pitch": 1.16, "speed": 1.05},
}


def build_timeline(durations):
    """durations[(scene_id, idx)] -> segundos. Devuelve escenas con tiempos absolutos."""
    t = TITLE_DUR
    out = []
    for sc in SCENES:
        start = t
        cur = t + sc["pre"]
        lines = []
        for i, (spk, text, wait) in enumerate(sc["lines"]):
            if i:
                cur += GAP + wait
            d = durations[(sc["id"], i)]
            lines.append({"spk": spk, "text": text, "start": cur, "end": cur + d, "idx": i})
            cur += d
        end = cur + sc["post"]
        out.append({**sc, "start": start, "end": end, "lines": lines})
        t = end
    if TOTAL - t < MIN_END:
        raise SystemExit(f"El guion dura {t:.2f}s; no cabe en {TOTAL}s con la cartela final.")
    return out, t

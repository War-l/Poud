"""Guion condensado de «El hombre que quería ser justo».

Cada escena: decorado (`set`), segundos de acción antes del primer diálogo
(`pre`) y después del último (`post`), y sus líneas:
(personaje, texto, pausa extra antes de la línea).
La duración de cada línea la fija el audio sintetizado (tts.py).
"""

TITLE = "El hombre que quería ser justo"
TITLE_DUR = 6.0
END_DUR = 6.0
GAP = 0.35

SCENES = [
    {"id": 1, "name": "El árbol", "set": "garden_morning", "pre": 3.6, "post": 2.6, "lines": [
        ("AN", "Ahora sí crecerá como debe.", 0),
        ("JA", "Tal vez. Pero también le he quitado las ramas que le permitían encontrar la luz.", 0.4),
    ]},
    {"id": 2, "name": "El juicio", "set": "court", "pre": 2.4, "post": 2.4, "lines": [
        ("AN", "La ley debe ser igual para todos.", 0),
        ("TO", "¿Y si obedecer la ley significa dejar morir a alguien?", 0.3),
        ("AN", "Las circunstancias importan. Pero no borran lo que has hecho.", 0.5),
    ]},
    {"id": 3, "name": "La hija", "set": "home_evening", "pre": 1.8, "post": 2.6, "lines": [
        ("EL", "Padre, ¿y si yo necesitara un medicamento que no puedes pagar?", 0),
        ("AN", "No permitiría que te pasara nada.", 0),
        ("EL", "¿Y si otro tuviera que robarlo para salvar a su madre?", 0.9),
        ("AN", "No es lo mismo.", 0),
        ("EL", "¿Por qué?", 0.2),
    ]},
    {"id": 4, "name": "El expediente", "set": "office_day", "pre": 2.6, "post": 1.8, "lines": [
        ("AN", "¿Por qué no volviste a pedir ayuda?", 0),
        ("TO", "Volví dos veces. Me dijeron que regresara con los documentos.", 0.2),
        ("TO", "Preferí enfrentarme a un juez antes que volver a casa con las manos vacías.", 0.5),
    ]},
    {"id": 5, "name": "El maestro", "set": "library", "pre": 1.8, "post": 2.2, "lines": [
        ("AN", "Si justifico el robo, ¿cómo podré exigir que los demás respeten la ley?", 0),
        ("SA", "¿Crees que ser justo es tratar todos los casos de la misma manera?", 0.3),
        ("SA", "¿Defiendes la justicia, o la seguridad de saber que siempre has actuado correctamente?", 0.9),
    ]},
    {"id": 6, "name": "La decisión", "set": "office_night", "pre": 2.4, "post": 2.4, "lines": [
        ("EL", "¿Qué vas a hacer?", 0),
        ("AN", "No existe una decisión sin consecuencias.", 0.3),
        ("EL", "¿Y si te equivocas?", 0.3),
        ("AN", "Tendré que responder por ello.", 0.4),
    ]},
    {"id": 7, "name": "El recuerdo", "set": "memory", "pre": 1.4, "post": 2.6, "lines": [
        ("EL", "Padre, cuando era niña, rompí la ventana de un vecino.", 0),
        ("EL", "Conocías las circunstancias. Y me diste la oportunidad de aprender.", 1.2),
    ]},
    {"id": 8, "name": "La reputación", "set": "steps", "pre": 1.8, "post": 2.8, "lines": [
        ("CI", "Si cambia su criterio ahora, ¿cómo podremos confiar en usted?", 0),
        ("AN", "Si mantengo un criterio injusto solo para parecer coherente, ¿qué confianza merezco?", 0.3),
        ("AN", "Comprender no significa justificarlo todo.", 0.5),
    ]},
    {"id": 9, "name": "La rama", "set": "garden_evening", "pre": 2.4, "post": 3.2, "lines": [
        ("AN", "Reconocer el daño no significa repararlo.", 0),
        ("JA", "No. Pero es difícil reparar aquello que uno se niega a reconocer.", 0.4),
    ]},
    {"id": 10, "name": "Lo que queda", "set": "plaza", "pre": 1.8, "post": 4.6, "lines": [
        ("SA", "¿Y qué harás la próxima vez?", 0),
        ("AN", "Volver a examinarme. Sin suponer que ya soy un hombre justo.", 0.3),
        ("AN", "Empecemos por el principio. ¿Qué ha ocurrido?", 3.6),
    ]},
]

SPEAKERS = {
    # voz Piper, hablante, tono, velocidad, (graves, brillo) de ecualización
    "AN": {"name": "Andrés", "voice": "es_ES-davefx-medium", "sid": 0, "pitch": 0.96, "speed": 0.90},
    "SA": {"name": "Samuel", "voice": "es_ES-davefx-medium", "sid": 0, "pitch": 0.84, "speed": 0.80},
    "EL": {"name": "Elena", "voice": "es_ES-sharvard-medium", "sid": 1, "pitch": 1.00, "speed": 0.93},
    "TO": {"name": "Tomás", "voice": "es_ES-sharvard-medium", "sid": 0, "pitch": 1.07, "speed": 0.95},
    "JA": {"name": "Jardinero", "voice": "es_ES-carlfm-x_low", "sid": 0, "pitch": 0.94, "speed": 0.86},
    "CI": {"name": "Ciudadano", "voice": "es_ES-sharvard-medium", "sid": 0, "pitch": 0.90, "speed": 1.04},
}


def build_timeline(durations):
    """durations[(scene_id, idx)] -> s. Devuelve (escenas con tiempos absolutos, duración total)."""
    t = TITLE_DUR
    out = []
    for sc in SCENES:
        start, cur, lines = t, t + sc["pre"], []
        for i, (spk, text, wait) in enumerate(sc["lines"]):
            if i:
                cur += GAP + wait
            d = durations[(sc["id"], i)]
            lines.append({"spk": spk, "text": text, "start": cur, "end": cur + d, "idx": i})
            cur += d
        end = cur + sc["post"]
        out.append({**sc, "start": start, "end": end, "lines": lines})
        t = end
    return out, t + END_DUR

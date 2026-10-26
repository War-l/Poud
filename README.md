# Poud: vídeos programáticos

Todo vídeo de este repositorio sigue el **método de producción** de [`metodo/`](metodo/README.md).
Es obligatorio y se verifica de forma automática. Las instrucciones para trabajar aquí están en
[`CLAUDE.md`](CLAUDE.md).

| Carpeta | Contenido |
|---|---|
| [`metodo/`](metodo/README.md) | Método de producción: proceso, verificador, revisión del vídeo, ejemplos y pruebas |
| [`estilo/`](estilo/README.md) | Estudio de estilo en tiempo real (32 s a 1080p renderizados en 31,7 s) |
| [`justo/`](justo/README.md) | Primer intento de «El hombre que quería ser justo» (motor lento; no cumple el tiempo real) |
| `video/` | «El espejo cubierto», vídeo de 60 s (documentado abajo) |

---

## El espejo cubierto — video programático de 60 s

`el_espejo_cubierto.mp4` (1920×1080, 30 fps, 60 s, con voz, música y efectos) está
generado al 100 % por código, a partir del guion «El espejo cubierto».

### Cómo se construye

| Paso | Archivo | Qué hace |
|---|---|---|
| Guion | `video/guion.py` | Versión condensada del guion (6 escenas, 16 líneas) y cálculo de la línea de tiempo para que dure exactamente 60 s. |
| Voces | `video/tts.py` | Sintetiza cada línea con [Piper](https://github.com/rhasspy/piper): Maestro = `es_ES-davefx`, Alumno y Joven = `es_ES-sharvard` con distinto tono. |
| Imagen | `video/draw.py`, `video/scenes.py`, `video/render.py` | Dibujo vectorial con Cairo: personajes articulados (caminar, agacharse, sentarse, gestos), decorados (plaza, esquina, fuente, taller con espejo, anochecer), cámara, subtítulos y cartelas. La boca de cada personaje se mueve con la envolvente real de su audio. |
| Sonido | `video/audio.py` | Música sintetizada (pad en La menor + caja de música), ambientes (murmullo, fuente, grillos), efectos (monedas que tintinean en cada bote, tela, tropiezo) y atenuación de la música bajo los diálogos. |

### Reconstruir

Requiere `ffmpeg` y Python 3.10+.

```bash
pip install -r video/requirements.txt
./video/build.sh            # genera ./el_espejo_cubierto.mp4
```

`build.sh` descarga las voces (~140 MB, desde las releases de sherpa-onnx en GitHub),
genera los diálogos, renderiza los 1800 fotogramas (~1 min con 4 núcleos), mezcla el
audio y une todo con ffmpeg.

Para revisar fotogramas sueltos sin renderizar todo:

```bash
cd video && python3 render.py --stills 5 20 35   # PNGs en video/build/stills/
```

### Adaptación del guion

En 60 s no cabe el guion completo, así que cada escena conserva su momento clave:

1. **La moneda** — las monedas caen, el joven devuelve una y presume ante sus amigos. «¿Habría hecho lo mismo si nadie lo hubiera visto?»
2. **El hombre invisible** — la gente pasa junto al anciano. «¿Y él ha recibido ayuda de tu deseo?»
3. **La pregunta** — junto a la fuente. «¿Te molestaría que nadie supiera que lo ayudaste?»; el alumno abre la boca y no responde.
4. **El espejo** — el maestro retira la tela; el alumno se mira y baja la vista.
5. **La vergüenza** — al día siguiente, sin nadie mirando. El alumno ayuda al anciano con el abrigo sin mirar al maestro.
6. **Lo que queda** — al anochecer alguien tropieza; el alumno corre a ayudar y el maestro sigue caminando. Ninguno mira atrás.

# El hombre que quería ser justo

Cortometraje de 2 min 43 s (2560×1440, 24 fps, formato panorámico 2,39:1) generado íntegramente por
código: imagen, iluminación, voces, música y efectos de sonido.

## Cómo está hecho

### Imagen: ilustración por capas + composición tipo VFX en GPU

- **Decorados 2.5D con trazado de rayos.** Cada decorado se compone de planos pintados con Cairo en
  unidades reales (metros). Son las paredes, los suelos, los techos y los recortes de árboles,
  muebles y fachadas. Un shader GLSL lanza un rayo por píxel contra cada plano. Así la
  perspectiva, el paralaje y el filtrado anisótropo de suelos y paredes son geométricamente
  correctos (`engine/shaders.py`, `FS_PLANE`).
- **Luz que se suma, en espacio lineal HDR.** La radiancia se calcula como albedo/π × la suma de
  las irradiancias:
  - el cielo, como hemisferio de luz;
  - la radiosidad del suelo;
  - el sol;
  - las luces puntuales, con caída de 1/r².

  Nunca se pinta la luz encima de la imagen.
- **Colores calculados con física.**
  - Las lámparas, el fuego y el pasillo usan color de cuerpo negro: ley de Planck integrada con
    las curvas CIE 1931 y pasada a sRGB lineal (`engine/physics.py`).
  - El cielo, el color del sol y la luz ambiente salen de un modelo de dispersión atmosférica
    Rayleigh + Mie (Nishita). Por eso el sol bajo se vuelve rojizo y el crepúsculo es azul.
- **Perspectiva atmosférica.** La extinción depende de la longitud de onda y se suma la luz
  dispersada hacia el ojo, con fase Henyey-Greenstein alrededor del sol.
- **Sol a través de ventanas.** Cada punto del suelo, de las paredes o de los personajes se
  proyecta hacia el sol hasta el muro de las ventanas. Así se obtienen las manchas de luz, la
  sombra de los parteluces y de las persianas, y una penumbra que crece con la distancia.
- **Luz volumétrica.** Un ray-marching integra los haces de sol dentro de las salas, y la integral
  analítica de 1/r² da el halo de las lámparas. Todo se calcula en rodajas de profundidad, para
  que los objetos ocluyan lo que queda detrás.
- **Profundidad de campo de lente delgada.** El círculo de confusión se calcula con la focal en mm,
  el diafragma f/N y la distancia de foco reales, en formato completo. Los planos muy desenfocados
  se calculan a media resolución.
- **Desenfoque de movimiento.** Usa un obturador de 180°:
  - para la cámara, mediante el vector de desplazamiento en pantalla de cada plano;
  - para brazos y piernas, promediando subfotogramas;
  - para la lluvia, con trazos de longitud igual a la velocidad × el tiempo de exposición.
- **Millones de partículas.** Polvo en suspensión y polen (hasta 2 millones por plano):
  - el polvo solo es visible dentro de los haces de sol;
  - el polen brilla a contraluz por la dispersión Mie;
  - las partículas desenfocadas forman discos de bokeh que conservan la energía.

  También hay chispas de chimenea, vapor, lluvia y cristales que estallan.
- **Volumen en los recortes.** Las normales se infieren desde la silueta (normales infladas). Con
  ellas, personajes y follaje reciben luz de contorno, oscurecimiento y retroiluminación
  translúcida según la dirección real de la luz.
- **Postproducción de cine.**
  - Rayos crepusculares en espacio de pantalla.
  - Bloom con cadena de mipmaps (Jimenez 2014).
  - Viñeteado natural cos⁴.
  - Aberración cromática.
  - Tonemapping ACES.
  - Gradación de color.
  - Grano dependiente de la luminancia.
  - Tramado.
- **Movimiento con inercia.** Las cámaras y los gestos usan la respuesta analítica de un oscilador
  amortiguado: arranques y frenadas suaves, con un ligero rebote. Se puede evaluar en cualquier
  instante, por eso sirve para el submuestreo del obturador. También hay:
  - cámara en mano con ruido fractal;
  - parpadeo y respiración;
  - pelo y ropa con retardo;
  - boca sincronizada con la envolvente real de cada voz.

La «GPU» es Mesa llvmpipe: OpenGL 4.5 emulado en la CPU, porque este entorno no tiene tarjeta
gráfica. El mismo código funciona sin cambios en una GPU real, varios órdenes de magnitud más
rápido.

### Sonido

- **Voces:** Piper (TTS neuronal local) con voces de España, con tono y tempo distintos para cada
  personaje (`tts.py`).
- **Acústica de cada sala:** convolución con respuestas de impulso sintéticas (tribunal de
  ~1,7 s de RT60, despacho seco, plaza abierta). El diálogo se panea según la posición del
  personaje en el plano.
- **Música original sintetizada:**
  - piano con inharmonicidad de cuerda rígida;
  - cuerdas en ensemble y campanas;
  - progresión por escena, de re menor a re mayor.
- **Ambientes y efectos:**
  - ambientes: pájaros, grillos, lluvia, fuego, fuente, multitud;
  - efectos: tijeras de podar, cristal que se rompe, papeles;
  - pasos detectados automáticamente a partir de la fase de marcha de cada personaje, con
    sonido según el suelo.

## Estructura

| Archivo | Contenido |
|---|---|
| `guion.py` | Guion condensado (10 escenas, 30 líneas) y línea de tiempo |
| `tts.py` | Síntesis de voz |
| `engine/` | Motor: shaders, render OpenGL, física, personajes, director de cámara |
| `sets/` | Decorados: jardín, tribunal, casa, despacho, biblioteca, plazas |
| `film.py` | Coreografía: planos, actores, objetos y tiempos de cada escena |
| `render.py` | Render de fotogramas, títulos, subtítulos y bandas panorámicas |
| `audio.py` | Banda sonora completa |
| `build_all.sh` | Proceso completo y reanudable |

## Reconstruir

Requiere `ffmpeg`, Python 3.10+, Mesa con EGL (llvmpipe o una GPU) y estos paquetes:

```bash
pip install moderngl glcontext pycairo numpy scipy soundfile piper-tts pillow
./fetch_voices.sh          # voces Piper (desde las releases de sherpa-onnx en GitHub)
python3 tts.py             # diálogos
./build_all.sh             # imagen (~2,5 h en 4 núcleos de CPU) + sonido -> ../el_hombre_que_queria_ser_justo.mp4
```

Para una prueba rápida: `RES=1280x720 ./build_all.sh`, o fotogramas sueltos con
`python3 render.py --res 1280x720 --stills 25 74 130`.

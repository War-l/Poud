# Estudio de estilo — render en tiempo real

`estilo.py` genera un vídeo de 32 s a 1920×1080 y 24 fps, con formato panorámico 2,39:1 y
sonido. Hace todo el trabajo (pintado, fotogramas, codificación, sonido y mezcla) en **menos
tiempo del que dura el vídeo**, en 4 núcleos de CPU y sin tarjeta gráfica: medido con `time`,
tarda unos 31 s para 32 s de vídeo (0,96–0,99×).

```bash
pip install moderngl glcontext pycairo numpy scipy soundfile pillow
time python3 estilo.py                 # -> estilo.mp4
python3 estilo.py --stills 3 12 24     # fotogramas sueltos en PNG
```

## Estilo

Es un contraluz de atardecer con siluetas por capas: un hombre junto a un árbol joven atado a su
tutor, en lo alto de una colina. Detrás, cordilleras que se funden en la bruma y nubes iluminadas
desde abajo. La belleza viene de la luz, el color y la profundidad.

- **Cielo físico:** un pase de GPU calcula una vez la dispersión Rayleigh + Mie (modelo de
  Nishita). De ahí salen el color del sol, el del horizonte y el del cenit.
- **Perspectiva atmosférica real:** cada cordillera se apaga según su distancia (3–45 km) y se
  suma la luz del aire del horizonte. La bruma se acumula en los valles.
- **Nubes:** el sol está por debajo de su base, así que la luz se integra desde abajo con la ley
  de Beer. El borde plateado surge de la dispersión hacia delante (fase Henyey-Greenstein). La
  cara en sombra combina luz roja dispersada y cielo azul, lo que da el tono malva.
- **Luz de contorno:** las siluetas se iluminan según la dirección real del sol, con más
  intensidad cerca de él.
- **Cámara:**
  - objetivo de 50 mm f/2.8 con profundidad de campo de lente delgada;
  - cambio de foco de la hierba al hombre;
  - paralaje real, con desplazamiento lateral que descubre el sol tras la copa.
- **Movimiento:**
  - viento con ráfagas que viajan por el mundo (la hierba y el árbol se doblan con ellas);
  - hojas, vilanos con bokeh y una bandada de pájaros.
- **Lente y película:**
  - rayos crepusculares y halo;
  - fantasmas de lente;
  - viñeteado;
  - gradación ACES mediante LUT 3D;
  - grano con tamaño real.
- **Sonido:** el viento sigue la misma función de ráfagas que mueve la hierba. Encima suenan
  piano y cuerdas, de re menor a re mayor.

## Por qué es rápido

1. **Pintado inicial en paralelo:** todo lo caro (nubes, cordilleras, siluetas, luz de contorno,
   desenfoques) se pinta una vez al inicio, en 4 procesos, en unos 2 s.
2. **Fondo precompuesto:** el cielo, el sol y las montañas están en el infinito, sin paralaje,
   así que se precomponen en un solo fondo.
3. **Un único shader por fotograma:** compone de delante hacia atrás con salida temprana.
   - El viento se calcula por columna (1920 valores en la CPU), no por píxel.
   - La hierba y la colina solo se evalúan bajo su silueta.
   - Las capas se guardan en 8 bits con codificación HDR (raíz cuadrada + escala), que se leen
     el doble de rápido que las de coma flotante.
4. **Efectos a baja resolución:** los rayos y el halo se calculan a 1/8 de resolución. La
   gradación completa cabe en una LUT 3D.
5. **Conversión en GPU:** pasa a YUV 4:2:0 BT.709 en la propia GPU. x264 corre en paralelo en el
   preset `ultrafast` con un hilo, y el sonido se sintetiza en otro proceso.

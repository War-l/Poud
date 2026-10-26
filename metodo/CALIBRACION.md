# Calibración de `revisar.py`

Un instrumento de medida se calibra antes de confiar en él («pesas justas»). Esta es la
calibración de los testigos automáticos de continuidad con imágenes reales.

## Muestra

- **Vídeo:** `justo/build/vista_previa_132s_1080p.mp4`, la vista previa de 132 s de «El hombre
  que quería ser justo» (1920×1080, 2,39:1 con bandas).
- **Cortes:** 35. De ellos, 27 son entre planos de una misma escena y 8 son cambios de escena con
  fundido a negro, que no se evalúan.
- **Planos:** sus tiempos se extrajeron de `justo/film.py`, la definición de los planos de cada
  escena.
- **Juicio visual** (segundo testigo): cada corte se juzgó mirando la hoja de cortes y se
  clasificó en una de cuatro clases:
  - *coherente*: misma luz;
  - *incoherente*: salto de luz que un espectador nota;
  - *dudoso*: contraplano con un fondo de distinta exposición, aceptable pero notable;
  - *corte invisible*.

## Lo que la calibración corrigió

1. **Convención de fotogramas.** 12 cortes aparecían «desfasados». Un segundo testigo
   independiente, el detector de escenas de ffmpeg, mostró que todos ocurrían exactamente un
   fotograma después de lo previsto.
   - Causa: el motor cambia de plano en el primer fotograma con t ≥ inicio, y la herramienta
     redondeaba al más cercano.
   - Corrección: `Expediente.fotograma_de` usa la misma convención que el motor.
   - Tras el cambio, los 26 cortes visibles coinciden con su fotograma.
2. **Bandas negras.** En formato 2,39:1 el 10 % más oscuro de cada fotograma eran las bandas, así
   que la medida de las sombras siempre daba 0. Ahora se recortan antes de medir
   (`sin_bandas`).
3. **Umbral de color.**
   - El color de las luces llega a ΔC 31 en cortes coherentes, cuando el sol, el cielo o una
     barba blanca entran en cuadro. En los incoherentes midió entre 10 y 15.
   - No distingue unos de otros, así que con umbral 8 producía falsas alarmas.
   - Ahora solo marca errores groseros de balance de blancos (ΔC > 40, por encima de todo lo
     observado en cortes coherentes).
4. **Umbral de exposición.** Se mantiene en |ΔL| > 40:
   - los 2 cortes incoherentes midieron 43 y 45;
   - los coherentes, como máximo 23;
   - los dudosos, entre 25 y 38.

## Resultado con los umbrales finales

| Juicio visual | Cortes | Marcados |
|---|---|---|
| Incoherente | 2 | 2 |
| Coherente | 18 | 0 |
| Dudoso | 6 | 0 (quedan para la revisión manual de la hoja) |
| Corte invisible | 1 | 1 (el plano previsto no se ve: decisión del autor) |

## Limitaciones

- La muestra es pequeña: 27 cortes de una sola película y un solo estilo.
- Las medidas son estadísticas de todo el encuadre: no separan la luz del contenido.
- Por eso el veredicto final de cada corte es siempre humano y se anota en
  `entrega.veredictos` (regla de los dos testigos).
- Hay que volver a calibrar cuando cambie el estilo de forma importante y añadir aquí la nueva
  muestra.

## Datos

ΔC: diferencia de crominancia CIELAB. ΔL: diferencia de luminosidad mediana.

| Corte | t (s) | ΔC luces | ΔC sombras | ΔL | Juicio visual | Marcado | Nota |
|---|---|---|---|---|---|---|---|
| P1>P2 | 9.25 | 15.83 | 1.25 | -2.1 | coherente | no | plano general con cielo y casa |
| P2>P3 | 11.79 | 5.39 | 3.98 | 2.88 | coherente | no |  |
| P3>P4 | 16.96 | 13.69 | 6.26 | -1.03 | coherente | no |  |
| P5>P6 | 23.67 | 12.58 | 11.95 | 1.27 | coherente | no |  |
| P6>P7 | 27.67 | 9.92 | 9.31 | -43.45 | incoherente | sí | contraplano del tribunal mucho más oscuro y rojizo |
| P7>P8 | 31.92 | 14.64 | 0.01 | 45.2 | incoherente | sí | vuelta al plano claro del tribunal |
| P9>P10 | 37.17 | 12.84 | 0.04 | -35.74 | dudoso | no | fondo oscuro tras Elena frente a pared iluminada tras Andrés |
| P10>P11 | 39.62 | 7.39 | 0.1 | 37.95 | dudoso | no |  |
| P11>P12 | 41.88 | 7.26 | 0.01 | -38.35 | dudoso | no |  |
| P12>P13 | 45.96 | 5.0 | 0.04 | 25.07 | dudoso | no |  |
| P13>P14 | 47.42 | 4.5 | 19.03 | -25.96 | dudoso | no |  |
| P14>P15 | 48.38 | 3.35 | 0.0 | 31.64 | dudoso | no |  |
| P16>P17 | 53.12 | 2.9 | 5.66 | -1.21 | coherente | no |  |
| P17>P18 | 55.08 | 1.19 | 0.0 | -4.84 | coherente | no |  |
| P18>P19 | 64.54 | 1.62 | 0.0 | -14.74 | coherente | no |  |
| P20>P21 | 68.46 | 11.78 | 0.0 | -23.11 | coherente | no |  |
| P21>P22 | 72.12 | 9.75 | 16.18 | 14.6 | coherente | no | barba blanca en cuadro |
| P22>P23 | 82.04 | 9.4 | 0.78 | -12.19 | coherente | no |  |
| P24>P25 | 87.67 | 13.57 | 0.0 | 5.78 | coherente | no |  |
| P25>P26 | 90.67 | 17.59 | 0.0 | -0.5 | coherente | no |  |
| P26>P27 | 92.58 | 17.7 | 0.0 | 1.01 | coherente | no |  |
| P28>P29 | 106.38 | 0.26 | 0.0 | 0.35 | corte invisible | sí | el corte cae dentro del destello blanco del recuerdo: no se ve |
| P30>P31 | 111.21 | 0.08 | 2.33 | 1.08 | coherente | no |  |
| P31>P32 | 115.29 | 0.13 | 2.08 | -1.54 | coherente | no |  |
| P32>P33 | 123.29 | 0.2 | 0.0 | 1.43 | coherente | no |  |
| P34>P35 | 128.08 | 30.87 | 2.02 | -17.81 | coherente | no | plano general con el sol en cuadro |
| P35>P36 | 131.04 | 0.9 | 3.48 | -0.66 | coherente | no |  |

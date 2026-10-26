# Instrucciones del proyecto (obligatorias)

Este repositorio produce vídeos programáticos. **Todo vídeo sigue el método de
[`metodo/README.md`](metodo/README.md), sin excepciones.** El usuario lo pidió así: «quiero que así
se siga en todos los vídeos, sé riguroso».

El método integra los métodos del usuario, que se conservan íntegros en
[`metodo/fuentes/metodos_originales.md`](metodo/fuentes/metodos_originales.md). Cada pilar está
asignado a un paso y a una comprobación en [`metodo/TRAZABILIDAD.md`](metodo/TRAZABILIDAD.md).

## Orden de trabajo para cada vídeo

1. Crear `<carpeta>/expediente.yaml` desde [`metodo/plantilla.yaml`](metodo/plantilla.yaml) **antes
   de escribir código de producción**. Si el usuario entrega un guion, guardarlo íntegro junto al
   expediente.
2. Completar las fases 0 a 5: recepción, enfoque, enseñanza, imaginar y crear, narrativa visual y
   biblia de continuidad.
3. **Puerta A**: `python3 -m metodo.verificar <expediente> --fase plan` con 0 errores.
4. **Prototipo**:
   - fotogramas clave de cada plano con el motor real y a resolución final;
   - un plano completo en movimiento, con ms/fotograma medido;
   - `python3 -m metodo.revisar` sobre ese material.

   Enviarlo al usuario y **esperar su aprobación** antes de la producción completa, salvo que haya
   pedido el vídeo terminado sin revisión intermedia (en ese caso, citar sus palabras en el
   expediente).
5. **Producción**: el código lee tiempos, planos y estados del expediente
   (`metodo.expediente.cargar`). No se copian datos a mano.
6. **Revisión**:
   - ejecutar `python3 -m metodo.revisar <expediente> <video> --render-s <segundos medidos>`;
   - dar un veredicto con dos testigos a cada corte marcado;
   - completar la lista REV-01 a REV-09;
   - registrar cada ajuste con problema, causa, cambio y verificación.
7. **Puerta C**: `python3 -m metodo.verificar <expediente> --fase final` con 0 errores.
8. Entregar con un informe que empiece por el resultado, solo con datos medidos, e incluya las
   preguntas de comprobación para probar el vídeo con espectadores.

Si el usuario solo pide un tema o un enfoque, se aplica la fase 1 y se verifica con
`--fase enfoque`.

## Restricciones permanentes

- **Tiempo de render ≤ duración del vídeo; nunca más de 1,1×.** Se mide de principio a fin con
  `time`: precómputo, fotogramas, codificación, audio y mezcla. Si el coste estimado no cabe, se
  simplifica el diseño antes de producir.
- **Belleza al servicio del mensaje.** Cada efecto declara qué aporta; lo que no aporta se elimina.
  La referencia técnica de tiempo real es [`estilo/estilo.py`](estilo/estilo.py): 32 s a 1080p en
  31,7 s.
  - El motor de `justo/` va más de 50 veces más lento que el tiempo real (más de 2 h para 132 s).
  - No se usa para producir sin optimizarlo antes hasta cumplir la regla anterior.
- **Fidelidad al guion del usuario.** No se cambian su mensaje ni sus diálogos. Todo cambio se
  registra en `enfoque.cambios_guion`, se propone y necesita su aprobación.
- **Solo se afirma lo medido o verificado.** Lo no confirmado se marca como tal. El audio no se
  puede escuchar desde aquí: solo se informa de sus mediciones (sonoridad, picos).
- **Lo divino no se representa con una figura**; se alude con símbolos.
- **Comunicación en español.** Primero el resultado; frases simples.

## Mantenimiento del método

- Si el usuario envía nuevos métodos o correcciones:
  - añadirlos a `metodo/fuentes/` sin modificar el texto;
  - actualizar `metodo/README.md` y `metodo/TRAZABILIDAD.md`;
  - si hace falta, añadir reglas al verificador, cada una con su prueba.
- Tras cualquier cambio en `metodo/` deben pasar las pruebas:
  `python3 -m unittest discover -s metodo/pruebas -t .`
- Si cambia el estilo visual de forma importante, volver a calibrar `revisar` y añadir la muestra a
  [`metodo/CALIBRACION.md`](metodo/CALIBRACION.md).

# Método de producción de vídeos

**Este método es obligatorio para todos los vídeos de este proyecto.** El usuario lo pidió así:
«quiero que así se siga en todos los vídeos, sé riguroso».

- Une en un solo proceso los métodos del usuario (texto íntegro en
  [`fuentes/metodos_originales.md`](fuentes/metodos_originales.md)).
- Cada pilar de esas fuentes tiene un paso y una comprobación asignados en
  [`TRAZABILIDAD.md`](TRAZABILIDAD.md).
- Ningún pilar queda sin aplicar.

## Idea rectora

Un vídeo de este proyecto no se juzga por lo bonita que sea cada imagen, sino por si **enseña**:

- el espectador comprende la idea central;
- la ve demostrada con acciones;
- puede aplicarla.

La belleza, la técnica y los efectos están al servicio de eso y nunca lo sustituyen.

> Contar es transmitir; enseñar es facilitar el aprendizaje. Un vídeo puede comunicar muy bien y,
> aun así, enseñar mal.

## Piezas del sistema

| Pieza | Qué es |
|---|---|
| `expediente.yaml` (uno por vídeo) | El plano completo de la obra: enfoque, enseñanza, ideas, biblia visual, escenas, planos, prototipo, ajustes y entrega. Es la **fuente única de verdad**: el código de producción lee de aquí los tiempos, los planos y los estados. |
| [`plantilla.yaml`](plantilla.yaml) | Expediente vacío con cada campo explicado. |
| `python3 -m metodo.verificar EXPEDIENTE --fase F` | Comprueba de forma automática las reglas del método (enfoque, enseñanza, creación, narrativa, continuidad, coste, entrega). Si hay errores, la fase no se puede dar por cerrada. |
| `python3 -m metodo.revisar EXPEDIENTE VIDEO` | Observa y compara el vídeo renderizado. Genera la hoja de cortes, la hoja por personaje y la hoja de planos. Mide la continuidad de la luz en cada corte y la técnica de la entrega (resolución, fps, duración, sonoridad, picos). |
| [`ejemplos/`](ejemplos/) | Pruebas del método con los dos ejemplos de la conversación del usuario: «La decisión» y el enfoque sobre la envidia. |
| `pruebas/` | Pruebas automáticas que demuestran que cada regla detecta el error que debe detectar. |
| [`CALIBRACION.md`](CALIBRACION.md) | Calibración de los testigos automáticos de `revisar` con 27 cortes reales. |

## El proceso

| Fase | Pregunta que responde | Entregable (sección del expediente) |
|---|---|---|
| 0. Recepción e inspección | ¿Qué se pide y con qué contamos? | `recepcion` |
| 1. Enfoque | ¿Qué decir exactamente y es verdad? | `enfoque` |
| 2. Enseñanza | ¿Qué debe aprender el espectador y cómo se comprueba? | `ensenanza` |
| 3. Imaginar y crear | ¿Cómo representarlo y cuánto cuesta? | `creacion` |
| 4. Narrativa visual | ¿Qué ve y oye el espectador en cada plano? | `escenas`, `planos` |
| 5. Continuidad | ¿Qué debe mantenerse y qué puede cambiar? | `biblia` |
| **Puerta A** | `verificar --fase plan` sin errores | — |
| 6. Prototipo | ¿Funciona antes de invertir en producirlo? | `prototipo` |
| **Puerta B** | Prototipo aprobado por el usuario | — |
| 7. Producción | Código que lee el expediente; render en tiempo real | código + vídeo |
| 8. Observar, comparar, probar y ajustar | ¿El vídeo cumple el plan? | `ajustes`, `entrega.veredictos`, `entrega.revision_manual` |
| **Puerta C** | `verificar --fase final` sin errores | — |
| 9. Entrega y evaluación | ¿Qué se entrega y cómo se comprueba el aprendizaje? | `entrega` + informe |

Si el usuario solo pide un enfoque o un tema, el proceso se detiene en la fase 1 y se verifica con
`--fase enfoque`.

---

## Fase 0. Recepción e inspección

*Fuentes: planificar (inspección nocturna de Nehemías), observar (limpiar el instrumento).*

1. **Leer el pedido completo dos veces** y anotar su origen:
   - `guion_usuario`: el usuario entrega el guion;
   - `tema`: el usuario da un tema o una idea y hay que descubrir qué decir.
2. **Inspección previa (inventario)**: qué existe ya y se puede reutilizar (motores, estilos
   aprobados, sonidos, voces) y qué hay que construir. Se inspecciona antes de proponer.
3. **Declarar supuestos y sesgos propios** antes de investigar: la viga en el propio ojo.

## Fase 1. Enfoque: qué decir

*Fuentes: observar e investigar, identificar y profundizar, generar y explorar, discernir y
seleccionar, contrastar y validar, y la metodología de enfoques específicos con su fase 5 de
verificación.*

### Si el origen es un tema

El proceso es: **preguntar → delimitar → investigar → jerarquizar → seleccionar → verificar →
aprobar, reformular o descartar**.

1. **Preguntas fundamentales**, las cuatro obligatorias:
   - *origen*: ¿de dónde procede y por qué surge?
   - *significado*: ¿qué significa y con qué fin?
   - *naturaleza*: ¿qué es esencialmente y qué lo distingue?
   - *consecuencia*: ¿qué fruto produce?
2. **Delimitar**: lista explícita de lo que queda **dentro** y lo que queda **fuera**. Se separa la
   paja del grano.
3. **Investigar** con diligencia y desde el principio: fuentes directas, no rumores de segunda mano.
4. **Jerarquizar** los hallazgos: una sola **piedra angular**, luego los principales y luego los
   secundarios.
5. **Generar al menos 3 enfoques** distintos y evaluarlos **con los mismos criterios** (pesas
   justas). Criterios mínimos:
   - fundamento investigable;
   - capacidad explicativa;
   - contraste;
   - potencial visual;
   - enseñanza práctica.
6. **Seleccionar**. Si el elegido no es el de mayor puntuación, se justifica por escrito.
7. **Verificar** (dos o tres testigos):
   - al menos **2 fuentes independientes verificadas**, con su referencia;
   - contraejemplos o excepciones;
   - limitaciones;
   - veredicto: `aprobar`, `reformular` (con la nueva formulación) o `descartar`.

   Un dato que no se pudo confirmar se marca como no confirmado; nunca se presenta como hecho.

### Si el origen es un guion del usuario

1. **Fidelidad al modelo**: el mensaje y los diálogos del usuario no se cambian. No se condensa
   salvo necesidad, y toda condensación o cambio:
   - se registra en `enfoque.cambios_guion`, con su ajuste;
   - se propone al usuario;
   - requiere su aprobación antes de producir.
2. Se guarda el guion íntegro junto al expediente (`enfoque.guion`).
3. Se declara el **tipo de obra**: parábola, documental, explicativo o testimonio.
4. **Afirmaciones verificables**: todo dato, cifra o cita presentada como hecho necesita 2 fuentes
   verificadas. Lo que es ficción u opinión se marca como tal.
5. Al modelar los planos (fase 4) el verificador revisa el guion en busca de incoherencias de
   objetos, presencia, tiempos y luz. Las que encuentre se tratan como ajustes.

## Fase 2. Enseñanza: qué debe aprender el espectador

*Fuentes: método de enseñanza (los 7 pilares), comunicar y educar, corregir y orientar, y la
secuencia captar–contexto–explicar–demostrar–practicar–evaluar–cerrar.*

1. **Público, idioma y nivel**: `leche`, para principios elementales, o `alimento_solido`. Se habla
   «en la lengua del oyente».
2. **Objetivo observable**: «El espectador podrá + verbo observable + contenido».
   - Verbos válidos: distinguir, identificar, explicar, aplicar, decidir, comparar…
   - Prohibidos como verbo principal: entender, comprender, saber, conocer, aprender, apreciar.
     No se pueden comprobar.
3. **Idea central** en una oración de 30 palabras como máximo (la piedra angular), y una **pregunta
   central** que la obra hace al espectador (método de preguntas). El espectador descubre la
   respuesta por sí mismo.
4. **Hilo conductor**: la línea que une el primer plano con el último.
5. **Conceptos con prerrequisitos** (gradualidad, de la leche al alimento sólido): ningún concepto
   aparece antes que aquellos en los que se apoya.
6. **Secuencia didáctica**. Cada función se asigna a planos concretos; si se omite una, se
   justifica en `ensenanza.omisiones`:

   | Función | Para qué sirve |
   |---|---|
   | `captar` | Pregunta, problema o historia en el primer 10 % (máximo 8 s). |
   | `contexto` | Qué sucede y por qué importa. |
   | `explicar` | El concepto con claridad, a la medida del oyente. |
   | `demostrar` | La idea hecha visible con una acción. |
   | `preguntar` | El espectador juzga. |
   | `aplicar` | La idea trasladada a otra situación. |
   | `cerrar` | Resumen o acción propuesta, en el último plano. |
7. **Mostrar, no solo decir**: la idea central se demuestra al menos en un plano con canal
   `visual`, no solo con diálogo o rótulo.
8. **Símbolos y mementos** (las piedras del Jordán, la sombra y la sustancia): cada símbolo tiene
   un significado, se **siembra** en un plano y se **cosecha** en otro posterior. La repetición
   con variación fija la enseñanza.
9. **Corrección paciente**: si la obra muestra un error, muestra también la corrección y su porqué,
   sin violencia.
10. **Coherencia del maestro**: quien enseña en la obra vive lo que enseña. Si no lo hace, la obra
    muestra esa incoherencia como tal.
11. **Comprobación del aprendizaje**:
    - de 2 a 4 preguntas, cada una con su respuesta esperada y los planos que la responden;
    - al menos una se responde con la imagen;
    - se entregan con el vídeo para probarlo con espectadores reales.

## Fase 3. Imaginar y crear: cómo representarlo

*Fuentes: imaginar (5 pilares), crear (6 pilares), generar–elegir–prototipar, mostrar y
representar.*

1. **Generar al menos 3 ideas de representación**: concepto visual, metáfora y estilo. Al menos una
   no debe ser la primera ocurrencia. Se evalúan **con los mismos criterios**:
   - servicio al mensaje;
   - claridad;
   - belleza;
   - viabilidad en tiempo real;
   - continuidad.
2. **Elegir** y justificar. Si existe un estilo aprobado por el usuario, se parte de él.
3. **Plano del estilo**: paleta, luz, materiales y tipografía, definidos antes de producir.
4. **Filtro de vanidad** (la torre de Babel): cada efecto o técnica declara qué aporta al mensaje.
   Lo que no aporta se elimina. Nada se hace «para hacerse un nombre».
5. **Representación veraz**:
   - cada símbolo remite a lo que representa y se explica o se cosecha en la obra;
   - lo divino no se representa con una figura: se alude con símbolos (luz, sonido) que remiten a
     lo representado.
6. **Calcular el costo antes de empezar**:
   - el coste del render es `fotogramas × ms_por_fotograma + precómputo + audio`;
   - debe ser **≤ la duración del vídeo**, y nunca más de 1,1×;
   - si no cabe, se simplifica el diseño **antes** de producir, no después.

## Fase 4. Narrativa visual: planificar y visualizar

*Fuentes: planificar, mostrar y representar, componer y encuadrar, secuenciar y conectar, y
narrativa audiovisual.*

1. **Escenas**: cada una declara:
   - lugar y momento: dos escenas con el mismo lugar y momento son **continuas**;
   - personajes presentes, vestuario y eje de acción;
   - luz y paleta;
   - función y cómo conecta con el hilo conductor;
   - transición de entrada y su **puente** (sonoro o visual). Las transiciones son coyunturas, no
     saltos.
2. **Plan de planos**. Cada plano declara:
   - inicio y duración;
   - tamaño: GPG, PG, PE, PA, PM, PMC, PP, PPP o PD;
   - cámara: lado del eje, ángulo, focal y movimiento;
   - qué **muestra**;
   - **función narrativa** y **función didáctica**;
   - **canal**: visual, diálogo, texto o narración;
   - composición, sujetos con su posición en pantalla, mirada y movimiento;
   - objetos visibles con su estado y eventos;
   - sonido, y diálogo o texto si los hay.
3. **Componer y encuadrar**:
   - un único **centro de interés** (la piedra angular del cuadro), que es el sujeto principal;
   - jerarquía de principal y secundarios;
   - qué se deja **fuera** del cuadro y por qué;
   - regla de composición: tercios, centrada, simétrica, o libre con motivo;
   - **aire** en la dirección de la mirada y del movimiento.
4. **Secuenciar y conectar**:
   - progresión de causa a efecto;
   - cada plano prepara el siguiente;
   - ritmo con planos de al menos 1 s;
   - variedad de tamaños;
   - tiempo de lectura suficiente: rótulos a 15 caracteres/s + 1 s, y diálogos a 2,8 palabras/s
     como máximo.
5. **Narrativa audiovisual**: cada plano declara su sonido (ambiente, efectos, voz, música o
   silencio). El sonido puede anticipar o unir planos.

## Fase 5. Continuidad: la biblia visual

*Fuentes: mantener y verificar, observar y comparar, y continuidad técnica entre planos.*

La biblia (`biblia`) fija lo invariable:

- **personajes**: rasgos, variantes de vestuario y dirección de viaje;
- **lugares**: geografía, hora, clima y luz clave;
- **objetos**: estado inicial y **transiciones permitidas**, cada una con su causa;
- **paletas**.

El verificador aplica estas reglas de continuidad técnica:

| Código | Regla |
|---|---|
| CON-01 | **Eje de 180°**: en escenas continuas la cámara no cruza el eje sin un motivo declarado: movimiento de cámara visible, plano neutro o nuevo eje. |
| CON-02 | **Posiciones relativas**: quien está a la izquierda sigue a la izquierda, salvo un cruce mostrado en cámara. |
| CON-03 | **Raccord de mirada**: si A mira a B, mira hacia el lado de la pantalla donde está B. |
| CON-04 | **Dirección de movimiento**: un sujeto que avanza hacia la derecha sigue hacia la derecha en el plano siguiente, salvo un cambio de dirección mostrado. |
| CON-05 | **Vestuario**: idéntico en escenas continuas, salvo un cambio declarado. |
| CON-06 | **Presencia**: nadie aparece en un plano sin estar en la escena. |
| CON-07 | **Estados de objetos**: cada cambio es una transición permitida que ocurre en un evento a la vista. Fuera de cámara solo cambian en saltos de tiempo justificados. Nada reaparece ni desaparece. |
| CON-08 | **Luz**: hora, clima y luz clave constantes en escenas continuas, salvo un cambio declarado. |
| NAR-09 | **Regla de 30°**: no se corta entre dos planos casi iguales del mismo sujeto (salto). |

### Puerta A

```bash
python3 -m metodo.verificar <carpeta>/expediente.yaml --fase plan
```

Debe terminar con **0 errores**. Cada aviso se resuelve o se acepta por escrito en `ajustes`.
No se escribe código de producción antes de pasar esta puerta: «el que se apresura llega a la
pobreza».

## Fase 6. Prototipo: la prueba de los diez días

*Fuentes: generar–elegir–prototipar (Daniel), probar y ajustar.*

1. **Fotogramas clave de cada plano** (inicio, medio y fin) con el **motor real** y a la resolución
   final. Es el storyboard verdadero, no un boceto.
2. **Un plano completo en movimiento**, midiendo el tiempo real por fotograma. Con esa medida se
   recalcula el coste (`prototipo.ms_fotograma_medido`).
3. `python3 -m metodo.revisar` sobre el prototipo: hoja de planos, hoja de cortes y hoja por
   personaje.
4. **Enviar al usuario** el storyboard real, el plano en movimiento y el plan resumido.
   - **Por defecto se espera su aprobación** antes de la producción completa
     (`prototipo.estado: aprobado`).
   - Si el usuario pidió el vídeo terminado sin revisión intermedia, se registra con sus palabras
     (`estado: omitido_por_usuario`, `cita`).
5. Lo aprendido se registra como **ajustes** antes de producir. Se incorpora lo aprendido de la
   prueba piloto.

> Lección vivida: el primer intento de «El hombre que quería ser justo» se renderizó durante más de
> 2 horas en un estilo que el usuario no había visto y que no le gustó. Esta puerta existe para que
> eso no se repita.

## Fase 7. Producción

1. El código **lee el expediente**: tiempos, lados de cámara, direcciones en pantalla y estados de
   los objetos (`metodo.expediente.cargar`). No se copian datos a mano.
2. **Render en tiempo real**, de un solo pase, medido de principio a fin con `time`. Incluye
   precómputo, fotogramas, codificación, audio y mezcla.
3. No se renderiza nada que no esté en el plan. Si hace falta algo nuevo, primero se actualiza el
   expediente y se vuelve a verificar.

## Fase 8. Observar, comparar, probar y ajustar

*Fuentes: observar y comparar, mantener y verificar, probar y ajustar.*

1. `python3 -m metodo.revisar <expediente> <video> --render-s <segundos medidos>` genera:
   - **Hoja de cortes**: último fotograma de cada plano junto al primero del siguiente. Marca:
     - los cortes de escenas continuas con un salto de exposición (|ΔL| > 40) o un error grosero de
       balance de blancos (ΔC > 40), sin `cambio_luz` declarado;
     - los cortes que no aparecen en el fotograma que dice el expediente.

     Los umbrales están calibrados con 27 cortes reales ([`CALIBRACION.md`](CALIBRACION.md)).
   - **Hoja por personaje**: el personaje en todos sus planos, para compararlo con la biblia.
   - **Hoja de planos**: un fotograma por plano, para comprobar que se entiende sin texto.
   - **Medición de la entrega**: resolución, fps, duración, sonoridad integrada (LUFS) y pico
     real.
2. **Dos testigos por veredicto**: cada corte marcado necesita la regla del plan o la medición,
   más la inspección visual de la hoja. El veredicto se anota en `entrega.veredictos`. Ningún
   veredicto se da por la sola palabra de un testigo.
3. **Lista de revisión manual** (`entrega.revision_manual`). Se responde cada punto con
   evidencia:

   | Código | Pregunta |
   |---|---|
   | REV-01 | ¿Se entiende cada plano sin diálogos ni rótulos? (hoja de planos) |
   | REV-02 | ¿Cada personaje conserva rasgos y vestuario de la biblia? (hoja por personaje) |
   | REV-03 | ¿Cada corte marcado tiene veredicto con dos testigos? |
   | REV-04 | ¿La idea central se ve en una acción? |
   | REV-05 | ¿Hay algo que se luce sin servir al mensaje? (vanidad) |
   | REV-06 | ¿Luz, paleta y composición son coherentes con el estilo aprobado y la biblia? |
   | REV-07 | ¿El sonido está medido (sonoridad, picos) y ningún efecto contradice la imagen? |
   | REV-08 | ¿El mensaje y los diálogos del usuario están intactos, salvo cambios aprobados? |
   | REV-09 | ¿Los símbolos remiten a lo que representan y lo divino se alude sin figura? |
4. **Ajustar con proporción**. Cada ajuste queda registrado en `ajustes` con problema, causa,
   cambio y verificación:
   - se aísla la falla y se reemplaza solo la piedra dañada;
   - se usa la corrección mínima, con la herramienta adecuada;
   - se prefiere podar a añadir;
   - después se vuelve a verificar.

### Puerta C

```bash
python3 -m metodo.verificar <carpeta>/expediente.yaml --fase final
```

Debe terminar con 0 errores. Exige además:

- el render medido ≤ 1,1× la duración;
- la técnica conforme: resolución, fps, duración, sonoridad entre −18 y −14 LUFS, y pico real
  ≤ −1 dBTP;
- todos los ajustes verificados;
- todos los cortes marcados con veredicto;
- la lista REV completa.

## Fase 9. Entrega y evaluación

El informe al usuario empieza por el resultado y contiene:

1. Qué enseña la obra (objetivo y pregunta central) y cómo lo hace (secuencia).
2. **Solo lo medido**: tiempo de render, duración, sonoridad. Nada se afirma sin medirlo. El
   sonido no se puede escuchar desde aquí, así que solo se informa de sus mediciones.
3. Los ajustes hechos y cualquier cambio al guion.
4. Las limitaciones conocidas.
5. Las **preguntas de comprobación** para probar el vídeo con espectadores reales: la evaluación
   final del aprendizaje la hacen personas, no el código.

---

## Reglas permanentes

| N.º | Regla | Origen |
|---|---|---|
| R1 | Nada se produce sin un expediente que pase la Puerta A. | Planificar; calcular el costo |
| R2 | Render ≤ duración del vídeo, nunca más de 1,1×, medido de principio a fin. | Pedido del usuario; calcular el costo |
| R3 | Mostrar, no solo decir: la idea central se ve en una acción. | Enseñar con la conducta; acción profética |
| R4 | Todo elemento tiene una función narrativa y didáctica; nada para lucirse. | Sin palabrería vana; Babel |
| R5 | Fidelidad al guion del usuario; los cambios se proponen y se aprueban. | Fidelidad al modelo |
| R6 | Solo se afirma lo medido o verificado; lo no confirmado se marca. | Autoridad auténtica; pesas justas |
| R7 | Dos testigos para cada veredicto de continuidad o de verdad. | Dos o tres testigos |
| R8 | Probar antes de invertir: el prototipo se aprueba antes de la producción completa. | Prueba de Daniel |
| R9 | Gradualidad: nada se enseña antes que su fundamento. | Leche y alimento sólido |
| R10 | Lo divino no se representa con una figura; se alude con símbolos. | Representación veraz |
| R11 | Se habla en la lengua del oyente: el público y el idioma se definen siempre. | Pentecostés; Areópago |
| R12 | El resultado depurado vale más que la primera versión: se ajusta hasta pasar la Puerta C. | Mejor es el fin que el principio |

## Uso rápido

```bash
# 1. Nuevo vídeo
mkdir mi_video && cp metodo/plantilla.yaml mi_video/expediente.yaml

# 2. Verificar el plan (Puerta A)
python3 -m metodo.verificar mi_video/expediente.yaml --fase plan

# 3. Revisar el prototipo o el vídeo
python3 -m metodo.revisar mi_video/expediente.yaml mi_video/video.mp4 --render-s 31.7

# 4. Puerta C
python3 -m metodo.verificar mi_video/expediente.yaml --fase final

# Pruebas del propio método
python3 -m unittest discover -s metodo/pruebas -t . -v
```

Desde el código de producción:

```python
from metodo.expediente import cargar
ex = cargar("mi_video/expediente.yaml")
for p in ex.planos:                       # tiempos y fotogramas exactos de cada plano
    f0, f1 = ex.fotogramas(p)
f = ex.fotograma_de(16.92)                # misma convención que el motor (primer fotograma con t ≥ inicio)
estado = ex.estado_objetos(12.0)          # estado de cada objeto de la biblia en un instante
lado = ex.lado_en_pantalla("P3", "hombre")            # 'izquierda' / 'derecha' según el eje
mira = ex.direccion_hacia("P3", "hombre", "anciana")  # hacia dónde debe mirar o moverse
```

# Pruebas del método con los ejemplos de la conversación del usuario

## «La decisión» (`la_decision/`)

Es el ejemplo de narrativa visual de la conversación. El guion se conserva íntegro en
`la_decision/guion.md`. El expediente completa las fases 0 a 5 y **supera la Puerta A**:

```bash
python3 -m metodo.verificar metodo/ejemplos/la_decision/expediente.yaml --fase plan
# 0 errores, 1 aviso (un cambio al guion pendiente de aprobación) → PUERTA SUPERADA
```

Al aplicar el método aparecieron dos problemas que una lectura normal no ve:

1. **Incoherencia en el propio guion (CON-07).**
   - En la escena 3 «la persona mayor sostiene la bolsa».
   - En la escena 4 «el hombre entrega la bolsa».
   - La bolsa nunca pasa a sus manos.

   Corrección mínima propuesta (ajuste A1): el hombre entrega **la última naranja**, la que rodó
   hasta su zapato. Se mantiene el gesto de entregar y no se añaden acciones. Además, esa naranja se
   convierte en el símbolo de la obra (siembra en P2, cosecha en P7). Como cambia el guion, queda
   pendiente de la aprobación del usuario: el verificador no deja pasar a producción sin ella.
2. **Un error mío al planificar (NAR-07).** El rótulo final (69 caracteres) tenía 5,0 s y
   necesita 5,6 s para leerse. Se corrigió (ajuste A2).

Pasar a producción exige además el prototipo aprobado (PRO-01) y el coste medido (PRO-02):

```bash
python3 -m metodo.verificar metodo/ejemplos/la_decision/expediente.yaml --fase produccion
# 3 errores → NO SUPERADA (como debe ser hasta que el usuario apruebe)
```

## «La envidia» (`envidia/`)

Es la prueba del método de enfoques específicos de la conversación (solo fase 1).

- Las tres investigaciones citadas se verificaron y se registraron con su referencia completa:
  - Lange y Crusius, 2015;
  - van de Ven, Zeelenberg y Pieters, 2012;
  - Meier y Johnson, 2022.
- El dato «4 estudios con 1.094 participantes» atribuido al estudio de 2015 **no se pudo
  confirmar** en las fuentes consultadas. Queda marcado como no confirmado y el verificador avisa
  de que no puede presentarse como hecho.

```bash
python3 -m metodo.verificar metodo/ejemplos/envidia/expediente.yaml --fase enfoque
# 0 errores, 1 aviso (dato no confirmado) → PUERTA SUPERADA
```

Veredicto: **reformular**. La envidia no siempre conduce a perjudicarse: puede impulsar a mejorar
(envidia benigna) o a dañar (maliciosa). El merecimiento y el control percibidos influyen en cuál
de las dos aparece.

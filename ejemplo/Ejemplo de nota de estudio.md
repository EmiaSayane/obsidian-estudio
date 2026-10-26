---
tipo: theory
fecha: 2026-10-24 21:30
modulo: Fundamentals of AI
seccion: 03. Unsupervised Learning Algorithms
tags: [machine-learning, clustering]
---

# K-Means Clustering

Aqui escribo la nota normal, como siempre. Lo de arriba (entre las rayas) son las propiedades.

---

# GUIA RAPIDA: como rellenar las propiedades

Esta nota es solo un ejemplo para consultar cuando se me olvide. Va en `_sistema/documentos/`, nunca suelta en la raiz del vault, asi el script no la mueve.

## Flujo de siempre

1. Creo la nota nueva. Se carga la plantilla sola.
2. Relleno las propiedades (abajo explico cada una).
3. Escribo la nota.
4. Corro `python sistema.py ordenar` (mueve la nota a su carpeta y le pone numero si le falta).
5. Corro `python sistema.py roadmap` (actualiza el indice del curso).

## Las propiedades, una por una

**tipo** (menu, no se escribe a mano)
Opciones fijas: `theory`, `interactive`, `lab`. Siempre en ingles y en minuscula, porque el script las lee tal cual.

**fecha**
Viene sola al crear la nota. No se toca.

**modulo**
El modulo de la plataforma, NO la certificacion. Ejemplo: `Fundamentals of AI`, `Web Requests`.
La certificacion (cwes, etc.) no va en las notas. Vive aparte, en una nota de certificacion (ver abajo).
Se elige del menu. Si es un modulo nuevo, elijo "otro" y lo escribo como aparece en la plataforma.
Con "otro", la plantilla agrega `modulo_nuevo: true` y el script crea la carpeta del modulo y su indice. Esa linea la borra el script despues.
Si el nombre se parece mucho a un modulo que ya existe, el script no lo crea y me avisa en el reporte (probable error de tipeo).

**seccion**
La seccion dentro del modulo, con su numero de la plataforma. Formato: `NN. Nombre`.
Ejemplo: `03. Unsupervised Learning Algorithms`.
Aqui si escribo a mano, porque van apareciendo secciones nuevas a medida que estudio.
Si la carpeta de la seccion no existe, el script la crea. Si encuentra una casi igual (error de tipeo), no crea nada, deja la nota suelta y me avisa en el reporte.

**tags**
Temas que cruzan carpetas: `nmap`, `xss`, `clustering`. Varios separados por coma, en minuscula, sin espacios (usar guion).

## Nombre del archivo

Escribo el titulo limpio, sin numero: `K-Means Clustering`.
Si no tiene numero, el script le pone el siguiente libre de la seccion (`02. K-Means Clustering`).
Si quiero insertar algo en el medio, le pongo el numero yo y el script lo respeta.
Siempre dos digitos (01, 02, ... 10) para que 10 no quede antes que 2.

## Si la nota es un lab

Elijo `tipo: lab` y la plantilla agrega esta linea al inicio:

Teoria relacionada: [[pegar aqui el enlace a la nota de teoria]]

Asi desde la teoria veo que labs la practican, y desde el lab veo en que teoria se apoya.

## Donde viven las cosas

El contenido se guarda UNA sola vez, por modulo. Las certificaciones solo enlazan.

```
estudio/
  modulos/
    Fundamentals of AI/
      Fundamentals of AI.md        (indice del modulo, lo genera el script)
      01. Introduction to Machine Learning/
        01. Introduction to Machine Learning.md
  certificaciones/
    CWES.md                        (la hago yo a mano)
```

## Certificaciones

Una certificacion es una nota en `estudio/certificaciones/` con la lista ordenada de sus modulos, como enlaces al indice de cada modulo:

```
# CWES
1. [[Introduction to Networking]]
2. [[Web Requests]]
3. [[Fundamentals of AI]]
```

- El orden de los modulos es de la certificacion, no del modulo (el mismo modulo puede ir 2do en una y 5to en otra). Por eso esa lista la escribo yo.
- Si un modulo esta en dos certificaciones, lo enlazo en las dos. La nota del modulo no se duplica ni se toca.
- Desde el indice de un modulo veo en que certificaciones esta mirando los enlaces entrantes.

## Si algo falla

- La nota se quedo suelta en la raiz: revisar el reporte del script. Casi siempre falta `modulo` o `seccion`, o hay un error de tipeo.
- El roadmap no muestra la nota: correr `roadmap` de nuevo. Solo se actualiza cuando lo corro.
- Dos notas con el mismo nombre en cursos distintos: el script lo detecta y escribe esos enlaces con la ruta completa.

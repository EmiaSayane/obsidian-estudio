# obsidian-estudio

Script y plantilla para ordenar notas de estudio en Obsidian. Escribes la nota a mano, le pones unas propiedades, y el script la mueve a su carpeta, la numera y genera el roadmap de cada modulo.

Solo usa la biblioteca estandar de Python (3.8 o mas nuevo). No toca nada fuera del vault que le indiques.

## Que hace

- `ordenar`: mueve las notas sueltas de la raiz del vault a `modulos/<Modulo>/<NN. Seccion>/`, les pone numero si les falta, crea modulos y secciones nuevos cuando corresponde y ordena los adjuntos sueltos.
- `roadmap [modulo]`: regenera el indice de cada modulo (el orden de lectura, con el tipo de cada nota).
- `revisar`: solo informa (modulos sin certificacion, enlaces rotos, nombres repetidos, propiedades que no calzan con la carpeta).
- `todo`: `ordenar` y despues `roadmap` de todos los modulos.

Todos simulan por defecto. Con `--aplicar` ejecutan de verdad. Cada corrida deja un reporte en `_sistema/documentos/reporte.md` dentro del vault.

## Propiedades de una nota

```
---
tipo: theory            # theory, interactive o lab
fecha: 2026-10-24 21:30
modulo: Fundamentals of AI
seccion: 03. Unsupervised Learning Algorithms
tags: [machine-learning, clustering]
---
```

Para un modulo que todavia no existe, se agrega `modulo_nuevo: true`. Asi el script sabe que no es un error de tipeo. Si el nombre se parece mucho a uno existente, avisa y no crea nada (para forzarlo, `modulo_nuevo: forzar`).

Hay una nota de ejemplo con la guia completa en `ejemplo/`.

## Estructura esperada del vault

```
(raiz)                      aqui nacen las notas nuevas, sueltas
modulos/
  <Modulo>/
    <Modulo>.md             indice (lo genera el script)
    <NN. Seccion>/
      <NN. Nota>.md
certificaciones/
  <Certificacion>.md        las escribes a mano, con enlaces a los modulos
_sistema/
  plantillas/               la plantilla de Templater
  documentos/               reglas y reporte
  adjuntos/                 imagenes, pdf, etc.
```

## Uso

El codigo vive aqui, fuera del vault. Se le indica el vault con `--vault`:

```
python3 sistema.py todo --vault "/ruta/al/vault"            # simula
python3 sistema.py todo --aplicar --vault "/ruta/al/vault"  # ejecuta
```

Para no escribir la ruta cada vez, un alias en `~/.zshrc`:

```
alias estudio='python3 ~/GitHub/obsidian-estudio/sistema.py --vault "/ruta/al/vault"'
```

Y despues: `estudio todo`, `estudio todo --aplicar`, `estudio revisar`.

## Plantilla

`plantillas/nota-estudio.md` es una plantilla de [Templater](https://github.com/SilentVoid13/Templater). Va dentro del vault, en `_sistema/plantillas/`. Pregunta tipo, modulo, seccion y tags con menus que salen de las carpetas y tags reales del vault.

## Seguridad

El script solo lee y mueve archivos dentro del vault que le pasas, y nunca borra notas. Aun asi, antes de la primera corrida con `--aplicar`, conviene tener el vault respaldado y revisar lo que muestra la simulacion.
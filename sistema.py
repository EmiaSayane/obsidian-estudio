#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sistema.py: ordena las notas de estudio de un vault de Obsidian y genera roadmaps.

Solo usa la libreria estandar de Python (3.8 o superior).

Comandos (todos simulan por defecto; agrega --aplicar para ejecutar de verdad):

    python3 sistema.py ordenar            mueve las notas sueltas a su seccion y ordena los adjuntos
    python3 sistema.py roadmap [modulo]   regenera el indice de un modulo (o de todos)
    python3 sistema.py revisar            solo informa: huerfanos, duplicados, inconsistencias
    python3 sistema.py todo               ordenar y despues roadmap de todos los modulos

Estructura esperada del vault (el script vive en _sistema/codigo/):

    (raiz del vault)                            notas nuevas, sueltas, sin ordenar
    00-inbox/                                   opcional: tambien se revisa si existe
    modulos/<Modulo>/<NN. Seccion>/<NN. Nota>.md
    modulos/<Modulo>/<Modulo>.md                indice del modulo (lo genera el script)
    certificaciones/<Cert>.md                   la escribes tu a mano, con enlaces a modulos
    _sistema/                                   todo lo del sistema, ordenado en subcarpetas:
        codigo/sistema.py                       este script
        plantillas/nota-estudio.md              plantilla de Templater
        documentos/                             Reglas del sistema, ejemplo, reporte.md
        adjuntos/                               imagenes, pdf y otros adjuntos

Reglas que sigue el script:
  - Una nota se considera de estudio si tiene alguna de las propiedades tipo, modulo o seccion.
    Las demas notas sueltas (ideas, borradores sin esas propiedades) no se tocan.
    Se revisan las notas que estan directamente en la raiz del vault y las de 00-inbox/.
  - Los adjuntos (imagenes, pdf, audio, video) que queden sueltos en la raiz se mueven a _sistema/adjuntos/.
    Si una nota los enlaza con ruta (formato markdown) no se mueven, para no romper el enlace.
  - Un modulo se crea solo si la nota trae `modulo_nuevo: true` (la plantilla lo agrega cuando
    eliges "otro"). Si el nombre se parece mucho a un modulo existente, no se crea y la nota queda
    suelta con un aviso (para forzarlo: `modulo_nuevo: forzar`). Sin esa marca, un modulo que
    no existe deja la nota suelta.
  - Las secciones se crean solo si no hay otra con el mismo numero ni el mismo nombre.
    Asi un error de tipeo no llena el vault de carpetas basura.
  - Si el nombre de la nota no empieza con numero, se le asigna el siguiente libre de la seccion.
  - Si una nota cambia de nombre, los enlaces [[...]] que apuntaban a ella se actualizan.
"""
from __future__ import annotations

import argparse
import difflib
import re
import shutil
import sys
import unicodedata
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

TIPOS = ("theory", "interactive", "lab")
INBOX = "00-inbox"
ADJUNTOS = "_sistema/adjuntos"
EXT_ADJUNTOS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp", ".avif", ".heic",
                ".pdf", ".mp4", ".mov", ".webm", ".mp3", ".m4a", ".wav"}
MODULOS = "modulos"
CERTS = "certificaciones"
SISTEMA = "_sistema"
START = "<!-- roadmap:start -->"
END = "<!-- roadmap:end -->"
NUM_RE = re.compile(r"^(\d+)\.\s+(.*)$")


# ---------------------------------------------------------------- utilidades

def norm(s: str) -> str:
    """Minusculas, sin tildes ni puntuacion, para comparar nombres."""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def visible(p: Path) -> bool:
    return not p.name.startswith(".")


def md_del_vault(v: Path):
    """Todos los .md del vault, sin carpetas ocultas (.obsidian, .git, etc.) ni _sistema/
    (las reglas y ejemplos del sistema no son contenido de estudio)."""
    for f in v.rglob("*.md"):
        rel = f.relative_to(v)
        if any(part.startswith(".") for part in rel.parts) or rel.parts[0] == SISTEMA:
            continue
        yield f


def rel(v: Path, p: Path) -> str:
    return p.relative_to(v).as_posix()


def split_frontmatter(text: str):
    """Devuelve (lineas_del_frontmatter, indice_de_cierre) o None si no hay."""
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return lines[1:i], i
    return None


def leer_props(path: Path):
    text = path.read_text(encoding="utf-8")
    fm = split_frontmatter(text)
    if fm is None:
        return None, text
    props = {}
    for ln in fm[0]:
        m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*?)\s*$", ln)
        if m:
            props[m.group(1)] = m.group(2).strip().strip('"').strip("'")
    return props, text


def yaml_valor(valor: str) -> str:
    if re.search(r":\s|\s#|^[\[\]{}&*!|>'\"%@`]", valor):
        return '"' + valor.replace('"', '\\"') + '"'
    return valor


def set_prop(text: str, clave: str, valor: str) -> str:
    lines = text.split("\n")
    fm = split_frontmatter(text)
    if fm is None:
        return text
    fin = fm[1]
    nueva = f"{clave}: {yaml_valor(valor)}"
    for i in range(1, fin):
        if re.match(rf"^{re.escape(clave)}:", lines[i]):
            lines[i] = nueva
            return "\n".join(lines)
    lines.insert(fin, nueva)
    return "\n".join(lines)


def quitar_prop(text: str, clave: str) -> str:
    fm = split_frontmatter(text)
    if fm is None:
        return text
    lines = text.split("\n")
    fin = fm[1]
    medio = [ln for ln in lines[1:fin] if not re.match(rf"^{re.escape(clave)}:", ln)]
    return "\n".join(lines[:1] + medio + lines[fin:])


def num_y_titulo(nombre: str):
    m = NUM_RE.match(nombre.strip())
    if not m:
        return None, nombre.strip()
    return int(m.group(1)), m.group(2).strip()


def subcarpetas(p: Path):
    if not p.is_dir():
        return []
    return sorted(d for d in p.iterdir() if d.is_dir() and visible(d))


def numeros_en(sec_dir: Path):
    nums = set()
    if sec_dir.is_dir():
        for f in sec_dir.glob("*.md"):
            n, _ = num_y_titulo(f.stem)
            if n is not None:
                nums.add(n)
    return nums


# ---------------------------------------------------------------- reporte

class Reporte:
    def __init__(self, titulo: str, aplicar: bool, solo_informa: bool = False):
        self.titulo = titulo
        self.aplicar = aplicar
        self.solo_informa = solo_informa
        self.lineas = []

    def h(self, texto):
        self.lineas.append("")
        self.lineas.append(f"## {texto}")

    def add(self, texto):
        self.lineas.append(texto)

    def texto(self):
        if self.solo_informa:
            modo = "SOLO INFORMA (este comando nunca modifica nada)"
        else:
            modo = "APLICADO" if self.aplicar else "SIMULACION (no se toco nada, agrega --aplicar para ejecutar)"
        cab = [f"# {self.titulo}", "", f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M')}", f"Modo: {modo}"]
        return "\n".join(cab + self.lineas) + "\n"


# ---------------------------------------------------------------- enlaces

def reescribir_enlaces(v: Path, viejo: str, nuevo: str, aplicar: bool):
    """Cambia [[viejo]] por [[nuevo]] en todo el vault. Devuelve los archivos afectados."""
    patron = re.compile(r"\[\[" + re.escape(viejo) + r"(?=[\]|#^])")
    afectados = []
    for f in md_del_vault(v):
        try:
            t = f.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        t2 = patron.sub("[[" + nuevo, t)
        if t2 != t:
            afectados.append(f)
            if aplicar:
                f.write_text(t2, encoding="utf-8")
    return afectados


# ---------------------------------------------------------------- ordenar

def buscar_modulo(v: Path, nombre: str, extra=()):
    """Busca un modulo por nombre (sin importar mayusculas ni tildes).
    `extra` son carpetas de modulos que se crearan en esta misma corrida."""
    mods = subcarpetas(v / MODULOS) + list(extra)
    for d in mods:
        if norm(d.name) == norm(nombre):
            return d, []
    parecidos = difflib.get_close_matches(norm(nombre), [norm(d.name) for d in mods], n=3, cutoff=0.6)
    sugeridos = [d.name for d in mods if norm(d.name) in parecidos]
    return None, sugeridos


def modulos_cercanos(v: Path, nombre: str, extra=()):
    """Modulos con nombre casi igual (probable error de tipeo al crear uno nuevo)."""
    mods = subcarpetas(v / MODULOS) + list(extra)
    return [d.name for d in mods
            if difflib.SequenceMatcher(None, norm(d.name), norm(nombre)).ratio() >= 0.8]


def resolver_seccion(mod_dir: Path, seccion: str, planeadas=()):
    """Devuelve (carpeta, es_nueva, error). `planeadas` son secciones que se crearan en esta corrida."""
    n, titulo = num_y_titulo(seccion)
    if n is None or not titulo:
        return None, False, f"la seccion '{seccion}' debe tener formato 'NN. Nombre' (ejemplo: 03. Unsupervised Learning Algorithms)"
    for d in subcarpetas(mod_dir) + list(planeadas):
        dn, dt = num_y_titulo(d.name)
        if dn is None:
            continue
        if dn == n:
            if norm(dt) == norm(titulo):
                return d, False, None
            return None, False, (f"ya existe la seccion '{d.name}' con el numero {n:02d}, "
                                 f"pero escribiste '{seccion}'. Corrige el nombre en la nota")
        if norm(dt) == norm(titulo):
            return None, False, f"ya existe '{d.name}' con ese nombre pero otro numero. Revisa el numero en la nota"
    return mod_dir / f"{n:02d}. {titulo}", True, None


def barrer_adjuntos(v: Path, aplicar: bool):
    """Mueve a _sistema/adjuntos/ los adjuntos sueltos en la raiz del vault.
    No mueve uno si alguna nota lo enlaza con ruta (formato markdown), porque se romperia el enlace.
    Los enlaces con [[nombre]] no se rompen al mover."""
    sueltos = [f for f in sorted(v.iterdir())
               if f.is_file() and visible(f) and f.suffix.lower() in EXT_ADJUNTOS]
    if not sueltos:
        return [], []
    textos = []
    for f in md_del_vault(v):
        try:
            textos.append(f.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, OSError):
            continue
    todo = "\n".join(textos)
    destino_dir = v / ADJUNTOS
    movidos, saltados = [], []
    for f in sueltos:
        dest = destino_dir / f.name
        if dest.exists():
            saltados.append((f.name, f"ya existe un archivo con ese nombre en {ADJUNTOS}/"))
            continue
        patron = r"\]\(\s*<?(\./)?(" + re.escape(f.name) + "|" + re.escape(quote(f.name)) + ")"
        if re.search(patron, todo):
            saltados.append((f.name, "una nota lo enlaza con ruta (formato markdown), moverlo romperia ese enlace"))
            continue
        if aplicar:
            destino_dir.mkdir(parents=True, exist_ok=True)
            shutil.move(str(f), str(dest))
        movidos.append(f.name)
    return movidos, saltados


def ordenar(v: Path, aplicar: bool) -> Reporte:
    rep = Reporte("Reporte de ordenar", aplicar)
    if not (v / MODULOS).is_dir():
        sys.exit(f"No encuentro la carpeta {MODULOS}/ en {v}")

    # notas sueltas: las que estan directo en la raiz del vault, mas las de 00-inbox/ si existe
    fuentes = [f for f in sorted(v.glob("*.md")) if visible(f)]
    inbox = v / INBOX
    if inbox.is_dir():
        for f in sorted(inbox.rglob("*.md")):
            if not any(p.startswith(".") for p in f.relative_to(inbox).parts):
                fuentes.append(f)

    candidatas, ignoradas = [], []
    for f in fuentes:
        props, text = leer_props(f)
        if props is None or not (set(props) & {"tipo", "modulo", "seccion"}):
            ignoradas.append(f)
            continue
        candidatas.append((props.get("fecha", ""), f.name, f, props, text))
    # las mas antiguas primero, para que la numeracion siga el orden en que estudias
    candidatas.sort(key=lambda t: (t[0], t[1]))

    movidas, pendientes, creadas, enlaces = [], [], [], []
    planeados = defaultdict(set)
    destinos = set()
    secciones_creadas = set()
    secciones_planeadas = defaultdict(list)
    modulos_planeados = {}
    modulos_nuevos = []
    tocados = set()

    for _, _, f, props, text in candidatas:
        modulo_es_nuevo = False
        nombre = rel(v, f)
        tipo = props.get("tipo", "").strip().lower()
        modulo = props.get("modulo", "").strip()
        seccion = props.get("seccion", "").strip()

        if tipo not in TIPOS:
            pendientes.append((nombre, f"tipo '{props.get('tipo', '')}' no valido. Usa: {', '.join(TIPOS)}"))
            continue
        if not modulo or not seccion:
            faltan = [c for c, val in (("modulo", modulo), ("seccion", seccion)) if not val]
            pendientes.append((nombre, "falta rellenar: " + ", ".join(faltan)))
            continue

        mod_dir, sugeridos = buscar_modulo(v, modulo, modulos_planeados.values())
        if mod_dir is None:
            flag = props.get("modulo_nuevo", "").strip().lower()
            if flag not in ("true", "si", "sí", "yes", "forzar"):
                msg = (f"el modulo '{modulo}' no existe en {MODULOS}/. Si es un modulo nuevo, "
                       f"elige 'otro' en la plantilla o agrega 'modulo_nuevo: true' a la nota")
                if sugeridos:
                    msg += ". Quizas quisiste decir: " + ", ".join(sugeridos)
                pendientes.append((nombre, msg))
                continue
            if re.search(r'[\\/:*?"<>|#^\[\]]', modulo):
                pendientes.append((nombre, f"el nombre de modulo '{modulo}' tiene caracteres no permitidos"))
                continue
            if flag != "forzar":
                cercanos = modulos_cercanos(v, modulo, modulos_planeados.values())
                if cercanos:
                    pendientes.append((nombre, (
                        f"el modulo nuevo '{modulo}' se parece mucho a: {', '.join(cercanos)}. "
                        f"Si es el mismo, corrige el modulo en la nota. "
                        f"Si de verdad es otro, escribe 'modulo_nuevo: forzar'")))
                    continue
            mod_dir = v / MODULOS / modulo.strip()
            modulo_es_nuevo = True

        sec_dir, es_nueva, error = resolver_seccion(mod_dir, seccion, secciones_planeadas[mod_dir])
        if error:
            pendientes.append((nombre, error))
            continue

        usados = numeros_en(sec_dir) | planeados[sec_dir]
        n_actual, titulo = num_y_titulo(f.stem)
        if n_actual is not None:
            if n_actual in usados:
                pendientes.append((nombre, f"ya hay una nota con el numero {n_actual:02d} en '{sec_dir.name}'. Cambia el numero"))
                continue
            n = n_actual
        else:
            n = max(usados, default=0) + 1
            titulo = f.stem.strip()
        nuevo_stem = f"{n:02d}. {titulo}"
        dest = sec_dir / f"{nuevo_stem}.md"
        if dest.exists() or dest in destinos:
            pendientes.append((nombre, f"ya existe '{rel(v, dest)}'"))
            continue

        planeados[sec_dir].add(n)
        destinos.add(dest)
        tocados.add(mod_dir)

        if modulo_es_nuevo:
            modulos_planeados[norm(mod_dir.name)] = mod_dir
            modulos_nuevos.append(rel(v, mod_dir))
        if es_nueva and sec_dir not in secciones_creadas:
            secciones_creadas.add(sec_dir)
            secciones_planeadas[mod_dir].append(sec_dir)
            creadas.append(rel(v, sec_dir))

        afectados = []
        if nuevo_stem != f.stem:
            afectados = reescribir_enlaces(v, f.stem, nuevo_stem, False)

        if aplicar:
            sec_dir.mkdir(parents=True, exist_ok=True)
            nuevo = set_prop(text, "tipo", tipo)
            nuevo = set_prop(nuevo, "modulo", mod_dir.name)
            nuevo = set_prop(nuevo, "seccion", sec_dir.name)
            nuevo = quitar_prop(nuevo, "modulo_nuevo")
            if nuevo != text:
                f.write_text(nuevo, encoding="utf-8")
            shutil.move(str(f), str(dest))
            if nuevo_stem != f.stem:
                reescribir_enlaces(v, f.stem, nuevo_stem, True)
        movidas.append((nombre, rel(v, dest), len(afectados)))

    verbo = "Movidas" if aplicar else "Se moveran"
    rep.h(f"{verbo} ({len(movidas)})")
    if movidas:
        for origen, destino, n_enl in movidas:
            extra = f"  (enlaces actualizados en {n_enl} nota(s))" if n_enl else ""
            rep.add(f"- {origen}  ->  {destino}{extra}")
    else:
        rep.add("- Nada que mover.")

    if modulos_nuevos:
        rep.h(f"Modulos nuevos ({len(set(modulos_nuevos))})")
        for m in sorted(set(modulos_nuevos)):
            rep.add(f"- {m}")

    if creadas:
        rep.h(f"Secciones nuevas ({len(creadas)})")
        for c in creadas:
            rep.add(f"- {c}")

    rep.h(f"Pendientes, siguen sueltas ({len(pendientes)})")
    if pendientes:
        for nombre, motivo in pendientes:
            rep.add(f"- {nombre}: {motivo}")
    else:
        rep.add("- Ninguno.")

    if ignoradas:
        rep.h(f"Notas sueltas sin propiedades de estudio, no se tocaron ({len(ignoradas)})")
        for f in ignoradas:
            rep.add(f"- {rel(v, f)}")

    movidos_adj, saltados_adj = barrer_adjuntos(v, aplicar)
    if movidos_adj:
        rep.h(f"Adjuntos movidos a {ADJUNTOS}/ ({len(movidos_adj)})")
        for a in movidos_adj:
            rep.add(f"- {a}")
    if saltados_adj:
        rep.h(f"Adjuntos que no se movieron ({len(saltados_adj)})")
        for a, motivo in saltados_adj:
            rep.add(f"- {a}: {motivo}")
    return rep


# ---------------------------------------------------------------- roadmap

def mapa_de_nombres(v: Path):
    nombres = defaultdict(list)
    for f in md_del_vault(v):
        nombres[f.stem].append(f)
    return nombres


def enlace(v: Path, f: Path, nombres) -> str:
    if len(nombres[f.stem]) > 1:
        return f"[[{rel(v, f.with_suffix(''))}|{f.stem}]]"
    return f"[[{f.stem}]]"


def construir_bloque(v: Path, mod_dir: Path, nombres):
    secciones = []
    for d in subcarpetas(mod_dir):
        n, titulo = num_y_titulo(d.name)
        if n is not None:
            secciones.append((n, titulo, d))
    secciones.sort(key=lambda t: t[0])

    out = [START, "%% Generado por sistema.py. Lo que escribas entre las marcas se reemplaza. %%"]
    for n, titulo, d in secciones:
        out.append("")
        out.append(f"## {n:02d} {titulo}")
        notas = []
        for f in d.glob("*.md"):
            if not visible(f):
                continue
            nn, _ = num_y_titulo(f.stem)
            notas.append(((0, nn, f.name) if nn is not None else (1, 0, f.name), f))
        notas.sort(key=lambda t: t[0])
        if not notas:
            out.append("- (sin notas todavia)")
        for _, f in notas:
            props, _txt = leer_props(f)
            tipo = (props or {}).get("tipo", "").strip().lower()
            marca = f" ({tipo})" if tipo in TIPOS else ""
            out.append(f"- {enlace(v, f, nombres)}{marca}")
    faltan = []
    if secciones:
        presentes = {n for n, _, _ in secciones}
        faltan = [f"{i:02d}" for i in range(1, max(presentes) + 1) if i not in presentes]
        if faltan:
            out.append("")
            out.append("Secciones aun sin notas: " + ", ".join(faltan))
    out.append(END)
    return "\n".join(out), faltan


def roadmap(v: Path, modulo: str | None, aplicar: bool) -> Reporte:
    rep = Reporte("Reporte de roadmap", aplicar)
    if not (v / MODULOS).is_dir():
        sys.exit(f"No encuentro la carpeta {MODULOS}/ en {v}")
    if modulo:
        d, sugeridos = buscar_modulo(v, modulo)
        if d is None:
            extra = (" Quizas: " + ", ".join(sugeridos)) if sugeridos else ""
            sys.exit(f"El modulo '{modulo}' no existe.{extra}")
        mods = [d]
    else:
        mods = subcarpetas(v / MODULOS)

    nombres = mapa_de_nombres(v)
    rep.h(f"Modulos ({len(mods)})")
    for mod_dir in mods:
        bloque, faltan = construir_bloque(v, mod_dir, nombres)
        indice = mod_dir / f"{mod_dir.name}.md"
        if indice.exists():
            texto = indice.read_text(encoding="utf-8")
            if START in texto and END in texto:
                antes = texto.split(START)[0]
                despues = texto.split(END, 1)[1]
                nuevo = antes + bloque + despues
                accion = "actualizado"
            else:
                nuevo = texto.rstrip("\n") + "\n\n" + bloque + "\n"
                accion = "bloque agregado al final"
        else:
            nuevo = (f"---\ntipo: indice-modulo\nmodulo: {yaml_valor(mod_dir.name)}\n---\n\n"
                     f"# {mod_dir.name}\n\n{bloque}\n")
            texto = None
            accion = "creado"
        cambio = texto != nuevo
        if cambio and aplicar:
            indice.write_text(nuevo, encoding="utf-8")
        estado = accion if cambio else "sin cambios"
        rep.add(f"- {rel(v, indice)}: {estado}")
        if faltan:
            rep.add(f"    secciones sin notas: {', '.join(faltan)}")
    return rep


# ---------------------------------------------------------------- revisar

def revisar(v: Path) -> Reporte:
    rep = Reporte("Reporte de revisar", False, solo_informa=True)
    mods = subcarpetas(v / MODULOS)

    # modulos huerfanos y enlaces rotos en certificaciones
    enlazados = set()
    rotos = []
    for cert in sorted((v / CERTS).glob("*.md")) if (v / CERTS).is_dir() else []:
        txt = cert.read_text(encoding="utf-8")
        for m in re.finditer(r"\[\[([^\]|#]+)", txt):
            destino = m.group(1).strip().split("/")[-1]
            enlazados.add(norm(destino))
            if not any(norm(d.name) == norm(destino) for d in mods):
                rotos.append((cert.stem, destino))
    huerfanos = [d.name for d in mods if norm(d.name) not in enlazados]
    rep.h(f"Modulos que ninguna certificacion enlaza ({len(huerfanos)})")
    for h in huerfanos or ["Ninguno."]:
        rep.add(f"- {h}")
    if rotos:
        rep.h(f"Enlaces de certificaciones que no apuntan a un modulo ({len(rotos)})")
        for cert, dest in rotos:
            rep.add(f"- {cert}: [[{dest}]]")

    # nombres duplicados en el vault
    dup = {k: vs for k, vs in mapa_de_nombres(v).items() if len(vs) > 1}
    rep.h(f"Nombres de nota repetidos ({len(dup)})")
    for k, vs in sorted(dup.items()):
        rep.add(f"- {k}: " + " | ".join(rel(v, p) for p in vs))
    if not dup:
        rep.add("- Ninguno.")

    # notas dentro de modulos con propiedades que no calzan con su carpeta, o sin numero
    incons, sin_num = [], []
    for mod_dir in mods:
        for sec_dir in subcarpetas(mod_dir):
            for f in sorted(sec_dir.glob("*.md")):
                if not visible(f):
                    continue
                props, _ = leer_props(f)
                if props:
                    pm, ps = props.get("modulo"), props.get("seccion")
                    if pm and norm(pm) != norm(mod_dir.name):
                        incons.append(f"{rel(v, f)}: modulo='{pm}' pero esta en '{mod_dir.name}'")
                    if ps and norm(ps) != norm(sec_dir.name):
                        incons.append(f"{rel(v, f)}: seccion='{ps}' pero esta en '{sec_dir.name}'")
                if num_y_titulo(f.stem)[0] is None:
                    sin_num.append(rel(v, f))
    rep.h(f"Propiedades que no calzan con la carpeta ({len(incons)})")
    for i in incons or ["Ninguna."]:
        rep.add(f"- {i}")
    rep.h(f"Notas dentro de secciones sin numero en el nombre ({len(sin_num)})")
    for s in sin_num or ["Ninguna."]:
        rep.add(f"- {s}")
    return rep


# ---------------------------------------------------------------- main

REPORTE = SISTEMA + "/documentos/reporte.md"


def guardar_reporte(v: Path, rep: Reporte):
    destino = v / REPORTE
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(rep.texto(), encoding="utf-8")


def encontrar_vault(ruta):
    """Si no se pasa --vault, sube desde donde esta el script hasta la carpeta que contiene _sistema/."""
    if ruta:
        return Path(ruta).expanduser().resolve()
    padres = list(Path(__file__).resolve().parents)
    for p in padres:
        if (p / SISTEMA).is_dir() and (p / MODULOS).is_dir():
            return p
    for p in padres:
        if (p / SISTEMA).is_dir():
            return p
    sys.exit("No pude encontrar el vault. Usa --vault /ruta/al/vault")


def main():
    ap = argparse.ArgumentParser(description="Ordena notas de estudio de Obsidian y genera roadmaps.")
    ap.add_argument("comando", choices=["ordenar", "roadmap", "revisar", "todo"])
    ap.add_argument("modulo", nargs="?", help="solo para roadmap: nombre del modulo (si falta, todos)")
    ap.add_argument("--aplicar", action="store_true", help="ejecutar de verdad (por defecto solo simula)")
    ap.add_argument("--vault", help="ruta del vault (por defecto, la carpeta que contiene _sistema/)")
    args = ap.parse_args()

    v = encontrar_vault(args.vault)
    if not v.is_dir():
        sys.exit(f"El vault no existe: {v}")

    if args.comando == "ordenar":
        rep = ordenar(v, args.aplicar)
    elif args.comando == "roadmap":
        rep = roadmap(v, args.modulo, args.aplicar)
    elif args.comando == "revisar":
        rep = revisar(v)
    else:
        rep = ordenar(v, args.aplicar)
        if args.aplicar:
            rep2 = roadmap(v, None, True)
            rep.lineas += rep2.lineas
        else:
            rep.h("Roadmap")
            rep.add("- Se regenerara el indice de todos los modulos al aplicar.")

    print(rep.texto())
    guardar_reporte(v, rep)
    print(f"(Reporte guardado en {REPORTE})")


if __name__ == "__main__":
    main()

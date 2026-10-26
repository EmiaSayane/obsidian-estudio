<%*
// Plantilla de nota de estudio (Templater). Guardar en _sistema/plantillas/nota-estudio.md
// Todos los menus filtran mientras escribes. Los nombres salen de las carpetas y tags reales del vault.

const norm = (s) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();

// Parecido entre 0 y 1 (distancia de Levenshtein)
const parecido = (a, b) => {
  if (a === b) return 1;
  if (!a.length || !b.length) return 0;
  let fila = Array.from({ length: b.length + 1 }, (_, j) => j);
  for (let i = 1; i <= a.length; i++) {
    const nueva = [i];
    for (let j = 1; j <= b.length; j++) {
      nueva[j] = Math.min(fila[j] + 1, nueva[j - 1] + 1, fila[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
    }
    fila = nueva;
  }
  return 1 - fila[b.length] / Math.max(a.length, b.length);
};

const listarCarpetas = (ruta) => {
  const base = app.vault.getAbstractFileByPath(ruta);
  if (!base || !base.children) return [];
  return base.children.filter((f) => f.children).map((f) => f.name).sort();
};

const numeroDe = (nombre) => {
  const m = nombre.match(/^(\d+)\.\s+/);
  return m ? parseInt(m[1], 10) : null;
};

// ---- Tipo
const tipos = ["theory", "interactive", "lab"];
const tipo = (await tp.system.suggester(tipos, tipos, false, "Tipo de nota")) || "theory";

// ---- Modulo: menu con los existentes, mas la opcion de escribir uno nuevo
const modulos = listarCarpetas("modulos");
let modulo = await tp.system.suggester(
  [...modulos, "otro (escribirlo)"],
  [...modulos, "__otro__"],
  false,
  "Modulo"
);
let moduloNuevo = false;
if (modulo === "__otro__") {
  const escrito = ((await tp.system.prompt("Nombre del modulo nuevo (como aparece en la plataforma)")) || "").trim();
  const igual = modulos.find((m) => norm(m) === norm(escrito));
  if (igual) {
    modulo = igual; // ya existia, solo estaba escrito distinto
  } else {
    const cercanos = modulos.filter((m) => parecido(norm(m), norm(escrito)) >= 0.8);
    if (escrito && cercanos.length > 0) {
      const elegido = await tp.system.suggester(
        [...cercanos.map((m) => "Usar el existente: " + m), "No, es un modulo distinto: " + escrito],
        [...cercanos, "__nuevo__"],
        false,
        "Se parece a un modulo que ya existe"
      );
      if (elegido && elegido !== "__nuevo__") {
        modulo = elegido;
      } else {
        modulo = escrito;
        moduloNuevo = true;
      }
    } else {
      modulo = escrito;
      moduloNuevo = true;
    }
  }
}
modulo = modulo || "";

// ---- Seccion: menu con las existentes de ese modulo, mas la opcion de crear una nueva
const secciones = listarCarpetas("modulos/" + modulo);
let seccion = await tp.system.suggester(
  [...secciones, "nueva seccion (escribirla)"],
  [...secciones, "__nueva__"],
  false,
  "Seccion"
);
if (seccion === "__nueva__") {
  const siguiente = Math.max(0, ...secciones.map((s) => numeroDe(s) || 0)) + 1;
  let propuesta = String(siguiente).padStart(2, "0") + ". ";
  let escrita = "";
  let partes = null;
  while (!partes) {
    escrita = ((await tp.system.prompt("Seccion nueva, formato 'NN. Nombre' (vacio para dejarla sin seccion)", propuesta)) || "").trim();
    if (!escrita || escrita === propuesta.trim()) { escrita = ""; break; }
    partes = escrita.match(/^(\d+)\.\s+(.+)$/);
    propuesta = escrita;
  }
  seccion = escrita;
  if (partes) {
    const num = parseInt(partes[1], 10);
    const choques = secciones.filter(
      (s) => numeroDe(s) === num || norm(s.replace(/^\d+\.\s+/, "")) === norm(partes[2])
    );
    if (choques.length > 0) {
      const elegido = await tp.system.suggester(
        [...choques.map((s) => "Usar la existente: " + s), "Mantener lo que escribi (el script la va a rechazar si choca)"],
        [...choques, "__mantener__"],
        false,
        "Ya hay una seccion con ese numero o nombre"
      );
      if (elegido && elegido !== "__mantener__") seccion = elegido;
    }
  }
}
seccion = seccion || "";

// ---- Tags: se eligen entre los que ya existen en el vault (filtra al escribir) o se escribe uno nuevo
let existentes = [];
try {
  existentes = Object.keys(app.metadataCache.getTags()).map((t) => t.replace(/^#/, "")).sort();
} catch (e) {
  existentes = [];
}
const tags = [];
while (true) {
  const disponibles = existentes.filter((t) => !tags.includes(t));
  const op = await tp.system.suggester(
    ["Listo (terminar tags)", "Escribir un tag nuevo...", ...disponibles],
    ["__fin__", "__nuevo__", ...disponibles],
    false,
    "Tags elegidos: " + (tags.length ? tags.join(", ") : "ninguno")
  );
  if (!op || op === "__fin__") break;
  if (op === "__nuevo__") {
    const t = ((await tp.system.prompt("Tag nuevo")) || "").trim().toLowerCase().replace(/\s+/g, "-").replace(/^#/, "");
    if (t && !tags.includes(t)) tags.push(t);
  } else {
    tags.push(op);
  }
}

// ---- Resultado
tR += "---\n";
tR += "tipo: " + tipo + "\n";
tR += "fecha: " + tp.date.now("YYYY-MM-DD HH:mm") + "\n";
tR += "modulo: " + modulo + "\n";
if (moduloNuevo) {
  tR += "modulo_nuevo: true\n";
}
tR += "seccion: " + seccion + "\n";
tR += "tags: [" + tags.join(", ") + "]\n";
tR += "---\n\n";
if (tipo === "lab") {
  tR += "Teoria relacionada: [[]]\n\n";
}
%>

#!/usr/bin/env python3
"""Empaqueta una version de Jaime0 para jaime0-update.

Uso:
  scripts/empaquetar-actualizacion.py --clave ~/.jaime0/firma-actualizaciones.pem
      Crea dist/VERSION/ con manifiesto.json, manifiesto.json.sig, jaime0-VERSION.tar.gz
      y notas.md, listos para subir a una publicacion de GitHub con la etiqueta vVERSION.
  scripts/empaquetar-actualizacion.py --manifiesto-iso RUTA
      Solo escribe el manifiesto (sin firma) que la ISO instala como version de partida.
      Lo llama auto/build antes de compilar.

La version sale de usr/share/jaime0/version y las notas de publicaciones/VERSION.toml.
Las reglas (que rutas se gestionan, componentes, orden de versiones) son las del propio
jaime0-update, que se carga como modulo: hay una sola fuente.
"""
import argparse
import datetime
import hashlib
import importlib.machinery
import importlib.util
import io
import json
import os
import subprocess
import sys
import tarfile
import tomllib

sys.dont_write_bytecode = True

RAIZ_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INCLUDES = "config/includes.chroot_after_packages"
ACTUALIZADOR = os.path.join(RAIZ_REPO, INCLUDES, "usr/local/bin/jaime0-update")

# Dentro de las rutas gestionadas, lo que solo existe en el medio vivo o se genera al compilar.
# Fuera de PREFIJOS_PERMITIDOS (de jaime0-update) quedan a proposito: el instalador y el
# sistema en vivo (etc/calamares, etc/live, usr/lib/live, usr/local/sbin, usr/share/calamares,
# usr/share/applications/instalar-sistema.desktop, la traduccion de Calamares), el
# repositorio y la clave de Brave (etc/apt/sources.list.d, usr/share/keyrings: confianza de
# apt en terceros), greetd (un error deja sin acceso al sistema) y lo de NVIDIA del nucleo
# (etc/modprobe.d, etc/udev/rules.d: necesitan initramfs y reinicio). Ver
# docs/actualizaciones.md, "Que rutas gestiona".
EXCLUIDOS = {
    "usr/local/bin/instalar-sistema",   # Lo borra el instalador (hypr-limpiar-vivo)
    "usr/local/bin/setxkbmap",          # Idem
    "usr/share/jaime0/manifiesto.json",  # Lo genera este script
}
# Manifiestos que solo entiende un jaime0-update de esta version o posterior. Subelo (o
# ponlo en las notas: [requisitos] actualizador_minimo) solo cuando un actualizador anterior
# instalaria mal la version; no hace falta cada vez que cambia VERSION_ACTUALIZADOR.
ACTUALIZADOR_MINIMO = 2


def cargar_actualizador():
    os.environ.pop("JAIME0_RAIZ", None)
    cargador = importlib.machinery.SourceFileLoader("jaime0_update", ACTUALIZADOR)
    spec = importlib.util.spec_from_loader("jaime0_update", cargador)
    modulo = importlib.util.module_from_spec(spec)
    cargador.exec_module(modulo)
    return modulo


J = cargar_actualizador()


def gestionado(rel):
    # El bytecode (__pycache__, .pyc) lo genera cada equipo: nunca va en una publicacion.
    return (rel.startswith(J.PREFIJOS_PERMITIDOS) and rel not in EXCLUIDOS and not rel.endswith(J.NUEVO)
            and "__pycache__" not in rel.split("/") and not rel.endswith((".pyc", ".pyo")))


def modo_de(rel, datos):
    # Los modulos del servicio se importan, no se ejecutan: 644 aunque empiecen por #!.
    if rel.startswith("usr/local/lib/jaime0/"):
        return "644"
    if rel.startswith(("usr/local/bin/", "usr/local/libexec/")) or datos.startswith(b"#!"):
        return "755"
    return "644"


def archivos_actuales():
    base = os.path.join(RAIZ_REPO, INCLUDES)
    resultado = {}
    for carpeta, _, nombres in os.walk(base):
        for nombre in nombres:
            completo = os.path.join(carpeta, nombre)
            rel = os.path.relpath(completo, base).replace(os.sep, "/")
            if not gestionado(rel) or os.path.islink(completo):
                continue
            with open(completo, "rb") as f:
                datos = f.read()
            if b"\r\n" in datos and not rel.endswith((".png", ".jpg", ".qm", ".mo")):
                sys.exit(f"ERROR: {rel} tiene finales de linea CRLF")
            resultado[rel] = datos
    return resultado


def git(*args):
    return subprocess.run(["git", "-C", RAIZ_REPO] + list(args), capture_output=True, check=True).stdout


def versiones_anteriores(actual):
    """Etiquetas vX.Y.Z[-beta.N|-exp.N] anteriores a la actual, de la mas vieja a la mas nueva."""
    try:
        etiquetas = git("tag", "--list", "v*").decode().split()
    except (OSError, subprocess.CalledProcessError):
        print("Aviso: sin git, el manifiesto no lleva historico de versiones.", file=sys.stderr)
        return []
    limite = J.clave_version(actual)
    validas = [e for e in etiquetas if J.clave_version(e) and J.clave_version(e) < limite]
    return sorted(validas, key=J.clave_version)


def huellas_en(etiqueta):
    salida = git("ls-tree", "-r", "-z", etiqueta, "--", INCLUDES + "/")
    huellas = {}
    for entrada in salida.split(b"\0"):
        if not entrada:
            continue
        cabecera, camino = entrada.split(b"\t", 1)
        if cabecera.split()[1] != b"blob":
            continue
        rel = camino.decode()[len(INCLUDES) + 1:]
        if gestionado(rel):
            huellas[rel] = hashlib.sha256(git("cat-file", "blob", cabecera.split()[2].decode())).hexdigest()
    return huellas


def construir_carga(archivos, version):
    """tar.gz reproducible: orden fijo, fecha fija y dueno root."""
    fecha = int(os.environ.get("SOURCE_DATE_EPOCH", "0"))
    crudo = io.BytesIO()
    with tarfile.open(fileobj=crudo, mode="w", format=tarfile.PAX_FORMAT) as tar:
        for rel in sorted(archivos):
            datos = archivos[rel]
            info = tarfile.TarInfo(rel)
            info.size = len(datos)
            info.mtime = fecha
            info.mode = int(modo_de(rel, datos), 8)
            info.uid = info.gid = 0
            info.uname = info.gname = "root"
            tar.addfile(info, io.BytesIO(datos))
    import gzip
    comprimido = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=comprimido, mtime=fecha, compresslevel=9) as gz:
        gz.write(crudo.getvalue())
    return comprimido.getvalue()


def reinicio_necesario(cambiados):
    if any(r.startswith(("etc/default/grub.d/", "etc/systemd/", "usr/share/grub/")) for r in cambiados):
        return "sistema"
    if any(r.startswith(("etc/skel/", "usr/share/backgrounds/", "usr/lib/systemd/user/", "etc/fonts/"))
           for r in cambiados):
        return "sesion"
    return "ninguno"


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--clave", help="clave privada Ed25519 (nunca dentro del repositorio)")
    p.add_argument("--salida", default=os.path.join(RAIZ_REPO, "dist"))
    p.add_argument("--manifiesto-iso", metavar="RUTA")
    op = p.parse_args()

    with open(os.path.join(RAIZ_REPO, INCLUDES, "usr/share/jaime0/version"), encoding="utf-8") as f:
        version = f.read().strip()
    if not J.clave_version(version):
        sys.exit(f"ERROR: version no valida: {version!r}")

    notas = {}
    ruta_notas = os.path.join(RAIZ_REPO, "publicaciones", f"{version}.toml")
    if os.path.exists(ruta_notas):
        with open(ruta_notas, "rb") as f:
            notas = tomllib.load(f)
    elif not op.manifiesto_iso:
        sys.exit(f"ERROR: faltan las notas de la version: publicaciones/{version}.toml")

    archivos = archivos_actuales()
    anteriores = versiones_anteriores(version)
    historico = {}
    ultima = {}
    for etiqueta in anteriores:
        ultima = huellas_en(etiqueta)
        for rel, huella in ultima.items():
            historico.setdefault(rel, [])
            if huella not in historico[rel]:
                historico[rel].append(huella)

    actuales = {rel: hashlib.sha256(d).hexdigest() for rel, d in archivos.items()}
    cambiados = sorted(r for r in set(actuales) | set(ultima) if actuales.get(r) != ultima.get(r))
    carga = construir_carga(archivos, version)
    nombre_carga = f"jaime0-{version}.tar.gz"
    requisitos = dict(notas.get("requisitos", {}))
    requisitos.setdefault("actualizador_minimo", ACTUALIZADOR_MINIMO)
    entradas = {rel: {"sha256": actuales[rel], "modo": modo_de(rel, archivos[rel]),
                      "componente": J.componente_de(rel)} for rel in sorted(archivos)}

    manifiesto = {
        "formato": J.FORMATO_MANIFIESTO,
        "version": version,
        "canal": J.canal_de(version),
        "fecha": notas.get("fecha") or datetime.date.today().isoformat(),
        "desde": anteriores[-1].lstrip("v") if anteriores else None,
        "cambios": notas.get("cambios", []),
        "problemas_conocidos": notas.get("problemas_conocidos", []),
        "requisitos": requisitos,
        "compatibilidad": notas.get("compatibilidad", {}),
        "paquetes": notas.get("paquetes", []),
        # Los que cambian respecto a la version anterior (para las notas)...
        "componentes": sorted({J.componente_de(r) for r in cambiados}),
        # ...y la huella de conjunto de todos: asi se sabe si un componente cambio.
        "huellas_componentes": J.huellas_componentes(entradas),
        "reinicio": reinicio_necesario(cambiados),
        "carga": {"nombre": nombre_carga, "sha256": hashlib.sha256(carga).hexdigest(), "tamano": len(carga)},
        "archivos": entradas,
        "historico": {rel: h for rel, h in sorted(historico.items())},
    }
    J.validar_manifiesto(json.loads(json.dumps(manifiesto)), version)
    texto = (json.dumps(manifiesto, ensure_ascii=False, indent=1, sort_keys=True) + "\n").encode("utf-8")

    if op.manifiesto_iso:
        os.makedirs(os.path.dirname(os.path.abspath(op.manifiesto_iso)), exist_ok=True)
        with open(op.manifiesto_iso, "wb") as f:
            f.write(texto)
        print(f"Manifiesto {version}: {len(archivos)} archivos -> {op.manifiesto_iso}")
        return

    if not op.clave:
        sys.exit("ERROR: falta --clave")
    clave = os.path.realpath(os.path.expanduser(op.clave))
    clave_cmp = os.path.normcase(clave)
    repo_cmp = os.path.normcase(os.path.realpath(RAIZ_REPO))
    # Ni en el repositorio ni en una carpeta que se sincroniza con la nube.
    if clave_cmp.startswith(repo_cmp + os.sep) or "onedrive" in clave_cmp:
        sys.exit("ERROR: la clave privada no puede estar en el repositorio ni en OneDrive")
    destino = os.path.join(op.salida, version)
    os.makedirs(destino, exist_ok=True)
    for nombre, datos in (("manifiesto.json", texto), (nombre_carga, carga)):
        with open(os.path.join(destino, nombre), "wb") as f:
            f.write(datos)
    firma = os.path.join(destino, "manifiesto.json.sig")
    subprocess.run(["openssl", "pkeyutl", "-sign", "-inkey", clave, "-rawin",
                    "-in", os.path.join(destino, "manifiesto.json"), "-out", firma], check=True)
    publica = os.path.join(RAIZ_REPO, INCLUDES, "usr/share/jaime0/firma-actualizaciones.pem")
    subprocess.run(["openssl", "pkeyutl", "-verify", "-pubin", "-inkey", publica, "-rawin",
                    "-in", os.path.join(destino, "manifiesto.json"), "-sigfile", firma],
                   check=True, stdout=subprocess.DEVNULL)

    lineas = [f"**Canal:** {manifiesto['canal']} · **Componentes:** {', '.join(manifiesto['componentes']) or 'ninguno'}"
              f" · **Reinicio:** {manifiesto['reinicio']}", "", "### Cambios", ""]
    lineas += [f"- {c}" for c in manifiesto["cambios"]]
    if manifiesto["problemas_conocidos"]:
        lineas += ["", "### Problemas conocidos", ""] + [f"- {c}" for c in manifiesto["problemas_conocidos"]]
    lineas += ["", "### Cómo actualizar", "", "```bash", "jaime0-update", "```", "",
               "Los archivos `manifiesto.json`, `manifiesto.json.sig` y `" + nombre_carga +
               "` los usa `jaime0-update`; no hace falta descargarlos a mano."]
    with open(os.path.join(destino, "notas.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lineas) + "\n")
    print(f"Publicacion {version} ({manifiesto['canal']}) en {destino}")
    print(f"  {len(archivos)} archivos, {len(cambiados)} cambiados desde {manifiesto['desde'] or 'el principio'}, "
          f"carga {len(carga) / 1024:.0f} KiB, firma comprobada")
    prerelease = "" if manifiesto["canal"] == "stable" else " --prerelease"
    print(f"  Subir: gh release create v{version}{prerelease} --title 'Jaime0 {version}' "
          f"--notes-file {destino}/notas.md {destino}/manifiesto.json {destino}/manifiesto.json.sig "
          f"{destino}/{nombre_carga}")


if __name__ == "__main__":
    main()

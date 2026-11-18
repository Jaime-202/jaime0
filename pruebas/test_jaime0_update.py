#!/usr/bin/env python3
"""Pruebas de jaime0-update sobre un sistema de mentira (JAIME0_RAIZ), con publicaciones
locales file:// firmadas de verdad con una clave Ed25519 de usar y tirar.

    python3 -m unittest discover -s pruebas -v

Necesita python3 >= 3.11 y openssl 3. No necesita root ni red.
"""
import hashlib
import importlib.machinery
import importlib.util
import io
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
import unittest.mock

sys.dont_write_bytecode = True
REPO = pathlib.Path(__file__).resolve().parent.parent
PROGRAMA = REPO / "config/includes.chroot_after_packages/usr/local/bin/jaime0-update"


def cargar():
    cargador = importlib.machinery.SourceFileLoader("jaime0_update_pruebas", str(PROGRAMA))
    spec = importlib.util.spec_from_loader(cargador.name, cargador)
    modulo = importlib.util.module_from_spec(spec)
    cargador.exec_module(modulo)
    return modulo


J = cargar()


def sha(d):
    return hashlib.sha256(d).hexdigest()


class Escenario:
    """Raiz falsa, carpeta personal y un 'GitHub' local con publicaciones firmadas."""

    def __init__(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="jaime0-prueba-"))
        self.raiz = self.tmp / "raiz"
        self.casa = self.tmp / "casa"
        self.origen = self.tmp / "origen"
        for d in (self.raiz, self.casa, self.origen):
            d.mkdir()
        self.clave = self.tmp / "privada.pem"
        subprocess.run(["openssl", "genpkey", "-algorithm", "ed25519", "-out", str(self.clave)],
                       check=True, capture_output=True)
        publica = self.raiz / "usr/share/jaime0/firma-actualizaciones.pem"
        publica.parent.mkdir(parents=True)
        subprocess.run(["openssl", "pkey", "-in", str(self.clave), "-pubout", "-out", str(publica)],
                       check=True, capture_output=True)
        self.publicaciones = []
        self.historico = {}
        self.escribir_conf("stable")

    def escribir_conf(self, canal):
        conf = self.raiz / "etc/jaime0/update.conf"
        conf.parent.mkdir(parents=True, exist_ok=True)
        api = (self.origen / "releases.json").as_uri()
        conf.write_bytes((f"canal={canal}\napi={api}\n").encode())

    @staticmethod
    def empaquetar(archivos):
        carga = io.BytesIO()
        with tarfile.open(fileobj=carga, mode="w:gz") as tar:
            for rel, datos in sorted(archivos.items()):
                info = tarfile.TarInfo(rel)
                info.size = len(datos)
                tar.addfile(info, io.BytesIO(datos))
        return carga.getvalue()

    def manifiesto(self, version, archivos, historico, requisitos=None):
        carga = self.empaquetar(archivos)
        entradas = {r: {"sha256": sha(d), "modo": "755" if r.startswith(("usr/local/bin/", "usr/local/libexec/")) else "644",
                        "componente": J.componente_de(r)} for r, d in archivos.items()}
        m = {
            "formato": 1, "version": version, "canal": J.canal_de(version), "fecha": "2026-11-11",
            "cambios": [f"Cambios de {version}"], "problemas_conocidos": [],
            "requisitos": requisitos if requisitos is not None else {"version_minima": "0.1.0"},
            "compatibilidad": {}, "paquetes": [],
            "componentes": sorted({J.componente_de(r) for r in archivos}), "reinicio": "sesion",
            "huellas_componentes": J.huellas_componentes(entradas),
            "carga": {"nombre": f"jaime0-{version}.tar.gz", "sha256": sha(carga), "tamano": len(carga)},
            "archivos": entradas,
            "historico": {r: list(h) for r, h in historico.items()},
        }
        return m, carga

    def publicar(self, version, archivos, prerelease=None, alterar=None, requisitos=None, antes_de_firmar=None,
                 clave=None):
        """Publica una version. alterar(manifiesto_bytes, carga) -> (manifiesto_bytes, carga)
        permite falsificar algo DESPUES de firmar; antes_de_firmar(manifiesto, carga) ->
        (manifiesto, carga), preparar una publicacion mala pero bien firmada; clave, firmar
        con otra clave."""
        m, carga = self.manifiesto(version, archivos, self.historico, requisitos)
        if antes_de_firmar:
            m, carga = antes_de_firmar(m, carga)
        texto = json.dumps(m, indent=1, sort_keys=True).encode()
        d = self.origen / version
        d.mkdir()
        (d / "manifiesto.json").write_bytes(texto)
        subprocess.run(["openssl", "pkeyutl", "-sign", "-inkey", str(clave or self.clave), "-rawin",
                        "-in", str(d / "manifiesto.json"), "-out", str(d / "manifiesto.json.sig")],
                       check=True, capture_output=True)
        if alterar:
            texto, carga = alterar(texto, carga)
            (d / "manifiesto.json").write_bytes(texto)
        (d / m["carga"]["nombre"]).write_bytes(carga)
        nombres = ["manifiesto.json", "manifiesto.json.sig", m["carga"]["nombre"]]
        self.publicaciones.append({
            "tag_name": "v" + version, "name": version, "draft": False,
            "prerelease": J.canal_de(version) != "stable",
            "assets": [{"name": n, "browser_download_url": (d / n).as_uri()} for n in nombres],
        })
        (self.origen / "releases.json").write_bytes((json.dumps(self.publicaciones)).encode())
        for r, datos in archivos.items():
            self.historico.setdefault(r, [])
            if sha(datos) not in self.historico[r]:
                self.historico[r].append(sha(datos))
        return m

    def instalar_iso(self, version, archivos):
        """Lo que deja la ISO: archivos, version, manifiesto y la carpeta del usuario."""
        m, _ = self.manifiesto(version, archivos, {})
        for rel, datos in archivos.items():
            destino = self.raiz / rel
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_bytes(datos)
            if rel.startswith("etc/skel/"):
                casa = self.casa / rel[len("etc/skel/"):]
                casa.parent.mkdir(parents=True, exist_ok=True)
                casa.write_bytes(datos)
        (self.raiz / "usr/share/jaime0/version").write_bytes((version + "\n").encode())
        (self.raiz / "usr/share/jaime0/manifiesto.json").write_bytes(json.dumps(m).encode())
        (self.raiz / "var/lib/jaime0").mkdir(parents=True)
        (self.raiz / "usr/lib").mkdir(parents=True, exist_ok=True)
        (self.raiz / "usr/lib/os-release").write_bytes(
            f'NAME="ZYRON"\nID=jaime0\nVERSION="{version}"\nVERSION_ID={version}\n'.encode())
        (self.raiz / "var/lib/jaime0/manifiesto-instalacion.json").write_bytes(json.dumps(m).encode())
        for r, datos in archivos.items():
            self.historico.setdefault(r, []).append(sha(datos))

    def ejecutar(self, *args, entorno=None):
        env = dict(os.environ)
        env.update({"JAIME0_RAIZ": str(self.raiz), "HOME": str(self.casa), "NO_COLOR": "1",
                    "PYTHONIOENCODING": "utf-8",
                    "PYTHONDONTWRITEBYTECODE": "1"})
        env.pop("XDG_STATE_HOME", None)
        env.update(entorno or {})
        r = subprocess.run([sys.executable, str(PROGRAMA)] + list(args), env=env,
                           capture_output=True, text=True, encoding="utf-8", stdin=subprocess.DEVNULL)
        self.ultima_salida = r.stdout
        return r.returncode, r.stdout + r.stderr

    def json(self, *args, entorno=None):
        """Ejecuta una orden --json: (codigo, documento). La salida estandar debe ser UNA linea."""
        rc, todo = self.ejecutar(*args, entorno=entorno)
        lineas = self.ultima_salida.splitlines()
        assert len(lineas) == 1, f"se esperaba una linea JSON y salio: {todo!r}"
        return rc, json.loads(lineas[0])

    def foto(self):
        """Contenido de todo lo que el actualizador podria tocar (sistema y carpeta personal)."""
        r = {}
        for base in (self.raiz / "etc", self.raiz / "usr", self.casa / ".config"):
            for p in base.rglob("*"):
                if p.is_file():
                    r[str(p.relative_to(self.tmp))] = p.read_bytes()
        return r

    def leer(self, ruta):
        return (self.raiz / ruta).read_bytes() if not ruta.startswith("~/") else (self.casa / ruta[2:]).read_bytes()

    def existe(self, ruta):
        return (self.raiz / ruta).exists() if not ruta.startswith("~/") else (self.casa / ruta[2:]).exists()

    def limpiar(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


BASE = {
    "etc/skel/.config/hypr/hyprland.lua": b"-- hypr v1\n",
    "etc/skel/.config/waybar/style.css": b"/* waybar v1 */\n",
    "etc/skel/.config/kitty/kitty.conf": b"# kitty v1\n",
    "etc/skel/.config/rofi/viejo.rasi": b"/* se retira */\n",
    "etc/skel/.config/dunst/dunstrc": b"# dunst v1\n",
    "etc/skel/.config/btop/btop.conf": b"# btop v1\n",
    "usr/local/bin/captura": b"#!/bin/sh\necho v1\n",
    "usr/local/bin/menu-energia": b"#!/bin/sh\necho v1\n",
    "usr/local/bin/tiempo-waybar": b"#!/bin/sh\necho se retira\n",
    "usr/local/bin/jaime0-update": b"#!/usr/bin/env python3\n# v1\n",
    "usr/share/jaime0/firma-actualizaciones.pem": None,  # se rellena con la real
    "usr/share/jaime0/version": b"0.2.0\n",
    "etc/jaime0/update.conf": None,
}


def base_real(esc):
    archivos = dict(BASE)
    archivos["usr/share/jaime0/firma-actualizaciones.pem"] = esc.leer("usr/share/jaime0/firma-actualizaciones.pem")
    archivos["etc/jaime0/update.conf"] = esc.leer("etc/jaime0/update.conf")
    return archivos


def siguiente(base, version):
    nueva = dict(base)
    nueva["etc/skel/.config/hypr/hyprland.lua"] = b"-- hypr v2 verde\n"
    nueva["etc/skel/.config/waybar/style.css"] = b"/* waybar v2 */\n"
    nueva["etc/skel/.config/kitty/kitty.conf"] = b"# kitty v2\n"
    nueva["etc/skel/.config/fastfetch/config.jsonc"] = b"{}\n"
    nueva["usr/local/bin/captura"] = b"#!/bin/sh\necho v2\n"
    nueva["usr/local/bin/menu-energia"] = b"#!/bin/sh\necho v2\n"
    nueva["usr/share/jaime0/version"] = (version + "\n").encode()
    del nueva["etc/skel/.config/rofi/viejo.rasi"]
    del nueva["usr/local/bin/tiempo-waybar"]
    return nueva


class Versiones(unittest.TestCase):
    def test_orden(self):
        orden = ["0.1.2", "0.2.0-exp.1", "0.2.0-beta.1", "0.2.0-beta.2", "0.2.0", "0.2.1", "0.10.0"]
        self.assertEqual(sorted(orden, key=J.clave_version), orden)

    def test_canales(self):
        self.assertTrue(J.admitida_en_canal("0.2.0", "stable"))
        self.assertFalse(J.admitida_en_canal("0.2.0-beta.1", "stable"))
        self.assertFalse(J.admitida_en_canal("0.2.0-exp.1", "beta"))
        self.assertTrue(J.admitida_en_canal("0.2.0-beta.1", "beta"))
        self.assertTrue(J.admitida_en_canal("0.2.0-exp.1", "experimental"))
        self.assertIsNone(J.clave_version("0.2"))
        self.assertIsNone(J.clave_version("0.2.0-rc.1"))

    def test_version_con_salto_de_linea(self):
        self.assertIsNone(J.clave_version("1.2.3\n"))

    def test_redireccion_a_http(self):
        """Cada salto de una redireccion debe ser HTTPS, no solo el final (hallazgo 3)."""
        manejador = J._SoloHTTPS()
        peticion = J.urllib.request.Request("https://example.org/a")
        with self.assertRaises(J.Fallo):
            manejador.redirect_request(peticion, None, 302, "Found", {}, "http://example.org/b")

    def test_rutas_peligrosas(self):
        for mala in ("../etc/passwd", "/etc/shadow", "etc/skel/../../etc/sudoers", "etc/sudoers",
                     "usr/local/bin/./x", "etc\\skel\\x", "usr/bin/sudo", ""):
            with self.assertRaises(J.Fallo, msg=mala):
                J.validar_ruta_relativa(mala)
        J.validar_ruta_relativa("etc/skel/.config/hypr/hyprland.lua")


class Actualizacion(unittest.TestCase):
    def setUp(self):
        self.e = Escenario()
        self.base = base_real(self.e)
        self.e.instalar_iso("0.2.0", self.base)

    def tearDown(self):
        self.e.limpiar()

    def test_flujo_completo(self):
        e = self.e
        # El usuario personaliza Hyprland y borra la config de dunst; el administrador
        # cambia un script del sistema y borra otro.
        (e.casa / ".config/hypr/hyprland.lua").write_bytes(b"-- MI configuracion\n")
        (e.casa / ".config/dunst/dunstrc").unlink()
        (e.raiz / "usr/local/bin/captura").write_bytes(b"#!/bin/sh\necho mio\n")
        (e.raiz / "usr/local/bin/menu-energia").unlink()
        (e.casa / ".config/rofi/viejo.rasi").write_bytes(b"/* lo toque */\n")
        nueva = siguiente(self.base, "0.2.1")
        e.publicar("0.2.1", nueva)

        rc, salida = e.ejecutar("comprobar")
        self.assertEqual(rc, 100, salida)
        self.assertIn("0.2.1", salida)

        rc, salida = e.ejecutar("--si", "--sin-paquetes")
        self.assertEqual(rc, 0, salida)
        self.assertEqual(e.leer("usr/share/jaime0/version"), b"0.2.1\n")
        # Personalizacion del usuario: intacta y la nueva al lado
        self.assertEqual(e.leer("~/.config/hypr/hyprland.lua"), b"-- MI configuracion\n")
        self.assertEqual(e.leer("~/.config/hypr/hyprland.lua.jaime0-nuevo"), b"-- hypr v2 verde\n")
        # Sin tocar por el usuario: se actualiza
        self.assertEqual(e.leer("~/.config/waybar/style.css"), b"/* waybar v2 */\n")
        self.assertEqual(e.leer("~/.config/kitty/kitty.conf"), b"# kitty v2\n")
        # Nuevo: se crea. Borrado por el usuario: no vuelve
        self.assertEqual(e.leer("~/.config/fastfetch/config.jsonc"), b"{}\n")
        self.assertTrue(e.existe("~/.config/dunst/dunstrc") is False)
        # Retirado de ZYRON pero modificado: se conserva
        self.assertEqual(e.leer("~/.config/rofi/viejo.rasi"), b"/* lo toque */\n")
        # Sistema: script cambiado por el admin = conflicto; borrado en /usr = se repone;
        # retirado y sin tocar = se elimina
        self.assertEqual(e.leer("usr/local/bin/captura"), b"#!/bin/sh\necho mio\n")
        self.assertEqual(e.leer("usr/local/bin/captura.jaime0-nuevo"), b"#!/bin/sh\necho v2\n")
        self.assertEqual(e.leer("usr/local/bin/menu-energia"), b"#!/bin/sh\necho v2\n")
        self.assertFalse(e.existe("usr/local/bin/tiempo-waybar"))
        self.assertFalse(e.existe("etc/skel/.config/rofi/viejo.rasi"))
        self.assertEqual(json.loads(e.leer("usr/share/jaime0/manifiesto.json"))["version"], "0.2.1")
        self.assertIn(b'VERSION="0.2.1"', e.leer("usr/lib/os-release"))
        self.assertIn(b'NAME="ZYRON"', e.leer("usr/lib/os-release"))
        # El canal del usuario no se pisa
        self.assertIn(b"canal=stable", e.leer("etc/jaime0/update.conf"))

        rc, salida = e.ejecutar("conflictos")
        self.assertIn("hyprland.lua", salida)
        self.assertIn("captura", salida)

        rc, salida = e.ejecutar("resolver", str(e.casa / ".config/hypr/hyprland.lua"), "--usar-nueva")
        self.assertEqual(rc, 0, salida)
        self.assertEqual(e.leer("~/.config/hypr/hyprland.lua"), b"-- hypr v2 verde\n")
        self.assertFalse(e.existe("~/.config/hypr/hyprland.lua.jaime0-nuevo"))
        rc, salida = e.ejecutar("resolver", "/usr/local/bin/captura", "--mantener")
        self.assertEqual(rc, 0, salida)
        self.assertFalse(e.existe("usr/local/bin/captura.jaime0-nuevo"))
        rc, salida = e.ejecutar("conflictos")
        self.assertIn("Ninguno", salida)

        # Segunda ejecucion: nada que hacer
        rc, salida = e.ejecutar("--si", "--sin-paquetes")
        self.assertEqual(rc, 0, salida)
        self.assertIn("al día", salida)

        # Revertir el sistema vuelve a 0.2.0 (solo archivos de ZYRON)
        rc, salida = e.ejecutar("revertir", "--si")
        self.assertEqual(rc, 0, salida)
        self.assertEqual(e.leer("usr/share/jaime0/version"), b"0.2.0\n")
        self.assertIn(b"VERSION_ID=0.2.0\n", e.leer("usr/lib/os-release"))
        self.assertEqual(e.leer("usr/local/bin/tiempo-waybar"), b"#!/bin/sh\necho se retira\n")
        self.assertEqual(e.leer("etc/skel/.config/kitty/kitty.conf"), b"# kitty v1\n")

    def test_instantaneas_snapper(self):
        e = self.e
        registro = e.tmp / "snapper.log"
        falso = e.tmp / "snapper_falso.py"
        falso.write_text(
            "import json, sys\n"
            f"r = r'{registro}'\n"
            "lineas = open(r).read().splitlines() if __import__('os').path.exists(r) else []\n"
            "open(r, 'a').write(json.dumps(sys.argv[1:]) + '\\n')\n"
            "print(41 + len(lineas))\n", encoding="utf-8")
        entorno = {"JAIME0_SNAPPER": json.dumps([sys.executable, str(falso)])}
        # Sin la configuracion "root" de snapper (sistema ext4): ni se intenta.
        e.publicar("0.2.1", siguiente(self.base, "0.2.1"))
        self.assertEqual(e.ejecutar("--si", "--sin-paquetes", entorno=entorno)[0], 0)
        self.assertFalse(registro.exists())
        # Con Btrfs y snapper: una antes y otra despues, enlazadas.
        (e.raiz / "etc/snapper/configs").mkdir(parents=True)
        (e.raiz / "etc/snapper/configs/root").write_text('SUBVOLUME="/"\n', encoding="utf-8")
        def version(numero):
            v = siguiente(self.base, numero)
            v["usr/local/bin/captura"] = f"#!/bin/sh\necho {numero}\n".encode()
            return v
        e.publicar("0.2.2", version("0.2.2"))
        rc, salida = e.ejecutar("--si", "--sin-paquetes", entorno=entorno)
        self.assertEqual(rc, 0, salida)
        llamadas = [json.loads(l) for l in registro.read_text().splitlines()]
        self.assertEqual(len(llamadas), 2)
        self.assertIn("pre", llamadas[0])
        self.assertIn("post", llamadas[1])
        self.assertEqual(llamadas[1][llamadas[1].index("--pre-number") + 1], "41")
        self.assertIn("41", salida)
        ultima = json.loads(e.leer("var/lib/jaime0/ultima.json"))
        self.assertEqual(ultima["instantaneas"], [41, 42])
        # Si snapper falla, la actualizacion sigue.
        falso.write_text("import sys\nsys.exit(1)\n", encoding="utf-8")
        e.publicar("0.2.3", version("0.2.3"))
        rc, salida = e.ejecutar("--si", "--sin-paquetes", entorno=entorno)
        self.assertEqual(rc, 0, salida)
        self.assertIn("instantánea", salida)
        self.assertEqual(e.leer("usr/share/jaime0/version"), b"0.2.3\n")

    def test_indicador_de_la_barra(self):
        e = self.e
        def barra():
            rc, salida = e.ejecutar("barra")
            self.assertEqual(rc, 0, salida)
            return json.loads(salida)
        # Sin comprobar nunca: nada que mostrar (y no usa la red).
        self.assertEqual(barra()["text"], "")
        e.publicar("0.2.1", siguiente(self.base, "0.2.1"))
        self.assertEqual(barra()["text"], "", "la barra no consulta la red por su cuenta")
        self.assertEqual(e.ejecutar("comprobar")[0], 100)
        d = barra()
        self.assertEqual(d["class"], "disponible")
        self.assertIn("0.2.1", d["tooltip"])
        # Tras actualizar desaparece solo, aunque nadie vuelva a comprobar.
        self.assertEqual(e.ejecutar("--si", "--sin-paquetes")[0], 0)
        self.assertEqual(barra()["text"], "")
        # Un estado roto no rompe la barra.
        estado = e.casa / ".local/state/jaime0/disponible.json"
        estado.write_text("{roto", encoding="utf-8")
        self.assertEqual(barra()["text"], "")
        # Al dia: comprobar deja de anunciar version (pero recuerda cuando comprobo, para
        # "estado --json"), y la barra no muestra nada.
        self.assertEqual(e.ejecutar("comprobar")[0], 0)
        guardado = json.loads(estado.read_text(encoding="utf-8"))
        self.assertIsNone(guardado["disponible"])
        self.assertNotIn("version", guardado)
        self.assertIsInstance(guardado["comprobado"], int)
        self.assertEqual(barra()["text"], "")
        # ZYRON al dia pero con correcciones de seguridad de Debian: el icono aparece.
        debian = json.dumps({"paquetes": 12, "seguridad": ["libssl3t64", "openssl"], "comprobado": "x"})
        rc, salida = e.ejecutar("comprobar", entorno={"JAIME0_PRUEBA_DEBIAN": debian})
        self.assertEqual(rc, 0, salida)
        self.assertIn("2 con correcciones de seguridad", salida)
        d = barra()
        self.assertEqual(d["class"], "seguridad")
        self.assertIn("2 actualizaciones de seguridad", d["tooltip"])
        self.assertIn("12 paquetes", d["tooltip"])
        # Solo paquetes normales pendientes: no molesta en la barra.
        debian = json.dumps({"paquetes": 5, "seguridad": [], "comprobado": "x"})
        e.ejecutar("comprobar", entorno={"JAIME0_PRUEBA_DEBIAN": debian})
        self.assertEqual(barra()["text"], "")

    def test_canales(self):
        e = self.e
        e.publicar("0.3.0-beta.1", siguiente(self.base, "0.3.0-beta.1"))
        rc, salida = e.ejecutar("comprobar")
        self.assertEqual(rc, 0, salida)  # stable no ve la beta
        rc, salida = e.ejecutar("canal", "beta", "--si")
        self.assertEqual(rc, 0, salida)
        rc, salida = e.ejecutar("comprobar")
        self.assertEqual(rc, 100, salida)
        self.assertIn("beta", salida)
        e.publicar("0.3.0-exp.1", siguiente(self.base, "0.3.0-exp.1"))
        e.publicar("0.4.0-exp.1", siguiente(self.base, "0.4.0-exp.1"))
        rc, salida = e.ejecutar("cambios")
        self.assertIn("0.3.0-beta.1", salida)  # beta no ve experimental
        self.assertNotIn("0.4.0-exp.1", salida)
        rc, salida = e.ejecutar("canal", "inventado", "--si")
        self.assertEqual(rc, 1)

    def test_firma_falsa(self):
        e = self.e

        def falsificar(texto, carga):
            m = json.loads(texto)
            m["cambios"] = ["inofensivo"]
            return json.dumps(m).encode(), carga
        e.publicar("0.2.1", siguiente(self.base, "0.2.1"), alterar=falsificar)
        antes = e.leer("etc/skel/.config/kitty/kitty.conf")
        rc, salida = e.ejecutar("--si", "--sin-paquetes")
        self.assertEqual(rc, 1)
        self.assertIn("firma", salida.lower())
        self.assertEqual(e.leer("etc/skel/.config/kitty/kitty.conf"), antes)
        self.assertEqual(e.leer("usr/share/jaime0/version"), b"0.2.0\n")

    def test_carga_alterada(self):
        e = self.e

        def cambiar_carga(texto, carga):
            return texto, carga + b"basura"
        e.publicar("0.2.1", siguiente(self.base, "0.2.1"), alterar=cambiar_carga)
        rc, salida = e.ejecutar("--si", "--sin-paquetes")
        self.assertEqual(rc, 1)
        self.assertRegex(salida, "no coincide|demasiado grande")
        self.assertEqual(e.leer("usr/share/jaime0/version"), b"0.2.0\n")

    def test_ruta_fuera_firmada(self):
        """Ni con firma valida se escribe fuera de las rutas de ZYRON."""
        e = self.e
        mala = siguiente(self.base, "0.2.1")
        mala["etc/sudoers.d/puerta"] = b"ALL ALL=(ALL) NOPASSWD: ALL\n"
        e.publicar("0.2.1", mala)
        rc, salida = e.ejecutar("--si", "--sin-paquetes")
        self.assertEqual(rc, 1)
        self.assertFalse(e.existe("etc/sudoers.d/puerta"))

    def test_historico_malicioso_firmado(self):
        """Las rutas del historico deciden borrados: tambien se validan (auditoria, hallazgo 1)."""
        e = self.e
        victima = e.raiz / "etc/shadow-victima"
        victima.write_bytes(b"secreto\n")
        e.historico["etc/shadow-victima"] = [sha(b"secreto\n")]
        e.publicar("0.2.1", siguiente(self.base, "0.2.1"))
        rc, salida = e.ejecutar("--si", "--sin-paquetes")
        self.assertEqual(rc, 1, salida)
        self.assertTrue(victima.exists())
        self.assertEqual(e.leer("usr/share/jaime0/version"), b"0.2.0\n")

    def test_diario_plantado(self):
        """Un diario manipulado no puede restaurar fuera de la carpeta personal (hallazgo 4)."""
        e = self.e
        fuera = e.tmp / "fuera.txt"
        copias = e.casa / ".local/state/jaime0/copias/20260101-000000-000000_0.2.0_0.2.1"
        (copias / "archivos").mkdir(parents=True)
        (copias / "archivos/0").write_bytes(b"malo\n")
        (copias / "diario.json").write_bytes(json.dumps({
            "estado": "completada", "alcance": "usuario", "desde": "0.2.0", "hasta": "0.2.1",
            "entradas": [{"ruta": str(fuera), "existia": True, "copia": str(copias / "archivos/0"),
                          "modo": "0o644"}]}).encode())
        rc, salida = e.ejecutar("revertir", "--usuario", "--si")
        self.assertEqual(rc, 1, salida)
        self.assertFalse(fuera.exists())

    def test_corte_y_recuperacion(self):
        e = self.e
        e.publicar("0.2.1", siguiente(self.base, "0.2.1"))
        foto = {r: e.leer(r) for r in self.base if e.existe(r)}
        rc, salida = e.ejecutar("_sistema", "0.2.1", entorno={"JAIME0_PRUEBA_CORTE": "3"})
        self.assertEqual(rc, 99, salida)  # proceso muerto a mitad
        rc, salida = e.ejecutar("estado")
        self.assertIn("interrumpida", salida)
        rc, salida = e.ejecutar("recuperar")
        self.assertEqual(rc, 0, salida)
        for r, datos in foto.items():
            self.assertEqual(e.leer(r), datos, r)
        self.assertFalse(e.existe("etc/skel/.config/fastfetch/config.jsonc"))
        # Despues se actualiza con normalidad
        rc, salida = e.ejecutar("--si", "--sin-paquetes")
        self.assertEqual(rc, 0, salida)
        self.assertEqual(e.leer("usr/share/jaime0/version"), b"0.2.1\n")

    def test_corte_recuperado_al_actualizar(self):
        """Sin pedir 'recuperar': la siguiente actualizacion deshace antes lo interrumpido."""
        e = self.e
        e.publicar("0.2.1", siguiente(self.base, "0.2.1"))
        rc, _ = e.ejecutar("_sistema", "0.2.1", entorno={"JAIME0_PRUEBA_CORTE": "5"})
        self.assertEqual(rc, 99)
        rc, salida = e.ejecutar("--si", "--sin-paquetes")
        self.assertEqual(rc, 0, salida)
        self.assertIn("interrumpida", salida)
        self.assertEqual(e.leer("usr/local/bin/captura"), b"#!/bin/sh\necho v2\n")

    def test_no_retrocede(self):
        e = self.e
        e.publicar("0.2.1", siguiente(self.base, "0.2.1"))
        self.assertEqual(e.ejecutar("--si", "--sin-paquetes")[0], 0)
        rc, salida = e.ejecutar("_sistema", "0.2.1")
        self.assertEqual(rc, 1)
        self.assertIn("no es más nueva", salida)

    def test_version_minima(self):
        e = self.e

        def exigir(texto, carga):
            return texto, carga
        nueva = siguiente(self.base, "0.5.0")
        m = e.publicar("0.5.0", nueva)
        # Se rehace con requisito alto y firma valida
        datos = json.loads((e.origen / "0.5.0/manifiesto.json").read_text())
        datos["requisitos"]["version_minima"] = "0.4.0"
        (e.origen / "0.5.0/manifiesto.json").write_bytes(json.dumps(datos).encode())
        subprocess.run(["openssl", "pkeyutl", "-sign", "-inkey", str(e.clave), "-rawin",
                        "-in", str(e.origen / "0.5.0/manifiesto.json"),
                        "-out", str(e.origen / "0.5.0/manifiesto.json.sig")], check=True)
        rc, salida = e.ejecutar("--si", "--sin-paquetes")
        self.assertEqual(rc, 1)
        self.assertIn("al menos la 0.4.0", salida)

    @unittest.skipIf(os.name == "nt", "los enlaces simbolicos necesitan privilegios en Windows")
    def test_enlace_no_se_sigue(self):
        e = self.e
        fuera = e.tmp / "fuera"
        fuera.mkdir()
        objetivo = e.casa / ".config/kitty"
        shutil.rmtree(objetivo)
        objetivo.symlink_to(fuera, target_is_directory=True)
        e.publicar("0.2.1", siguiente(self.base, "0.2.1"))
        rc, salida = e.ejecutar("--si", "--sin-paquetes")
        self.assertEqual(rc, 0, salida)
        self.assertEqual(list(fuera.iterdir()), [])


# ------------------------------------------------------------------------------------
# Version 2 del actualizador: servicio, ayudante y politica; requisitos; --json; fase visible
# ------------------------------------------------------------------------------------
SERVICIO = "usr/local/lib/jaime0/jaime0_servicio/"
AYUDANTE = "usr/local/libexec/jaime0-ufw-estado"
POLITICA = "usr/share/polkit-1/actions/es.jaime0.ufw-estado.policy"
CLAVES_ESTADO = {"ok", "version_instalada", "version_actualizador", "canal", "comprobado", "disponible", "nueva",
                 "en_curso", "ultima", "conflictos", "interrumpida", "puede_revertir", "configuracion"}
CLAVES_DISPONIBLE = {"version", "canal", "fecha", "cambios", "problemas_conocidos", "componentes", "paquetes",
                     "requisitos"}
CLAVES_GRUPO_PLAN = {"crear", "reemplazar", "conflictos", "retirar", "conservar"}
CLAVES_OPERACION = {"t", "operacion", "version", "resultado", "detalle"}


def con_servicio(base):
    v = dict(base)
    v[SERVICIO + "__init__.py"] = b"# servicio v1\n"
    v[SERVICIO + "api.py"] = b"# api v1\n"
    v[AYUDANTE] = b"#!/bin/sh\nexec ufw status verbose\n"
    v[POLITICA] = b"<policyconfig><!-- v1 --></policyconfig>\n"
    v["usr/share/jaime0/control/shell.qml"] = b"// control v1\n"
    return v


def servicio_nuevo(base, version):
    v = siguiente(base, version)
    v[SERVICIO + "api.py"] = b"# api v2\n"
    v[SERVICIO + "actualizaciones.py"] = b"# modulo nuevo\n"
    v[AYUDANTE] = b"#!/bin/sh\nexec ufw status numbered\n"
    v[POLITICA] = b"<policyconfig><!-- v2 --></policyconfig>\n"
    v["usr/share/jaime0/control/shell.qml"] = b"// control v2\n"
    return v


def systemctl_falso(e):
    """(entorno, registro): un systemctl de mentira que anota sus argumentos."""
    registro = e.tmp / "systemctl.log"
    falso = e.tmp / "systemctl_falso.py"
    falso.write_text(f"import json, sys\nopen(r'{registro}', 'a').write(json.dumps(sys.argv[1:]) + '\\n')\n",
                     encoding="utf-8")
    return {"JAIME0_SYSTEMCTL": json.dumps([sys.executable, str(falso)])}, registro


def stat_falso(pid, arranque):
    """Una linea de /proc/PID/stat con el arranque (campo 22) indicado."""
    return f"{pid} (jaime0-update) " + " ".join(["S"] + ["0"] * 18 + [str(arranque)] + ["0"] * 10) + "\n"


class Validaciones(unittest.TestCase):
    def test_rutas_nuevas_y_excluidas(self):
        for buena in (SERVICIO + "api.py", AYUDANTE, POLITICA, "usr/share/jaime0/control/shell.qml"):
            J.validar_ruta_relativa(buena)
        for mala in (SERVICIO + "__pycache__/api.cpython-313.pyc", SERVICIO + "api.pyc",
                     "usr/local/libexec/otro-ayudante", "usr/share/polkit-1/actions/org.otro.policy",
                     "etc/greetd/config.toml", "etc/calamares/settings.conf", "usr/local/sbin/hypr-limpiar-vivo",
                     "etc/apt/sources.list.d/brave-browser-release.sources", "etc/modprobe.d/jaime0-nvidia.conf",
                     "usr/share/keyrings/brave-browser-archive-keyring.gpg"):
            with self.assertRaises(J.Fallo, msg=mala):
                J.validar_ruta_relativa(mala)

    def test_componentes(self):
        self.assertEqual(J.componente_de(SERVICIO + "api.py"), "servicio")
        self.assertEqual(J.componente_de(AYUDANTE), "servicio")
        self.assertEqual(J.componente_de(POLITICA), "servicio")
        self.assertEqual(J.componente_de("usr/lib/systemd/user/jaime0-servicio.service"), "servicio")
        self.assertEqual(J.componente_de("usr/share/jaime0/control/shell.qml"), "control-center")
        self.assertEqual(J.componente_de("usr/local/bin/jaime0-control"), "control-center")
        self.assertEqual(J.componente_de("usr/local/bin/captura"), "herramientas")
        a = {SERVICIO + "api.py": {"sha256": "a" * 64}, "usr/local/bin/x": {"sha256": "b" * 64}}
        b = dict(a, **{SERVICIO + "api.py": {"sha256": "c" * 64}})
        ha, hb = J.huellas_componentes(a), J.huellas_componentes(b)
        self.assertNotEqual(ha["servicio"], hb["servicio"])
        self.assertEqual(ha["herramientas"], hb["herramientas"])

    def test_requisitos_y_huellas_en_el_manifiesto(self):
        e = Escenario()
        try:
            m, _ = e.manifiesto("0.2.1", {"usr/local/bin/x": b"x\n"}, {})
            J.validar_manifiesto(json.loads(json.dumps(m)))
            for malo in ("3", True, 0, -1, 1.5):
                m2 = json.loads(json.dumps(m))
                m2["requisitos"]["actualizador_minimo"] = malo
                with self.assertRaises(J.Fallo, msg=repr(malo)):
                    J.validar_manifiesto(m2)
            m3 = json.loads(json.dumps(m))
            m3["huellas_componentes"]["herramientas"] = "0" * 64
            with self.assertRaisesRegex(J.Fallo, "huellas de los componentes"):
                J.validar_manifiesto(m3)
            m4 = json.loads(json.dumps(m))
            del m4["huellas_componentes"]  # manifiestos de la 0.2: sin el campo, se aceptan
            J.validar_manifiesto(m4)
            m4["requisitos"]["actualizador_minimo"] = J.VERSION_ACTUALIZADOR + 1
            with self.assertRaisesRegex(J.Fallo, "a mano"):
                J.comprobar_requisitos(m4, "0.2.0")
            m4["requisitos"]["actualizador_minimo"] = J.VERSION_ACTUALIZADOR
            J.comprobar_requisitos(m4, "0.2.0")
        finally:
            e.limpiar()

    def test_version_del_actualizador(self):
        self.assertIsInstance(J.VERSION_ACTUALIZADOR, int)
        self.assertGreaterEqual(J.VERSION_ACTUALIZADOR, 2)
        self.assertEqual(J.FORMATO_MANIFIESTO, 1)


class PermisosForzados(unittest.TestCase):
    """Ayudante, politica y paquete del servicio: root:root y 755/644 tras cada operacion."""

    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="jaime0-permisos-"))
        for rel, datos in ((SERVICIO + "api.py", b"x"), (SERVICIO + "__pycache__/api.cpython-313.pyc", b"x"),
                           (AYUDANTE, b"#!/bin/sh\n"), ("usr/local/libexec/ajeno", b"#!/bin/sh\n"),
                           (POLITICA, b"<p/>"), ("usr/share/polkit-1/actions/org.ajena.policy", b"<p/>")):
            p = self.tmp / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(datos)
        self.chown, self.chmod = [], []
        self.parches = [
            unittest.mock.patch.object(J, "RAIZ", str(self.tmp)),
            unittest.mock.patch.object(J, "MODO_PRUEBA", True),
            unittest.mock.patch.object(J, "es_root", lambda: True),
            unittest.mock.patch.object(J.os, "chown", lambda c, u, g: self.chown.append((c, u, g)), create=True),
            unittest.mock.patch.object(J.os, "chmod", lambda c, m: self.chmod.append((c, m))),
        ]
        for p in self.parches:
            p.start()

    def tearDown(self):
        for p in reversed(self.parches):
            p.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def modos(self):
        return {os.path.relpath(c, self.tmp).replace(os.sep, "/"): m for c, m in self.chmod}

    def test_siempre_aunque_no_cambien(self):
        avisos = J.acciones_posteriores([])
        modos = self.modos()
        self.assertEqual(modos[AYUDANTE], 0o755)
        self.assertEqual(modos[POLITICA], 0o644)
        self.assertEqual(modos[SERVICIO + "api.py"], 0o644)
        self.assertEqual(modos["usr/local/lib/jaime0"], 0o755)
        self.assertEqual(modos[SERVICIO.rstrip("/")], 0o755)
        self.assertNotIn("usr/local/libexec/ajeno", modos)
        self.assertNotIn("usr/share/polkit-1/actions/org.ajena.policy", modos)
        self.assertEqual({(u, g) for _, u, g in self.chown}, {(0, 0)})
        self.assertEqual({os.path.relpath(c, self.tmp).replace(os.sep, "/") for c, _, _ in self.chown}, set(modos))
        self.assertNotIn("servicio", avisos)
        # Sin cambios en el paquete, el bytecode no se toca.
        self.assertTrue((self.tmp / SERVICIO / "__pycache__").exists())

    def test_paquete_cambiado_sin_bytecode_viejo(self):
        avisos = J.acciones_posteriores([SERVICIO + "api.py"])
        self.assertFalse((self.tmp / SERVICIO / "__pycache__").exists())
        self.assertIn("servicio", avisos)
        self.assertEqual(self.modos()[AYUDANTE], 0o755)

    def test_control_center_avisa(self):
        self.assertIn("servicio", J.acciones_posteriores(["usr/share/jaime0/control/shell.qml"]))


class TemasDeArranque(unittest.TestCase):
    """Tema de GRUB copiado a /boot y animacion de arranque (initramfs) tras actualizarlos."""

    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="jaime0-arranque-"))
        self.parches = [unittest.mock.patch.object(J, "RAIZ", str(self.tmp)),
                        unittest.mock.patch.object(J, "MODO_PRUEBA", True),
                        unittest.mock.patch.object(J, "asegurar_permisos", lambda: None)]
        for p in self.parches:
            p.start()

    def tearDown(self):
        for p in reversed(self.parches):
            p.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_tema_de_grub_tambien_en_boot(self):
        """Con el disco cifrado GRUB solo lee /boot: el tema se copia alli, sin restos viejos."""
        tema = self.tmp / "usr/share/grub/themes/hypr"
        tema.mkdir(parents=True)
        (tema / "theme.txt").write_text("nuevo")
        viejo = self.tmp / "boot/grub/themes/hypr"
        viejo.mkdir(parents=True)
        (viejo / "sobrante.png").write_bytes(b"x")
        self.assertIn("reinicio", J.acciones_posteriores(["usr/share/grub/themes/hypr/theme.txt"]))
        self.assertEqual((viejo / "theme.txt").read_text(), "nuevo")
        self.assertFalse((viejo / "sobrante.png").exists())

    def test_sin_boot_grub_no_crea_nada(self):
        tema = self.tmp / "usr/share/grub/themes/hypr"
        tema.mkdir(parents=True)
        (tema / "theme.txt").write_text("nuevo")
        J.acciones_posteriores(["usr/share/grub/themes/hypr/theme.txt"])
        self.assertFalse((self.tmp / "boot").exists())

    def activar(self, nuevos, actual):
        llamadas = []
        with unittest.mock.patch.object(J, "tema_de_arranque", lambda: actual),              unittest.mock.patch.object(J.subprocess, "run", lambda orden, **k: llamadas.append(orden)):
            J.acciones_posteriores([J.TEMA_ZYRON], nuevos=nuevos)
        return [o for o in llamadas if o[0] == "plymouth-set-default-theme"]

    def test_la_animacion_nueva_se_activa_si_llega_por_primera_vez(self):
        self.assertEqual(self.activar({J.TEMA_ZYRON}, "jaime0"), [["plymouth-set-default-theme", "zyron"]])

    def test_no_pisa_un_tema_elegido_despues(self):
        self.assertEqual(self.activar(set(), "jaime0"), [])          # ya existia: se eligio jaime0
        self.assertEqual(self.activar({J.TEMA_ZYRON}, "spinner"), [])  # otro tema elegido a mano

    def test_animacion_de_arranque_pide_reinicio(self):
        self.assertIn("reinicio", J.acciones_posteriores(["usr/share/plymouth/themes/zyron/zyron.script"]))
        self.assertEqual(J.componente_de("usr/share/plymouth/themes/zyron/z.png"), "temas")


class ServicioYJson(unittest.TestCase):
    def setUp(self):
        self.e = Escenario()
        self.base = con_servicio(base_real(self.e))
        self.e.instalar_iso("0.2.0", self.base)

    def tearDown(self):
        self.e.limpiar()

    def test_actualiza_servicio_ayudante_y_politica(self):
        e = self.e
        cache = e.raiz / SERVICIO / "__pycache__"
        cache.mkdir()
        (cache / "api.cpython-313.pyc").write_bytes(b"bytecode viejo")
        entorno, registro = systemctl_falso(e)
        e.publicar("0.2.1", servicio_nuevo(self.base, "0.2.1"))
        rc, salida = e.ejecutar("--si", "--sin-paquetes", entorno=entorno)
        self.assertEqual(rc, 0, salida)
        self.assertEqual(e.leer(SERVICIO + "api.py"), b"# api v2\n")
        self.assertEqual(e.leer(SERVICIO + "actualizaciones.py"), b"# modulo nuevo\n")
        self.assertEqual(e.leer(AYUDANTE), b"#!/bin/sh\nexec ufw status numbered\n")
        self.assertEqual(e.leer(POLITICA), b"<policyconfig><!-- v2 --></policyconfig>\n")
        self.assertEqual(e.leer("usr/share/jaime0/control/shell.qml"), b"// control v2\n")
        self.assertFalse(cache.exists(), "el bytecode viejo se borra")
        # La fase de usuario reinicia el servicio (sin fallar) y pide reabrir el Control Center.
        llamadas = [json.loads(l) for l in registro.read_text().splitlines()]
        self.assertEqual(llamadas, [["--user", "try-restart", "jaime0-servicio.service"]])
        self.assertIn("Control Center", salida)
        # Una segunda pasada no vuelve a reiniciar: las huellas quedaron anotadas.
        rc, salida = e.ejecutar("usuario", "--si", entorno=entorno)
        self.assertEqual(rc, 0, salida)
        self.assertEqual(len(registro.read_text().splitlines()), 1)

    def test_sin_cambios_del_servicio_no_reinicia(self):
        e = self.e
        entorno, registro = systemctl_falso(e)
        e.publicar("0.2.1", siguiente(self.base, "0.2.1"))
        rc, salida = e.ejecutar("--si", "--sin-paquetes", entorno=entorno)
        self.assertEqual(rc, 0, salida)
        self.assertFalse(registro.exists())
        self.assertNotIn("Control Center", salida)

    def test_systemctl_que_falla_no_rompe(self):
        e = self.e
        falso = e.tmp / "falla.py"
        falso.write_text("import sys\nsys.exit(1)\n", encoding="utf-8")
        e.publicar("0.2.1", servicio_nuevo(self.base, "0.2.1"))
        rc, salida = e.ejecutar("--si", "--sin-paquetes",
                                entorno={"JAIME0_SYSTEMCTL": json.dumps([sys.executable, str(falso)])})
        self.assertEqual(rc, 0, salida)
        self.assertIn("al volver a entrar", salida)

    def test_conflicto_en_el_servicio_no_se_pisa(self):
        e = self.e
        (e.raiz / SERVICIO / "api.py").write_bytes(b"# api retocada a mano\n")
        (e.casa / ".config/hypr/hyprland.lua").write_bytes(b"-- mia\n")
        e.publicar("0.2.1", servicio_nuevo(self.base, "0.2.1"))
        rc, plan = e.json("comprobar", "--json")
        self.assertEqual(rc, 100)
        self.assertIn("/" + SERVICIO + "api.py", plan["plan"]["sistema"]["conflictos"])
        self.assertIn("~/.config/hypr/hyprland.lua", plan["plan"]["usuario"]["conflictos"])
        rc, salida = e.ejecutar("--si", "--sin-paquetes")
        self.assertEqual(rc, 0, salida)
        self.assertEqual(e.leer(SERVICIO + "api.py"), b"# api retocada a mano\n")
        self.assertEqual(e.leer(SERVICIO + "api.py.jaime0-nuevo"), b"# api v2\n")
        self.assertEqual(e.leer("~/.config/hypr/hyprland.lua"), b"-- mia\n")
        rc, estado = e.json("estado", "--json")
        self.assertIn({"ruta": "/" + SERVICIO + "api.py", "ambito": "sistema"}, estado["conflictos"])
        self.assertIn({"ruta": "~/.config/hypr/hyprland.lua", "ambito": "usuario"}, estado["conflictos"])

    def test_firma_de_otra_clave(self):
        e = self.e
        otra = e.tmp / "otra.pem"
        subprocess.run(["openssl", "genpkey", "-algorithm", "ed25519", "-out", str(otra)],
                       check=True, capture_output=True)
        e.publicar("0.2.1", servicio_nuevo(self.base, "0.2.1"), clave=otra)
        antes = e.foto()
        rc, salida = e.ejecutar("--si", "--sin-paquetes")
        self.assertEqual(rc, 1, salida)
        self.assertIn("firma", salida.lower())
        self.assertEqual(e.foto(), antes)
        rc, doc = e.json("comprobar", "--json")
        self.assertEqual(rc, 1)
        self.assertEqual(doc, {"ok": False, "error": doc["error"], "nueva": False, "disponible": None, "plan": None})
        self.assertIn("firma", doc["error"].lower())

    def _carga_mala(self, version, cambiar):
        """Publicacion bien firmada cuya carga no cuadra con la lista de archivos."""
        nueva = servicio_nuevo(self.base, version)

        def preparar(m, carga):
            contenido = cambiar(dict(nueva))
            carga = Escenario.empaquetar(contenido)
            m["carga"]["sha256"], m["carga"]["tamano"] = sha(carga), len(carga)
            return m, carga
        self.e.publicar(version, nueva, antes_de_firmar=preparar)

    def test_carga_incompleta(self):
        e = self.e
        self._carga_mala("0.2.1", lambda c: {r: d for r, d in c.items() if r != SERVICIO + "api.py"})
        antes = e.foto()
        rc, salida = e.ejecutar("--si", "--sin-paquetes")
        self.assertEqual(rc, 1, salida)
        self.assertIn("exactamente los archivos", salida)
        self.assertEqual(e.foto(), antes)
        rc, salida = e.ejecutar("_sistema", "0.2.1")
        self.assertEqual(rc, 1, salida)
        self.assertEqual(e.foto(), antes)

    def test_archivo_con_huella_distinta(self):
        e = self.e
        self._carga_mala("0.2.1", lambda c: dict(c, **{AYUDANTE: b"#!/bin/sh\nrm -rf /\n"}))
        antes = e.foto()
        rc, salida = e.ejecutar("_sistema", "0.2.1")
        self.assertEqual(rc, 1, salida)
        self.assertIn("Huella incorrecta", salida)
        self.assertEqual(e.foto(), antes)

    def test_carga_cortada(self):
        e = self.e
        e.publicar("0.2.1", servicio_nuevo(self.base, "0.2.1"), alterar=lambda t, c: (t, c[:len(c) // 2]))
        antes = e.foto()
        rc, salida = e.ejecutar("--si", "--sin-paquetes")
        self.assertEqual(rc, 1, salida)
        self.assertIn("no coincide", salida)
        self.assertEqual(e.foto(), antes)

    def test_actualizador_minimo_no_cumplido(self):
        e = self.e
        exigido = J.VERSION_ACTUALIZADOR + 1
        e.publicar("0.2.1", servicio_nuevo(self.base, "0.2.1"), requisitos={"actualizador_minimo": exigido})
        antes = e.foto()
        rc, salida = e.ejecutar("--si", "--sin-paquetes")
        self.assertEqual(rc, 1, salida)
        self.assertIn(f"jaime0-update {exigido} o posterior", salida)
        self.assertIn("No se ha instalado nada", salida)
        self.assertIn("a mano", salida)
        self.assertIn("docs/actualizaciones.md", salida)
        self.assertEqual(e.foto(), antes)
        # La fase de sistema tambien lo comprueba por su cuenta.
        rc, salida = e.ejecutar("_sistema", "0.2.1")
        self.assertEqual(rc, 1, salida)
        self.assertEqual(e.foto(), antes)
        # comprobar --json: hay version nueva, pero no se puede instalar y no hay vista previa.
        rc, doc = e.json("comprobar", "--json")
        self.assertEqual(rc, 100)
        self.assertEqual(set(doc), {"ok", "error", "nueva", "disponible", "plan"})
        self.assertFalse(doc["ok"])
        self.assertTrue(doc["nueva"])
        self.assertIsNone(doc["plan"])
        self.assertIn("a mano", doc["error"])
        self.assertEqual(doc["disponible"]["requisitos"], {"actualizador_minimo": exigido})

    def test_version_minima_no_cumplida(self):
        e = self.e
        e.publicar("0.3.0", servicio_nuevo(self.base, "0.3.0"), requisitos={"version_minima": "0.2.5"})
        antes = e.foto()
        rc, salida = e.ejecutar("--si", "--sin-paquetes")
        self.assertEqual(rc, 1, salida)
        self.assertIn("al menos la 0.2.5", salida)
        self.assertEqual(e.foto(), antes)
        rc, doc = e.json("comprobar", "--json")
        self.assertEqual(rc, 100)
        self.assertFalse(doc["ok"])
        self.assertIn("0.2.5", doc["error"])

    def test_corte_a_mitad_y_recuperar(self):
        e = self.e
        e.publicar("0.2.1", servicio_nuevo(self.base, "0.2.1"))
        antes = e.foto()
        rc, salida = e.ejecutar("_sistema", "0.2.1", entorno={"JAIME0_PRUEBA_CORTE": "4"})
        self.assertEqual(rc, 99, salida)
        self.assertNotEqual(e.foto(), antes, "el corte debe llegar a cambiar algo")
        rc, estado = e.json("estado", "--json")
        self.assertTrue(estado["interrumpida"])
        self.assertIsNone(estado["en_curso"], "el proceso cortado ya no existe")
        self.assertEqual(estado["version_instalada"], "0.2.0")
        # Lo que ve un usuario sin permiso para leer los diarios de root: la marca abierta.
        self.assertTrue(e.existe("var/lib/jaime0/transaccion-abierta.json"))
        rc, salida = e.ejecutar("recuperar")
        self.assertEqual(rc, 0, salida)
        self.assertEqual(e.foto(), antes)
        rc, estado = e.json("estado", "--json")
        self.assertFalse(estado["interrumpida"])
        self.assertFalse(e.existe("var/lib/jaime0/transaccion-abierta.json"))
        self.assertEqual(estado["ultima"]["operacion"], "recuperar")
        self.assertEqual(estado["ultima"]["resultado"], "ok")

    def test_revertir_y_puede_revertir(self):
        e = self.e
        rc, estado = e.json("estado", "--json")
        self.assertFalse(estado["puede_revertir"])
        e.publicar("0.2.1", servicio_nuevo(self.base, "0.2.1"))
        self.assertEqual(e.ejecutar("--si", "--sin-paquetes")[0], 0)
        rc, estado = e.json("estado", "--json")
        self.assertTrue(estado["puede_revertir"])
        rc, salida = e.ejecutar("revertir", "--si")
        self.assertEqual(rc, 0, salida)
        self.assertEqual(e.leer(SERVICIO + "api.py"), b"# api v1\n")
        self.assertFalse(e.existe(SERVICIO + "actualizaciones.py"))
        self.assertEqual(e.leer(AYUDANTE), b"#!/bin/sh\nexec ufw status verbose\n")
        self.assertEqual(e.leer(POLITICA), b"<policyconfig><!-- v1 --></policyconfig>\n")
        self.assertEqual(e.leer("usr/share/jaime0/version"), b"0.2.0\n")
        self.assertIn("jaime0-servicio", salida)
        rc, estado = e.json("estado", "--json")
        self.assertFalse(estado["puede_revertir"])
        self.assertEqual(estado["version_instalada"], "0.2.0")
        self.assertEqual((estado["ultima"]["operacion"], estado["ultima"]["version"]), ("revertir", "0.2.0"))
        # Sin permiso para leer las copias (usuario normal), lo dice ultima.json.
        ultima = json.loads(e.leer("var/lib/jaime0/ultima.json"))
        self.assertTrue(ultima["revertida"])

    def test_json_de_estado_comprobar_e_historial(self):
        e = self.e
        rc, estado = e.json("estado", "--json")
        self.assertEqual(rc, 0)
        self.assertEqual(estado, {
            "ok": True, "version_instalada": "0.2.0", "version_actualizador": J.VERSION_ACTUALIZADOR,
            "canal": "stable", "comprobado": None, "disponible": None, "nueva": False, "en_curso": None,
            "ultima": None, "conflictos": [], "interrumpida": False, "puede_revertir": False,
            "configuracion": {"version": None}})

        # Al dia (GitHub sin publicaciones)
        (e.origen / "releases.json").write_text("[]", encoding="utf-8")
        rc, doc = e.json("comprobar", "--json")
        self.assertEqual((rc, doc), (0, {"ok": True, "nueva": False, "disponible": None, "plan": None}))

        # Version nueva: vista previa sin escribir nada
        (e.casa / ".config/kitty/kitty.conf").write_bytes(b"# mi kitty\n")
        e.publicar("0.2.1", servicio_nuevo(self.base, "0.2.1"))
        antes = e.foto()
        t0 = int(J.time.time())
        rc, doc = e.json("comprobar", "--json")
        t1 = int(J.time.time()) + 1
        self.assertEqual(rc, 100)
        self.assertEqual(e.foto(), antes)
        self.assertEqual(set(doc), {"ok", "nueva", "disponible", "plan"})
        self.assertTrue(doc["ok"])
        self.assertTrue(doc["nueva"])
        self.assertEqual(set(doc["disponible"]), CLAVES_DISPONIBLE)
        self.assertEqual(doc["disponible"]["version"], "0.2.1")
        self.assertEqual(doc["disponible"]["canal"], "stable")
        self.assertEqual(doc["disponible"]["cambios"], ["Cambios de 0.2.1"])
        self.assertIn("servicio", doc["disponible"]["componentes"])
        self.assertEqual(set(doc["plan"]), {"sistema", "usuario"})
        sistema, usuario = doc["plan"]["sistema"], doc["plan"]["usuario"]
        self.assertEqual(set(sistema), CLAVES_GRUPO_PLAN)
        self.assertEqual(set(usuario), CLAVES_GRUPO_PLAN)
        self.assertIn("/" + SERVICIO + "api.py", sistema["reemplazar"])
        self.assertIn("/" + SERVICIO + "actualizaciones.py", sistema["crear"])
        self.assertIn("/" + AYUDANTE, sistema["reemplazar"])
        self.assertIn("/usr/local/bin/tiempo-waybar", sistema["retirar"])
        self.assertEqual(sistema["conflictos"], [])
        self.assertIn("~/.config/fastfetch/config.jsonc", usuario["crear"])
        self.assertIn("~/.config/waybar/style.css", usuario["reemplazar"])
        self.assertEqual(usuario["conflictos"], ["~/.config/kitty/kitty.conf"])
        self.assertIn("~/.config/rofi/viejo.rasi", usuario["retirar"])

        rc, estado = e.json("estado", "--json")
        self.assertTrue(t0 <= estado["comprobado"] <= t1)
        self.assertEqual(estado["disponible"], doc["disponible"])
        self.assertTrue(estado["nueva"])

        # Sin red: la ultima comprobacion buena se conserva
        (e.origen / "releases.json").unlink()
        rc, doc = e.json("comprobar", "--json")
        self.assertEqual(rc, 1)
        self.assertEqual(doc, {"ok": False, "error": doc["error"], "nueva": False, "disponible": None, "plan": None})
        rc, estado2 = e.json("estado", "--json")
        self.assertEqual(estado2["comprobado"], estado["comprobado"])
        self.assertTrue(estado2["nueva"])
        (e.origen / "releases.json").write_bytes(json.dumps(e.publicaciones).encode())

        # Tras instalar
        self.assertEqual(e.ejecutar("--si", "--sin-paquetes")[0], 0)
        rc, estado = e.json("estado", "--json")
        self.assertEqual(set(estado), CLAVES_ESTADO)
        self.assertFalse(estado["nueva"])
        self.assertEqual(estado["version_instalada"], "0.2.1")
        self.assertEqual(estado["configuracion"], {"version": "0.2.1"})
        self.assertEqual(set(estado["ultima"]), {"operacion", "version", "fecha", "resultado", "detalle"})
        self.assertEqual(estado["ultima"]["resultado"], "ok")
        self.assertEqual(estado["ultima"]["version"], "0.2.1")
        self.assertIsInstance(estado["ultima"]["fecha"], int)

        rc, hist = e.json("historial", "--json")
        self.assertEqual(rc, 0)
        self.assertEqual(set(hist), {"ok", "operaciones"})
        self.assertTrue(hist["ok"])
        for o in hist["operaciones"]:
            self.assertEqual(set(o), CLAVES_OPERACION)
            self.assertIsInstance(o["t"], int)
            self.assertIn(o["resultado"], ("ok", "fallo"))
        self.assertIn(("actualizar", "0.2.1", "ok"), [(o["operacion"], o["version"], o["resultado"])
                                                      for o in hist["operaciones"]])
        self.assertIn(("usuario", "0.2.1", "ok"), [(o["operacion"], o["version"], o["resultado"])
                                                   for o in hist["operaciones"]])
        rc, uno = e.json("historial", "--json", "-n", "1")
        self.assertEqual(uno["operaciones"], hist["operaciones"][-1:])

    def test_ultima_operacion_fallida(self):
        e = self.e
        e.publicar("0.2.1", servicio_nuevo(self.base, "0.2.1"), alterar=lambda t, c: (t, c[:-1]))
        self.assertEqual(e.ejecutar("--si", "--sin-paquetes")[0], 1)
        rc, estado = e.json("estado", "--json")
        self.assertEqual(estado["ultima"]["operacion"], "actualizar")
        self.assertEqual(estado["ultima"]["resultado"], "fallo")
        self.assertIn("no coincide", estado["ultima"]["detalle"])
        self.assertFalse(estado["interrumpida"], "fallo antes de tocar nada: no hay nada a medias")
        # Una comprobacion sin red no cuenta como operacion fallida.
        (e.origen / "releases.json").unlink()
        e.ejecutar("comprobar", "--silencioso")
        rc, estado2 = e.json("estado", "--json")
        self.assertEqual(estado2["ultima"], estado["ultima"])

    def test_error_en_json_es_json(self):
        e = self.e
        (e.raiz / "var/lib/jaime0/conflictos.json").write_text("{roto", encoding="utf-8")
        rc, doc = e.json("estado", "--json")
        self.assertEqual(rc, 1)
        self.assertFalse(doc["ok"])
        self.assertIn("conflictos.json", doc["error"])


class OrdenDelHistorial(unittest.TestCase):
    """Dos registros (sistema y usuario) con operaciones en el mismo segundo: el historial las
    ordena por la hora exacta, no por el archivo del que salen. Fallaba en Linux, donde las
    pruebas de revertir caen en el mismo segundo que la actualizacion."""

    def test_mismo_segundo_en_registros_distintos_y_formato_antiguo(self):
        with tempfile.TemporaryDirectory() as d:
            sistema, usuario = os.path.join(d, "sistema.log"), os.path.join(d, "estado", "registro.log")
            os.makedirs(os.path.dirname(usuario))
            with open(sistema, "w", encoding="utf-8") as f:
                f.write("2026-11-16T10:00:00+01:00 viejo con segundos\n")
                f.write("2026-11-16T10:00:05.700000+01:00 segundo en el sistema\n")
            with open(usuario, "w", encoding="utf-8") as f:
                f.write("2026-11-16T10:00:05.200000+01:00 primero en el usuario\n")
            with unittest.mock.patch.object(J, "REGISTRO_SISTEMA", sistema), \
                    unittest.mock.patch.object(J, "dir_estado_usuario", return_value=os.path.join(d, "estado")):
                ops = J.leer_historial()
        self.assertEqual([o["detalle"] for o in ops],
                         ["viejo con segundos", "primero en el usuario", "segundo en el sistema"])
        self.assertTrue(all(set(o) == {"t", "operacion", "version", "resultado", "detalle"} for o in ops))
        self.assertEqual(ops[1]["t"], ops[2]["t"])


class EnCurso(unittest.TestCase):
    """La fase visible solo se muestra si el proceso que la escribio sigue vivo."""

    def setUp(self):
        self.e = Escenario()
        self.e.instalar_iso("0.2.0", base_real(self.e))
        self.proc = self.e.tmp / "proc"
        self.proc.mkdir()
        self.entorno = {"JAIME0_PROC": str(self.proc)}
        (self.e.raiz / "run").mkdir()

    def tearDown(self):
        self.e.limpiar()

    def progreso(self, ruta, fase="instalando", pid=4242, arranque=777):
        destino = self.e.raiz / ruta if not ruta.startswith("~/") else self.e.casa / ruta[2:]
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(json.dumps({"fase": fase, "version": "0.2.1", "desde": 1763300000,
                                       "detalle": "archivos del sistema", "pid": pid, "arranque": arranque}),
                           encoding="utf-8")

    def proceso(self, pid, arranque):
        (self.proc / str(pid)).mkdir(exist_ok=True)
        (self.proc / str(pid) / "stat").write_text(stat_falso(pid, arranque), encoding="ascii")

    def en_curso(self):
        rc, doc = self.e.json("estado", "--json", entorno=self.entorno)
        self.assertEqual(rc, 0)
        return doc["en_curso"], doc

    def test_vivo_muerto_y_reutilizado(self):
        self.assertIsNone(self.en_curso()[0], "sin archivo de progreso")
        self.progreso("run/jaime0-update.estado")
        self.assertIsNone(self.en_curso()[0], "archivo viejo de un proceso que ya no existe")
        self.proceso(4242, 777)
        self.assertEqual(self.en_curso()[0], {"fase": "instalando", "version": "0.2.1", "desde": 1763300000})
        self.proceso(4242, 778)
        self.assertIsNone(self.en_curso()[0], "el sistema reutilizo el pid para otro proceso")
        self.proceso(4242, 777)
        for fase in ("terminado", "fallo"):
            self.progreso("run/jaime0-update.estado", fase=fase)
            self.assertIsNone(self.en_curso()[0], fase)
        (self.e.raiz / "run/jaime0-update.estado").write_text("{roto", encoding="utf-8")
        self.assertIsNone(self.en_curso()[0], "archivo roto")

    def test_fase_de_usuario_y_marca_abierta(self):
        self.progreso("~/.local/state/jaime0/progreso.json", fase="instalando", pid=5000, arranque=1)
        self.proceso(5000, 1)
        en_curso, doc = self.en_curso()
        self.assertEqual(en_curso["fase"], "instalando")
        self.assertFalse(doc["interrumpida"])
        # Marca de transaccion abierta: interrumpida solo si su proceso ya no existe.
        (self.e.raiz / "var/lib/jaime0/transaccion-abierta.json").write_text(
            json.dumps({"desde": "0.2.0", "hasta": "0.2.1", "pid": 6000, "arranque": 9}), encoding="utf-8")
        (self.e.casa / ".local/state/jaime0/progreso.json").unlink()
        self.assertTrue(self.en_curso()[1]["interrumpida"])
        self.proceso(6000, 9)
        self.assertFalse(self.en_curso()[1]["interrumpida"])

    def test_una_actualizacion_real_termina_sin_en_curso(self):
        e = self.e
        e.publicar("0.2.1", siguiente(base_real(e), "0.2.1"))
        self.assertEqual(e.ejecutar("--si", "--sin-paquetes")[0], 0)
        progreso = json.loads((e.raiz / "run/jaime0-update.estado").read_text(encoding="utf-8"))
        self.assertEqual(progreso["fase"], "terminado")
        self.assertEqual(progreso["version"], "0.2.1")
        self.assertTrue({"fase", "version", "desde", "detalle"} <= set(progreso))
        usuario = json.loads((e.casa / ".local/state/jaime0/progreso.json").read_text(encoding="utf-8"))
        self.assertEqual(usuario["fase"], "terminado")
        # Aunque el pid siguiera vivo, "terminado" no es una operacion en curso.
        self.proceso(progreso["pid"], progreso["arranque"] if isinstance(progreso["arranque"], int) else 1)
        self.assertIsNone(self.en_curso()[0])


ACTUALIZACIONES = REPO / "config/includes.chroot_after_packages/usr/local/bin/actualizaciones"


@unittest.skipUnless(ACTUALIZACIONES.exists(), "sin el programa actualizaciones")
class BarraDeActualizaciones(unittest.TestCase):
    """"actualizaciones barra" muestra tambien la version de ZYRON que encontro la ultima
    comprobacion de jaime0-update, sin red y sin ejecutarlo."""

    def setUp(self):
        self.e = Escenario()
        self.base = base_real(self.e)
        self.e.instalar_iso("0.2.0", self.base)
        self.estado = self.e.casa / ".local/state/jaime0"

    def tearDown(self):
        self.e.limpiar()

    def barra(self):
        env = dict(os.environ)
        env.update({"JAIME0_RAIZ": str(self.e.raiz), "HOME": str(self.e.casa), "PYTHONIOENCODING": "utf-8",
                    "XDG_STATE_HOME": str(self.e.casa / ".local/state"), "NO_COLOR": "1"})
        r = subprocess.run([sys.executable, str(ACTUALIZACIONES), "barra"], env=env, capture_output=True,
                           text=True, encoding="utf-8", stdin=subprocess.DEVNULL)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(len(r.stdout.splitlines()), 1)
        return json.loads(r.stdout)

    def test_version_de_jaime0(self):
        e = self.e
        self.assertEqual(self.barra(), {"text": "", "class": "al-dia", "tooltip": ""})
        e.publicar("0.2.1", siguiente(self.base, "0.2.1"))
        self.assertEqual(self.barra()["text"], "", "la barra no consulta la red")
        self.assertEqual(e.ejecutar("comprobar")[0], 100)
        d = self.barra()
        self.assertEqual(d["class"], "disponible")
        self.assertEqual(d["text"], "\U000f06b0")
        self.assertEqual(d["tooltip"], "ZYRON 0.2.1 disponible (canal stable). Para instalarla: jaime0-update\n"
                                       "Clic: ver los detalles")
        # Con correcciones de seguridad de Debian: manda el color de seguridad y salen las dos.
        (self.estado / "actualizaciones.json").write_text(
            json.dumps({"paquetes": 12, "seguridad": ["openssl"], "comprobado": "x"}), encoding="utf-8")
        d = self.barra()
        self.assertEqual(d["class"], "seguridad")
        self.assertEqual(d["tooltip"].splitlines(), [
            "Debian: 1 actualización de seguridad (12 paquetes por actualizar en total)",
            "ZYRON 0.2.1 disponible (canal stable). Para instalarla: jaime0-update",
            "Clic: verlas e instalarlas"])
        # Instalada la version: desaparece la linea de ZYRON aunque nadie vuelva a comprobar.
        self.assertEqual(e.ejecutar("--si", "--sin-paquetes")[0], 0)
        self.assertEqual(self.barra()["tooltip"].splitlines(), [
            "Debian: 1 actualización de seguridad (12 paquetes por actualizar en total)",
            "Clic: verlas e instalarlas"])
        (self.estado / "actualizaciones.json").unlink()
        self.assertEqual(self.barra(), {"text": "", "class": "al-dia", "tooltip": ""})
        # Estado roto: se ignora.
        (self.estado / "disponible.json").write_text("{roto", encoding="utf-8")
        self.assertEqual(self.barra()["class"], "al-dia")

    def test_jaime0_update_lee_debian_de_actualizaciones(self):
        """jaime0-update ya no repite apt ni debsecan: usa lo que dejo "actualizaciones"."""
        e = self.e
        self.estado.mkdir(parents=True)
        (self.estado / "actualizaciones.json").write_text(
            json.dumps({"paquetes": 3, "seguridad": ["libssl3t64"], "comprobado": "x"}), encoding="utf-8")
        (e.origen / "releases.json").write_text("[]", encoding="utf-8")
        rc, salida = e.ejecutar("comprobar")
        self.assertEqual(rc, 0, salida)
        self.assertIn("1 con correcciones de seguridad", salida)


HOOK = REPO / "config/hooks/normal/0397-version.hook.chroot"


@unittest.skipUnless(HOOK.exists(), "fuera del repositorio")
class Integracion(unittest.TestCase):
    def test_un_solo_hook_y_aviso_diario(self):
        self.assertFalse((REPO / "config/hooks/normal/0397-actualizador.hook.chroot").exists())
        hook = HOOK.read_text(encoding="utf-8")
        self.assertIn("systemctl --global enable actualizaciones-aviso.timer", hook)
        self.assertNotIn("jaime0-update-aviso", hook)
        self.assertEqual(hook.count("/usr/lib/os-release"), 2)  # una sola vez: sed y printf
        self.assertIn("manifiesto-instalacion.json", hook)
        unidad = (REPO / "config/includes.chroot_after_packages/usr/lib/systemd/user/actualizaciones-aviso.service"
                  ).read_text(encoding="utf-8").splitlines()
        self.assertEqual([l for l in unidad if l.startswith("ExecStart")], [
            "ExecStart=/usr/local/bin/actualizaciones comprobar --notificar --silencioso",
            "ExecStart=-/usr/local/bin/jaime0-update comprobar --notificar --silencioso"])
        self.assertFalse(list((REPO / "config/includes.chroot_after_packages/usr/lib/systemd/user")
                              .glob("jaime0-update-aviso.*")))
        build = (REPO / "auto/build").read_text(encoding="utf-8")
        self.assertIn("PRIVATE KEY", build)
        self.assertIn("--manifiesto-iso", build)
        self.assertLess(build.index("--manifiesto-iso"), build.index("lb build"))

    def test_empaquetador_y_rutas_del_arbol(self):
        cargador = importlib.machinery.SourceFileLoader("empaquetar_pruebas", str(REPO / "scripts/empaquetar-actualizacion.py"))
        spec = importlib.util.spec_from_loader(cargador.name, cargador)
        E = importlib.util.module_from_spec(spec)
        cargador.exec_module(E)
        archivos = E.archivos_actuales()
        for dentro in (SERVICIO + "servicio.py", SERVICIO + "api.py", AYUDANTE, POLITICA,
                       "usr/local/bin/jaime0-update", "usr/share/jaime0/control/shell.qml",
                       "usr/lib/systemd/user/jaime0-servicio.service", "etc/skel/.config/hypr/hyprland.lua"):
            self.assertIn(dentro, archivos)
        for fuera in archivos:
            self.assertNotIn("__pycache__", fuera)
            self.assertFalse(fuera.endswith(".pyc"), fuera)
            self.assertFalse(fuera.startswith(("etc/calamares/", "etc/greetd/", "etc/modprobe.d/", "etc/udev/",
                                               "usr/local/sbin/", "usr/share/keyrings/", "etc/apt/sources.list.d/",
                                               "usr/share/calamares/", "usr/lib/live/", "etc/live/")), fuera)
        self.assertNotIn("usr/local/bin/instalar-sistema", archivos)
        self.assertNotIn("usr/share/jaime0/manifiesto.json", archivos)
        self.assertEqual(E.modo_de(SERVICIO + "api.py", b"#!/usr/bin/python3\n"), "644")
        self.assertEqual(E.modo_de(AYUDANTE, b"#!/bin/sh\n"), "755")
        self.assertEqual(E.modo_de(POLITICA, b"<p/>"), "644")


if __name__ == "__main__":
    unittest.main()

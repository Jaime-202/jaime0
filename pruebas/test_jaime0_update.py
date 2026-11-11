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

    def manifiesto(self, version, archivos, historico):
        carga = io.BytesIO()
        with tarfile.open(fileobj=carga, mode="w:gz") as tar:
            for rel, datos in sorted(archivos.items()):
                info = tarfile.TarInfo(rel)
                info.size = len(datos)
                tar.addfile(info, io.BytesIO(datos))
        carga = carga.getvalue()
        m = {
            "formato": 1, "version": version, "canal": J.canal_de(version), "fecha": "2026-11-11",
            "cambios": [f"Cambios de {version}"], "problemas_conocidos": [],
            "requisitos": {"version_minima": "0.1.0"}, "compatibilidad": {}, "paquetes": [],
            "componentes": sorted({J.componente_de(r) for r in archivos}), "reinicio": "sesion",
            "carga": {"nombre": f"jaime0-{version}.tar.gz", "sha256": sha(carga), "tamano": len(carga)},
            "archivos": {r: {"sha256": sha(d), "modo": "755" if r.startswith("usr/local/bin/") else "644",
                             "componente": J.componente_de(r)} for r, d in archivos.items()},
            "historico": {r: list(h) for r, h in historico.items()},
        }
        return m, carga

    def publicar(self, version, archivos, prerelease=None, alterar=None):
        """Publica una version. alterar(manifiesto_bytes, carga) -> (manifiesto_bytes, carga)
        permite falsificar algo DESPUES de firmar."""
        m, carga = self.manifiesto(version, archivos, self.historico)
        texto = json.dumps(m, indent=1, sort_keys=True).encode()
        d = self.origen / version
        d.mkdir()
        (d / "manifiesto.json").write_bytes(texto)
        subprocess.run(["openssl", "pkeyutl", "-sign", "-inkey", str(self.clave), "-rawin",
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
            f'NAME="Jaime0"\nID=jaime0\nVERSION="{version}"\nVERSION_ID={version}\n'.encode())
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
        return r.returncode, r.stdout + r.stderr

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
        # Retirado de Jaime0 pero modificado: se conserva
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
        self.assertIn(b'NAME="Jaime0"', e.leer("usr/lib/os-release"))
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

        # Revertir el sistema vuelve a 0.2.0 (solo archivos de Jaime0)
        rc, salida = e.ejecutar("revertir", "--si")
        self.assertEqual(rc, 0, salida)
        self.assertEqual(e.leer("usr/share/jaime0/version"), b"0.2.0\n")
        self.assertIn(b"VERSION_ID=0.2.0\n", e.leer("usr/lib/os-release"))
        self.assertEqual(e.leer("usr/local/bin/tiempo-waybar"), b"#!/bin/sh\necho se retira\n")
        self.assertEqual(e.leer("etc/skel/.config/kitty/kitty.conf"), b"# kitty v1\n")

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
        """Ni con firma valida se escribe fuera de las rutas de Jaime0."""
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


if __name__ == "__main__":
    unittest.main()

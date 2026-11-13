#!/usr/bin/env python3
"""Pruebas de jaime0-flatpak sin red ni privilegios: flatpak, apt-get, sudo y dpkg-query
son programas de mentira que guardan su estado en una carpeta temporal y anotan cada
llamada. Comprueban que no se hace nada sin confirmar y que activar/desactivar llaman a
lo que deben.

    python3 -m unittest discover -s pruebas -v
"""
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
REPO = pathlib.Path(__file__).resolve().parent.parent
PROGRAMA = REPO / "config/includes.chroot_after_packages/usr/local/bin/jaime0-flatpak"

# flatpak de mentira: remotos en $ESTADO/remotos, aplicaciones ("id<TAB>origen") en $ESTADO/apps.
FLATPAK = r"""#!/bin/sh
echo "flatpak $*" >> "$ESTADO/llamadas"
touch "$ESTADO/remotos" "$ESTADO/apps"
case "$*" in
    --version) echo "Flatpak 1.18.4" ;;
    *"remotes --user"*) : ;;
    *"remotes --system --columns=name"*) cat "$ESTADO/remotos" ;;
    *"remotes --columns=name,options"*) sed 's/$/\tsystem/' "$ESTADO/remotos" ;;
    *"list --system --app --columns=application,origin"*) cat "$ESTADO/apps" ;;
    *"list --app --columns=application,origin,installation"*) sed 's/$/\tsystem/' "$ESTADO/apps" ;;
    *"list --app --columns=application"*) cut -f1 "$ESTADO/apps" ;;
    *"remote-add"*) grep -qx flathub "$ESTADO/remotos" || echo flathub >> "$ESTADO/remotos" ;;
    *"remote-delete"*) : > "$ESTADO/remotos" ;;
    *"--unused"*) : ;;
    "uninstall "*) T=$(printf '	'); for A in "$@"; do grep -v "^$A$T" "$ESTADO/apps" > "$ESTADO/apps.n" || true; mv "$ESTADO/apps.n" "$ESTADO/apps"; done ;;
esac
"""
# apt-get de mentira: "install flatpak" pone el flatpak de mentira en el PATH; "remove" lo quita.
APT_GET = r"""#!/bin/sh
echo "apt-get $*" >> "$ESTADO/llamadas"
case "$*" in
    *install*) cp "$ESTADO/flatpak.plantilla" "$BIN/flatpak"; chmod +x "$BIN/flatpak" ;;
    *remove*) rm -f "$BIN/flatpak" ;;
esac
"""
SUDO = '#!/bin/sh\necho "sudo $*" >> "$ESTADO/llamadas"\nexec "$@"\n'
DPKG_QUERY = '#!/bin/sh\n[ -x "$BIN/flatpak" ] && printf installed\nexit 0\n'


class Escenario:
    def __init__(self, con_flatpak=False, remotos="", apps=""):
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="jaime0-flatpak-"))
        self.bin = self.tmp / "bin"
        self.estado = self.tmp / "estado"
        self.bin.mkdir()
        self.estado.mkdir()
        # Solo las herramientas que usa el programa: ningun flatpak, apt ni sudo de verdad.
        for herramienta in ("sh", "awk", "grep", "sed", "id", "cat", "cut", "cp", "mv", "rm", "chmod", "touch"):
            real = shutil.which(herramienta)
            if real:
                (self.bin / herramienta).symlink_to(real)
        for nombre, cuerpo in (("apt-get", APT_GET), ("sudo", SUDO), ("dpkg-query", DPKG_QUERY)):
            self._escribir(self.bin / nombre, cuerpo)
        self._escribir(self.estado / "flatpak.plantilla", FLATPAK)
        if con_flatpak:
            self._escribir(self.bin / "flatpak", FLATPAK)
        (self.estado / "remotos").write_text(remotos, encoding="utf-8")
        (self.estado / "apps").write_text(apps, encoding="utf-8")

    @staticmethod
    def _escribir(ruta, cuerpo):
        ruta.write_text(cuerpo, encoding="utf-8")
        ruta.chmod(0o755)

    def ejecutar(self, *args, entrada=None):
        entorno = {"PATH": str(self.bin), "ESTADO": str(self.estado), "BIN": str(self.bin), "LANG": "C.UTF-8"}
        return subprocess.run([str(self.bin / "sh"), str(PROGRAMA), *args], input=entrada, capture_output=True,
                              text=True, env=entorno, timeout=30, stdin=None if entrada is not None else subprocess.DEVNULL)

    def llamadas(self):
        f = self.estado / "llamadas"
        return f.read_text(encoding="utf-8").splitlines() if f.exists() else []

    def cambios(self):
        """Llamadas que modifican algo (las consultas de flatpak no cuentan)."""
        return [l for l in self.llamadas() if l.startswith(("apt-get", "sudo"))
                or any(o in l for o in ("remote-add", "remote-delete", "uninstall"))]

    def limpiar(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


@unittest.skipUnless(shutil.which("sh") and os.name == "posix", "necesita un sistema POSIX")
class PruebasFlatpak(unittest.TestCase):
    def escenario(self, **kw):
        e = Escenario(**kw)
        self.addCleanup(e.limpiar)
        return e

    def test_uso_y_argumentos_invalidos(self):
        e = self.escenario()
        for args in ((), ("raro",), ("activar", "--bla")):
            r = e.ejecutar(*args)
            self.assertEqual(r.returncode, 2, args)
            self.assertIn("Uso:", r.stderr)
        self.assertEqual(e.ejecutar("--help").returncode, 0)
        self.assertEqual(e.llamadas(), [])

    def test_estado_sin_flatpak(self):
        r = self.escenario().ejecutar("estado")
        self.assertEqual(r.returncode, 0)
        self.assertIn("no instalado", r.stdout)

    def test_activar_sin_terminal_no_cambia_nada(self):
        e = self.escenario()
        r = e.ejecutar("activar")
        self.assertEqual(r.returncode, 1)
        self.assertIn("Cancelado", r.stdout)
        self.assertIn("dl.flathub.org", r.stdout)
        self.assertEqual(e.llamadas(), [])

    def test_activar_con_si(self):
        e = self.escenario()
        r = e.ejecutar("activar", "--si")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        c = e.cambios()
        self.assertTrue(any("apt-get install -y flatpak" in l for l in c), c)
        self.assertTrue(any("remote-add --system --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo" in l
                            for l in c), c)
        self.assertFalse(any(" install flathub" in l or "flatpak install" in l for l in e.llamadas()))
        r = e.ejecutar("estado")
        self.assertIn("Flathub: activado", r.stdout)
        # Segunda vez: no hace nada.
        antes = len(e.cambios())
        self.assertIn("ya estan activados", e.ejecutar("activar", "--si").stdout)
        self.assertEqual(len(e.cambios()), antes)

    def test_activar_con_flatpak_ya_instalado_no_usa_apt(self):
        e = self.escenario(con_flatpak=True)
        self.assertEqual(e.ejecutar("activar", "--si").returncode, 0)
        self.assertFalse(any(l.startswith("apt-get") for l in e.llamadas()))

    def test_desactivar_responde_no(self):
        e = self.escenario(con_flatpak=True, remotos="flathub\n")
        # Con entrada pero sin terminal, confirmar() responde no sin leerla.
        r = e.ejecutar("desactivar", entrada="s\n")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(e.cambios(), [])

    def test_desactivar_con_si_quita_apps_remoto_y_paquete(self):
        e = self.escenario(con_flatpak=True, remotos="flathub\n", apps="org.ejemplo.App\tflathub\n")
        r = e.ejecutar("desactivar", "--si")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        c = e.cambios()
        self.assertTrue(any("uninstall --system -y --noninteractive org.ejemplo.App" in l for l in c), c)
        self.assertTrue(any("remote-delete --system --force flathub" in l for l in c), c)
        self.assertTrue(any("apt-get remove -y flatpak" in l for l in c), c)
        self.assertFalse(any("autoremove" in l for l in c), c)
        self.assertFalse((e.bin / "flatpak").exists())


if __name__ == "__main__":
    unittest.main()

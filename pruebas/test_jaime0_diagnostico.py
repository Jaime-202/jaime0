#!/usr/bin/env python3
"""Pruebas de jaime0-diagnostico: la limpieza de datos personales (limpiar) y que el
programa no falle aunque no haya ningun comando ni archivo del sistema (raiz falsa
con JAIME0_RAIZ y PATH vacio). Funcionan en Windows y en Linux.

    python3 -m unittest discover -s pruebas -v
"""
import importlib.machinery
import importlib.util
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
REPO = pathlib.Path(__file__).resolve().parent.parent
PROGRAMA = REPO / "config/includes.chroot_after_packages/usr/local/bin/jaime0-diagnostico"


def cargar():
    cargador = importlib.machinery.SourceFileLoader("jaime0_diagnostico_pruebas", str(PROGRAMA))
    spec = importlib.util.spec_from_loader(cargador.name, cargador)
    modulo = importlib.util.module_from_spec(spec)
    cargador.exec_module(modulo)
    return modulo


D = cargar()

SECCIONES = ["Jaime0", "Sistema", "CPU y memoria", "Gráfica y monitores", "Sonido", "Red", "Bluetooth",
             "Portátil", "Almacenamiento", "USB", "Firmware que falta", "Sesión gráfica", "Paquetes clave"]

# Salida de ejemplo con datos personales mezclados con datos tecnicos que deben quedar.
EJEMPLO = """\
Hyprland 0.57.0 built from branch v0.57.0, compilado a las 19:00 (19:00:05)
2: wlp2s0: <BROADCAST,MULTICAST,UP> mtu 1500
    link/ether a4:5e:60:c1:22:9f brd ff:ff:ff:ff:ff:ff
    inet 192.168.1.37/24 brd 192.168.1.255 scope global dynamic wlp2s0
    inet6 2a02:9130:8c3f:1200:5ab4:1f2e:8a9c:12ef/64 scope global
    inet6 fe80::1c2d:3e4f:5a6b:7c8d%wlp2s0 scope link
    inet6 ::1/128 scope host
Interfaz USB enx0a1b2c3d4e5f y otra MAC 00-1A-2B-3C-4D-5E
UUID=3f2b8c1e-9a4d-4c7e-b1f0-2d6e8a9c0b1d
usb 1-2: SerialNumber: S4EVNF0M123456X
  iSerial                 3 0123456789ABCDEF
    "serial": "PL1234567",
SSID: CasaGarcia_5G
contacto: maria.garcia@example.com
/home/maria/.config/hypr/hyprland.lua
portatil-de-maria kernel: maria ha iniciado sesion en portatil-de-maria
pipewire [1.6.9, maria@portatil-de-maria, pid:3202]
00:02.0 VGA compatible controller [0300]: Intel Corporation [8086:9a49] (rev 01)
Bus 001 Device 002: ID 8087:0026 Intel Corp. AX201 Bluetooth
Kernel: 6.12.0-1-amd64, mesa 26.1.6-1, PCI 0000:00:02.0
"""


def limpio(texto, usuario="maria", casa="/home/maria", equipo="portatil-de-maria"):
    return D.limpiar(texto, usuario=usuario, casa=casa, equipo=equipo)


class PruebasLimpiar(unittest.TestCase):
    def test_mac_con_dos_puntos_y_guiones(self):
        t = limpio("ether a4:5e:60:c1:22:9f y 00-1A-2B-3C-4D-5E y 0a1b.2c3d.4e5f")
        self.assertNotIn("a4:5e:60", t)
        self.assertNotIn("00-1A-2B", t)
        self.assertNotIn("0a1b.2c3d", t)
        self.assertEqual(t.count("<MAC>"), 3)

    def test_interfaz_con_mac_en_el_nombre(self):
        t = limpio("enx0a1b2c3d4e5f wlx001122334455 wlp2s0")
        self.assertEqual(t, "enx<MAC> wlx<MAC> wlp2s0")

    def test_ipv4(self):
        t = limpio("inet 192.168.1.37/24 brd 192.168.1.255, dns 8.8.8.8.")
        self.assertNotRegex(t, r"\d+\.\d+\.\d+\.\d+")
        self.assertIn("<IPv4>/24", t)

    def test_ipv6_completa_y_abreviada(self):
        for ip in ("2a02:9130:8c3f:1200:5ab4:1f2e:8a9c:12ef", "2001:0db8:0000:0000:0000:ff00:0042:8329",
                   "fe80::1c2d:3e4f:5a6b:7c8d%wlp2s0", "::1", "fd00::8807:5fa4:246b:e8bc", "2001:db8::",
                   "::ffff:192.0.2.128"):
            with self.subTest(ip=ip):
                t = limpio(f"inet6 {ip}/64 scope global")
                self.assertEqual(t, "inet6 <IPv6>/64 scope global")

    def test_no_rompe_versiones_horas_ni_ids(self):
        textos = ["Hyprland 0.57.0", "a las 19:00", "19:00:05", "Fecha 2026-11-13 13:00",
                  "ID 8087:0026 Intel Corp.", "PCI 0000:00:02.0", "[8086:9a49] (rev 01)",
                  "mesa 26.1.6-1", "kernel 6.12.0-1-amd64", "epoch 1:2.4.120-2", "PipeWire 1.6.9",
                  "Startup finished in 7.098s (kernel) + 12.483s", "Serial ATA controller",
                  "USB-Serial Controller", "jaime0 0.2.0-beta.1", "loop0 1.7G", "user@1000.service"]
        for texto in textos:
            with self.subTest(texto=texto):
                self.assertEqual(limpio(texto), texto)

    def test_uuid(self):
        t = limpio("root=UUID=3f2b8c1e-9a4d-4c7e-b1f0-2d6e8a9c0b1d ro")
        self.assertEqual(t, "root=UUID=<UUID> ro")

    def test_hostname(self):
        t = limpio("Equipo portatil-de-maria y PORTATIL-DE-MARIA; hostname=portatil-de-maria")
        self.assertNotIn("portatil", t.lower())
        self.assertIn("<equipo>", t)

    def test_hostname_generico_no_borra_el_nombre_del_producto(self):
        # En el sistema en vivo el equipo se llama "jaime0", igual que el producto.
        t = D.limpiar("Jaime0 0.2.0 en jaime0, pipewire [1.6.9, user@jaime0, pid:1]; hostname=jaime0",
                      usuario="user", casa="/home/user", equipo="jaime0")
        self.assertIn("Jaime0 0.2.0 en jaime0", t)
        self.assertIn("<usuario>@<equipo>", t)
        self.assertIn("hostname=jaime0", t)

    def test_usuario_y_carpeta_personal(self):
        t = limpio("/home/maria/.config/hypr/hyprland.lua; maria inicio sesion; HOME=/home/maria")
        self.assertNotIn("maria", t)
        self.assertIn("~/.config/hypr/hyprland.lua", t)
        self.assertIn("HOME=~", t)

    def test_usuario_generico_solo_en_contexto(self):
        t = D.limpiar("/home/user/x y /run/user/1000 y user@jaime0", usuario="user",
                      casa="/home/user", equipo="jaime0")
        self.assertEqual(t, "~/x y /run/user/1000 y <usuario>@<equipo>")

    def test_numeros_de_serie(self):
        t = limpio('usb 1-2: SerialNumber: S4EVNF0M123456X\n  iSerial                 3 0123456789ABCDEF\n'
                   '    "serial": "PL1234567",\nSerial Number: ABC-999\nID_SERIAL_SHORT=XYZ123\n'
                   'serial_number=QQQ777\nSerial No.: 55AA')
        for secreto in ("S4EVNF0M123456X", "0123456789ABCDEF", "PL1234567", "ABC-999", "XYZ123",
                        "QQQ777", "55AA"):
            self.assertNotIn(secreto, t)
        self.assertIn("iSerial                 3 <oculto>", t)

    def test_ssid(self):
        t = limpio("SSID: CasaGarcia_5G\nESSID:\"Vecino\"\nBSSID=aa\nssid=Movil de Maria")
        for secreto in ("CasaGarcia", "Vecino", "Movil"):
            self.assertNotIn(secreto, t)

    def test_correo(self):
        t = limpio("Contacto: maria.garcia+bugs@example.com, otro <a.b@sub.dominio.es>")
        self.assertNotIn("example.com", t)
        self.assertNotIn("dominio.es", t)
        self.assertEqual(t.count("<correo>"), 2)

    def test_ejemplo_completo(self):
        t = limpio(EJEMPLO)
        self.assertNotRegex(t, r"(?i)\b[0-9a-f]{2}([:-])(?:[0-9a-f]{2}\1){4}[0-9a-f]{2}\b")
        self.assertNotRegex(t, r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
        for secreto in ("2a02:", "fe80::", "::1/", "maria", "portatil", "CasaGarcia", "S4EVNF",
                        "3f2b8c1e", "example.com", "PL1234567", "0123456789ABCDEF"):
            self.assertNotIn(secreto, t)
        for tecnico in ("0.57.0", "19:00", "19:00:05", "8086:9a49", "8087:0026", "26.1.6-1",
                        "6.12.0-1-amd64", "0000:00:02.0", "wlp2s0", "1.6.9", "~/.config/hypr/hyprland.lua"):
            self.assertIn(tecnico, t)


class Escenario:
    """Raiz falsa sin nada (o con unos pocos archivos) y PATH vacio: ningun comando existe."""

    def __init__(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="jaime0-diagnostico-"))
        self.raiz = self.tmp / "raiz"
        self.casa = self.tmp / "casa"
        self.vacio = self.tmp / "sin-comandos"
        for d in (self.raiz, self.casa, self.vacio):
            d.mkdir()

    def archivo(self, relativo, contenido):
        destino = self.raiz / relativo
        destino.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(contenido, bytes):
            destino.write_bytes(contenido)
        else:
            destino.write_text(contenido, encoding="utf-8")

    def ejecutar(self, *args):
        env = {k: v for k, v in os.environ.items()
               if k.upper() not in ("PATH", "HYPRLAND_INSTANCE_SIGNATURE", "XDG_RUNTIME_DIR")}
        env.update(JAIME0_RAIZ=str(self.raiz), HOME=str(self.casa), USERPROFILE=str(self.casa),
                   PATH=str(self.vacio), PYTHONIOENCODING="utf-8", USER="maria", LOGNAME="maria")
        r = subprocess.run([sys.executable, str(PROGRAMA), *args], env=env, capture_output=True,
                           text=True, encoding="utf-8", timeout=60)
        return r.returncode, r.stdout, r.stderr

    def limpiar(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


class PruebasPrograma(unittest.TestCase):
    def setUp(self):
        self.e = Escenario()
        self.addCleanup(self.e.limpiar)

    def comprobar_secciones(self, informe):
        for n, titulo in enumerate(SECCIONES, 1):
            self.assertRegex(informe, rf"(?m)^== {n}\. {re.escape(titulo)}")
        self.assertNotIn("Error interno", informe)
        self.assertNotIn("Traceback", informe)
        self.assertIn("NO recoge", informe)

    def test_sin_comandos_ni_archivos_muestra_todas_las_secciones(self):
        rc, out, err = self.e.ejecutar("--pantalla")
        self.assertEqual(rc, 0, err)
        self.assertEqual(err, "")
        self.comprobar_secciones(out)
        self.assertIn("no disponible (falta lspci)", out)
        self.assertIn("no disponible (falta lsusb)", out)
        self.assertIn("no disponible (falta dpkg-query)", out)
        self.assertIn("requiere sudo", out)
        self.assertNotIn("\x1b[", out)  # sin colores fuera de una terminal

    def test_sudo_sin_sudo_no_falla(self):
        rc, out, err = self.e.ejecutar("--pantalla", "--sudo")
        self.assertEqual(rc, 0, err)
        self.comprobar_secciones(out)

    def test_guarda_el_informe_en_la_carpeta_personal(self):
        rc, out, err = self.e.ejecutar()
        self.assertEqual(rc, 0, err)
        archivos = list(self.e.casa.glob("jaime0-diagnostico-*.txt"))
        self.assertEqual(len(archivos), 1)
        self.assertRegex(archivos[0].name, r"^jaime0-diagnostico-\d{8}-\d{4}\.txt$")
        self.assertIn("Informe guardado en", out)
        self.comprobar_secciones(archivos[0].read_text(encoding="utf-8"))

    def test_opcion_desconocida(self):
        rc, out, err = self.e.ejecutar("--borrar-todo")
        self.assertEqual(rc, 2)
        self.assertIn("opción desconocida", err)

    def test_datos_de_la_raiz_falsa_y_limpieza(self):
        e = self.e
        e.archivo("usr/share/jaime0/version", "0.2.0-beta.1\n")
        e.archivo("run/live/medium/.disk", "")
        e.archivo("proc/sys/kernel/hostname", "portatil-de-maria\n")
        e.archivo("proc/sys/kernel/osrelease", "6.12.0-1-amd64\n")
        e.archivo("etc/os-release", 'PRETTY_NAME="Jaime0"\nVERSION_CODENAME=forky\n')
        e.archivo("sys/firmware/efi/efivars/SecureBoot-8be4df61-93ca-11d2-aa0d-00e098032b8c",
                  b"\x06\x00\x00\x00\x01")
        e.archivo("proc/cmdline", "BOOT_IMAGE=/vmlinuz root=UUID=3f2b8c1e-9a4d-4c7e-b1f0-2d6e8a9c0b1d "
                                  "hostname=portatil-de-maria ip=192.168.1.37 vt.default_red=0x12 quiet\n")
        e.archivo("proc/cpuinfo", "processor\t: 0\nmodel name\t: CPU de prueba\nphysical id\t: 0\n"
                                  "cpu cores\t: 2\n\nprocessor\t: 1\nmodel name\t: CPU de prueba\n"
                                  "physical id\t: 0\ncpu cores\t: 2\n")
        e.archivo("proc/meminfo", "MemTotal:       8000000 kB\nMemAvailable:   4000000 kB\nSwapTotal: 0 kB\n")
        e.archivo("proc/modules", "i915 4000000 10 - Live 0x0\nsnd 1 0 - Live 0x0\n")
        e.archivo("proc/asound/cards", " 0 [PCH            ]: HDA-Intel - HDA Intel PCH\n")
        e.archivo("sys/class/net/wlp2s0/wireless/.x", "")
        e.archivo("sys/class/net/wlp2s0/operstate", "up\n")
        e.archivo("sys/class/net/wlp2s0/address", "a4:5e:60:c1:22:9f\n")
        e.archivo("sys/class/power_supply/BAT0/type", "Battery\n")
        e.archivo("sys/class/power_supply/BAT0/present", "1\n")
        e.archivo("sys/class/power_supply/BAT0/capacity", "80\n")
        e.archivo("sys/class/power_supply/BAT0/energy_full", "45000000\n")
        e.archivo("sys/class/power_supply/BAT0/energy_full_design", "50000000\n")
        e.archivo("sys/class/power_supply/BAT0/serial_number", "BAT-SERIE-123\n")
        e.archivo("sys/class/backlight/intel_backlight/max_brightness", "19200\n")
        e.archivo("proc/acpi/button/lid/LID0/state", "state:      open\n")
        e.archivo("proc/bus/input/devices",
                  'I: Bus=0018 Vendor=06cb Product=7e7e\nN: Name="SYNA2B52:00 06CB:7E7E Touchpad"\n\n'
                  'I: Bus=0005 Vendor=004c Product=0269\nN: Name="Auriculares de Maria"\n')
        rc, out, err = e.ejecutar("--pantalla")
        self.assertEqual(rc, 0, err)
        self.comprobar_secciones(out)
        for esperado in ("Versión: 0.2.0-beta.1", "en vivo",
                         "Kernel: 6.12.0-1-amd64", "Arranque: UEFI", "Secure Boot: activado",
                         "CPU: CPU de prueba", "Núcleos: 2 físicos, 2 hilos", "RAM total: 7.6 GiB",
                         "i915", "HDA Intel PCH", "wlp2s0: wifi", "estado up", "carga 80 %",
                         "salud 90 %", "intel_backlight", "Tapa: open", "Touchpad: sí",
                         "<dispositivo Bluetooth>", "root=UUID=<UUID>", "hostname=<equipo>",
                         "ip=<IPv4>"):
            self.assertIn(esperado, out)
        for secreto in ("portatil", "maria", "Maria", "a4:5e:60", "BAT-SERIE", "192.168", "3f2b8c1e",
                        "vt.default_red"):
            self.assertNotIn(secreto, out)


if __name__ == "__main__":
    unittest.main()

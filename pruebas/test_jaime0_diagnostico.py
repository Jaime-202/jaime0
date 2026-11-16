#!/usr/bin/env python3
"""Pruebas de jaime0-diagnostico: la limpieza de datos personales (limpiar), que el
programa no falle aunque no haya ningun comando ni archivo del sistema (raiz falsa
con JAIME0_RAIZ y PATH vacio) y el diagnostico interpretado (comprobar, historial y
reparar) con un sistema de mentira y ejecutar() simulado. Funcionan en Windows y en Linux.

    python3 -m unittest discover -s pruebas -v
"""
import contextlib
import importlib.machinery
import importlib.util
import io
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock

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


# ---------------------------------------------------------------------------
# Diagnostico interpretado (comprobar, historial, reparar): en el mismo proceso, con una raiz
# falsa (D.RAIZ) y ejecutar() simulado. Nada toca el sistema real.
# ---------------------------------------------------------------------------

K1, K2 = "6.12.0-1-amd64", "6.12.0-2-amd64"
SKEL_WAYBAR = (REPO / "config/includes.chroot_after_packages/etc/skel/.config/waybar/config.jsonc").read_text(
    encoding="utf-8")


def res(salida="", ok=True, error="", motivo="", codigo=None):
    return D.Resultado(ok, salida, error, motivo, codigo if codigo is not None else (0 if ok else 1))


def falta(nombre):
    return D.Resultado(False, motivo=f"no disponible (falta {nombre})")


def unidad(activo="active", archivo="enabled", resultado="success", carga="loaded"):
    return res(f"LoadState={carga}\nActiveState={activo}\nUnitFileState={archivo}\nResult={resultado}\n")


class EjecutorFalso:
    """Imita ejecutar(): responde segun el comando (nombre del programa sin ruta + argumentos),
    exacto o por prefijo. Con sudo solo responde lo que lleve la clave "sudo ..."."""

    def __init__(self, respuestas):
        self.resp = respuestas  # el mismo diccionario: cada prueba lo cambia
        self.llamadas = []

    def __call__(self, args, env_extra=None, tiempo=None, sudo=False):
        clave = " ".join([os.path.basename(args[0]), *args[1:]])
        self.llamadas.append((clave, sudo))
        buscada = ("sudo " + clave) if sudo else clave
        for k in sorted(self.resp, key=len, reverse=True):
            if (k.startswith("sudo ") == sudo) and (buscada == k or buscada.startswith(k + " ")):
                r = self.resp[k]
                return r() if callable(r) else r
        return falta("sudo" if sudo else os.path.basename(args[0]))


KERNEL_SANO = "Linux version 6.12.0\nPM: suspend entry (deep)\nPM: suspend exit\nusb 1-1: new device\n"


def respuestas_sanas():
    return {
        "systemd-detect-virt": res("none\n", ok=False, codigo=1),
        "systemctl --failed": res(""),
        "systemctl --user --failed": res(""),
        "journalctl -b -p err -o json": res(""),
        "journalctl -k -b": res(KERNEL_SANO),
        "dpkg --audit": res(""),
        "dpkg-query -W": res("nvidia-kernel-dkms ii \n"),
        "hyprctl -j configerrors": res('[\n""\n]'),
        "hyprctl version": res("Hyprland 0.52.0 built from branch v0.52.0\n"),
        "hyprctl monitors all -j": res('[{"name":"eDP-1","width":1920,"height":1080,"refreshRate":144.0,'
                                       '"disabled":false}]'),
        "jaime0-ajustes ver --json": res('{"ajustes": [], "temas": {}, "fondos": [], "avisos": []}\n'),
        "jaime0-update estado --json": res('{"ok":true,"version_instalada":"0.4.0-beta.1","canal":"beta",'
                                           '"interrumpida":false,"en_curso":null,"nueva":false}\n'),
        "dkms status": res(f"nvidia-current/550.163.01, {K1}, x86_64: installed\n"),
        "mokutil --test-key": res("/var/lib/dkms/mok.pub is already enrolled\n"),
        "systemctl show NetworkManager.service": unidad(),
        "systemctl show bluetooth.service": unidad(),
        "systemctl show power-profiles-daemon.service": unidad(),
        "nmcli -t -f STATE,CONNECTIVITY general": res("connected:full\n"),
        "nmcli -t -f TYPE,DEVICE connection show --active": res("802-11-wireless:wlp0s20f3\n"),
        "bluetoothctl show": res("Controller 00:11:22:33:44:55 (public)\n\tPowered: yes\n"),
        "powerprofilesctl": res("  performance:\n    Degraded:   no\n\n* balanced:\n    CpuDriver: intel_pstate\n"),
    }


def stat_root(camino):
    return types.SimpleNamespace(st_mode=0o40755 if os.path.isdir(camino) else 0o100755, st_uid=0, st_gid=0)


class BaseDiagnostico(unittest.TestCase):
    """Portatil sano parecido al de Jaime0: Intel + NVIDIA (cargada), bateria, Wi-Fi y Bluetooth."""

    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="jaime0-diagnostico-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.raiz, self.casa, self.estado = self.tmp / "raiz", self.tmp / "casa", self.tmp / "estado"
        for d in (self.raiz, self.casa):
            d.mkdir()
        self.resp = respuestas_sanas()
        self.ejec = EjecutorFalso(self.resp)
        self.ordenes = []
        entorno = {"HOME": str(self.casa), "USERPROFILE": str(self.casa), "USER": "maria", "LOGNAME": "maria",
                   "XDG_CONFIG_HOME": str(self.casa / ".config"), "JAIME0_ESTADO": str(self.estado),
                   "HYPRLAND_INSTANCE_SIGNATURE": "firma", "XDG_SESSION_TYPE": "wayland"}
        for objetivo in (mock.patch.dict(os.environ, entorno),
                         mock.patch.object(D, "RAIZ", str(self.raiz)), mock.patch.object(D, "MODO_PRUEBA", True),
                         mock.patch.object(D, "ejecutar", self.ejec), mock.patch.object(D, "stat_ruta", stat_root),
                         mock.patch.object(D, "uso_disco", lambda c: (500 * D.GIB, 200 * D.GIB)),
                         mock.patch.object(D, "terminal_interactiva", lambda: True),
                         mock.patch.object(D, "ejecutar_orden", self.ejecutar_orden)):
            objetivo.start()
            self.addCleanup(objetivo.stop)
        self.portatil_sano()

    def ejecutar_orden(self, argv):
        self.ordenes.append(argv)
        return 0

    def archivo(self, relativo, contenido=""):
        destino = self.raiz / relativo
        destino.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(contenido, bytes):
            destino.write_bytes(contenido)
        else:
            destino.write_text(contenido, encoding="utf-8")

    def borrar(self, relativo):
        p = self.raiz / relativo
        shutil.rmtree(p) if p.is_dir() else p.unlink()

    def pci(self, slot, vendor, device, clase):
        for nombre, valor in (("vendor", vendor), ("device", device), ("class", clase)):
            self.archivo(f"sys/bus/pci/devices/{slot}/{nombre}", valor + "\n")

    def portatil_sano(self):
        a = self.archivo
        a("proc/sys/kernel/osrelease", K1 + "\n")
        a("proc/sys/kernel/hostname", "portatil-de-maria\n")
        a("proc/modules", "nvidia_drm 1 0 - Live 0x0\nnvidia 1 0 - Live 0x0\ni915 1 0 - Live 0x0\n")
        a("sys/module/nvidia/version", "550.163.01\n")
        a("proc/vmstat", "nr_free_pages 1\noom_kill 0\n")
        a("proc/mounts", "/dev/nvme0n1p2 / ext4 rw,relatime 0 0\n")
        a("proc/cmdline", "BOOT_IMAGE=/vmlinuz quiet splash\n")
        a("proc/123/comm", "Hyprland\n")
        a("sys/class/hwmon/hwmon0/name", "coretemp\n")
        a("sys/class/hwmon/hwmon0/temp1_input", "52000\n")
        self.pci("0000-00-02.0", "0x8086", "0x9bc4", "0x030000")
        self.pci("0000-01-00.0", "0x10de", "0x1f95", "0x030200")
        self.pci("0000-00-14.3", "0x8086", "0x06f0", "0x028000")
        a("sys/block/nvme0n1/removable", "0\n")
        for n, v in (("type", "Battery"), ("present", "1"), ("capacity", "80"), ("status", "Discharging"),
                     ("energy_full", "45000000"), ("energy_full_design", "50000000"), ("cycle_count", "120"),
                     ("serial_number", "BAT-SERIE-123")):
            a(f"sys/class/power_supply/BAT1/{n}", v + "\n")
        a("sys/class/power_supply/ACAD/type", "Mains\n")
        a("sys/class/power_supply/ACAD/online", "0\n")
        a("sys/class/net/wlp0s20f3/wireless/.x")
        a("sys/class/net/wlp0s20f3/operstate", "up\n")
        for n, (tipo, nombre) in enumerate((("wlan", "phy0"), ("bluetooth", "hci0"))):
            for k, v in (("type", tipo), ("name", nombre), ("soft", "0"), ("hard", "0")):
                a(f"sys/class/rfkill/rfkill{n}/{k}", v + "\n")
        a("sys/class/bluetooth/hci0/.x")
        a("sys/class/drm/card1-eDP-1/status", "connected\n")
        a("sys/firmware/efi/efivars/SecureBoot-8be4df61-93ca-11d2-aa0d-00e098032b8c", b"\x06\x00\x00\x00\x01")
        a("var/lib/dkms/mok.pub", "clave\n")
        a(f"lib/modules/{K1}/updates/dkms/nvidia-current.ko.xz", "x")
        a(f"lib/modules/{K1}/build/Makefile", "x")
        a(f"boot/vmlinuz-{K1}", "x")
        a("usr/local/libexec/jaime0-ufw-estado", "#!/bin/sh\n")
        a("usr/share/polkit-1/actions/es.jaime0.ufw-estado.policy", "<policyconfig/>\n")
        a("usr/local/lib/jaime0/jaime0_servicio/base.py", "\n")
        a("etc/skel/.config/waybar/config.jsonc", SKEL_WAYBAR)
        (self.casa / ".config/waybar").mkdir(parents=True)
        (self.casa / ".config/waybar/config.jsonc").write_text(SKEL_WAYBAR, encoding="utf-8")
        self.estado.mkdir()
        (self.estado / "actualizaciones.json").write_text(
            '{"paquetes": 0, "seguridad": [], "comprobado": "2026-11-16T09:00"}', encoding="utf-8")

    def correr(self, *args, entrada=None):
        salida = io.StringIO()
        with contextlib.redirect_stdout(salida), mock.patch("builtins.input", side_effect=entrada or []):
            rc = D.main(list(args))
        return rc, salida.getvalue()

    def comprobar(self, *extra):
        rc, out = self.correr("comprobar", "--json", *extra)
        self.assertEqual(rc, 0, out)
        lineas = out.splitlines()
        self.assertEqual(len(lineas), 1, "--json debe ser una sola línea")
        doc = json.loads(lineas[0])
        for p in doc["problemas"]:
            for causa in p["causas_probables"]:
                self.assertRegex(causa, r"(?i)probab|posib", f"{p['id']}: causa presentada como confirmada")
        return doc

    @staticmethod
    def comprobacion(doc, cid):
        return next(c for a in doc["areas"] for c in a["comprobaciones"] if c["id"] == cid)

    @staticmethod
    def problema(doc, pid):
        return next((p for p in doc["problemas"] if p["id"] == pid), None)


class PruebasComprobar(BaseDiagnostico):
    def test_sistema_sano_sin_falsos_positivos(self):
        doc = self.comprobar()
        self.assertEqual(doc["problemas"], [])
        estados = {c["id"]: c["estado"] for a in doc["areas"] for c in a["comprobaciones"]}
        self.assertFalse([c for c, e in estados.items() if e in ("WARNING", "ERROR", "CRITICAL")], estados)
        for cid in ("hardware.sensores", "hardware.memoria", "hardware.raiz", "hardware.bateria",
                    "sistema.unidades_sistema", "sistema.unidades_usuario", "sistema.errores_arranque",
                    "sistema.paquetes", "sistema.config_hyprland", "sistema.config_waybar", "sistema.config_ajustes",
                    "sistema.permisos", "sistema.actualizacion", "sistema.seguridad", "graficos.nvidia",
                    "graficos.sesion", "graficos.monitores", "graficos.aceleracion", "conectividad.networkmanager",
                    "conectividad.internet", "conectividad.wifi", "conectividad.bluetooth", "energia.perfiles",
                    "energia.cargador", "energia.suspension"):
            self.assertEqual(estados[cid], "OK", cid)
        self.assertEqual(estados["hardware.smart"], "NO_DISPONIBLE")  # sin --sudo
        self.assertIn("CPU 52 °C", self.comprobacion(doc, "hardware.sensores")["detalle"])
        self.assertIn("salud 90 %, 120 ciclos", self.comprobacion(doc, "hardware.bateria")["detalle"])
        self.assertIn("550.163.01", self.comprobacion(doc, "graficos.nvidia")["detalle"])

    def test_forma_exacta_del_json(self):
        self.resp["dpkg --audit"] = res(" roto   paquete roto\n")
        doc = self.comprobar()
        self.assertEqual(set(doc), {"ok", "v", "t", "duracion", "resumen", "areas", "problemas"})
        self.assertIs(doc["ok"], True)
        self.assertEqual(doc["v"], 1)
        self.assertIsInstance(doc["t"], int)
        self.assertIsInstance(doc["duracion"], (int, float))
        self.assertEqual(set(doc["resumen"]), {"CRITICAL", "ERROR", "WARNING", "INFO", "NO_DISPONIBLE", "NO_APLICA"})
        self.assertEqual([(a["id"], a["nombre"]) for a in doc["areas"]],
                         [("hardware", "HARDWARE"), ("sistema", "SYSTEM"), ("graficos", "GRAPHICS"),
                          ("conectividad", "CONNECTIVITY"), ("energia", "POWER")])
        for a in doc["areas"]:
            self.assertEqual(set(a), {"id", "nombre", "comprobaciones"})
            for c in a["comprobaciones"]:
                self.assertEqual(set(c), {"id", "nombre", "estado", "detalle"})
                self.assertIn(c["estado"], ("OK", "INFO", "WARNING", "ERROR", "CRITICAL", "NO_DISPONIBLE", "NO_APLICA"))
        p = doc["problemas"][0]
        self.assertEqual(set(p), {"id", "titulo", "gravedad", "componente", "area", "detectado", "causas_probables",
                                  "consecuencias", "recomendacion", "reparacion", "veces", "primera_vez", "ultima_vez"})
        self.assertEqual(set(p["reparacion"]), {"id", "descripcion", "ordenes", "root", "copia"})
        self.assertEqual((p["veces"], p["primera_vez"], p["ultima_vez"]), (1, doc["t"], doc["t"]))
        self.assertEqual(doc["resumen"]["ERROR"], 1)

    def test_problemas_ordenados_por_gravedad(self):
        self.resp["dpkg --audit"] = res(" roto   paquete roto\n")                            # ERROR
        (self.estado / "actualizaciones.json").write_text(
            '{"paquetes": 3, "seguridad": ["openssl"], "comprobado": "x"}', encoding="utf-8")  # WARNING
        self.resp["powerprofilesctl"] = res("* performance:\n    Degraded:   yes (lap-detected)\n")  # INFO
        sano = stat_root
        D.stat_ruta = lambda c: (types.SimpleNamespace(st_mode=0o100777, st_uid=0, st_gid=0)
                                 if c.endswith("jaime0-ufw-estado") else sano(c))          # CRITICAL
        doc = self.comprobar()
        self.assertEqual([p["gravedad"] for p in doc["problemas"]], ["CRITICAL", "ERROR", "WARNING", "INFO"])
        self.assertEqual(doc["resumen"], {"CRITICAL": 1, "ERROR": 1, "WARNING": 1, "INFO": 1,
                                          "NO_DISPONIBLE": 1, "NO_APLICA": 0})

    def test_sensores_no_disponibles(self):
        self.borrar("sys/class/hwmon")
        doc = self.comprobar()
        c = self.comprobacion(doc, "hardware.sensores")
        self.assertEqual(c["estado"], "NO_DISPONIBLE")
        self.assertEqual(doc["problemas"], [])

    def test_equipo_sin_nvidia(self):
        self.borrar("sys/bus/pci/devices/0000-01-00.0")
        self.borrar("sys/module/nvidia")
        self.archivo("proc/modules", "i915 1 0 - Live 0x0\n")
        self.resp["dkms status"] = res("")
        doc = self.comprobar()
        self.assertEqual(self.comprobacion(doc, "graficos.nvidia")["estado"], "NO_APLICA")
        self.assertEqual(doc["problemas"], [])

    def test_nvidia_sin_modulo_para_el_nucleo_actual(self):
        self.archivo("proc/sys/kernel/osrelease", K2 + "\n")
        self.archivo(f"lib/modules/{K2}/build/Makefile", "x")
        self.archivo(f"boot/vmlinuz-{K2}", "x")
        self.archivo("proc/modules", "i915 1 0 - Live 0x0\n")
        self.borrar("sys/module/nvidia")
        doc = self.comprobar()
        p = self.problema(doc, "graficos.nvidia_modulo_kernel")
        self.assertIsNotNone(p, doc["problemas"])
        self.assertEqual((p["titulo"], p["gravedad"], p["componente"], p["area"]),
                         ("NVIDIA DRIVER WARNING", "WARNING", "NVIDIA", "graficos"))
        self.assertIn("no está disponible para el núcleo actual", p["consecuencias"])
        self.assertIn(f"Núcleo en uso: {K2}", p["detectado"])
        self.assertIn(f"dkms status: nvidia-current/550.163.01, {K1}, x86_64: installed", p["detectado"])
        self.assertIn(f"Núcleos instalados que sí tienen el módulo: {K1}", p["detectado"])
        causas = " ".join(p["causas_probables"])
        for esperado in ("actualizó el núcleo", "compilación de DKMS", "incompatibilidad"):
            self.assertIn(esperado, causas)
        self.assertEqual(p["reparacion"]["ordenes"], [f"sudo /usr/sbin/dkms autoinstall -k {K2}"])
        self.assertIs(p["reparacion"]["root"], True)
        self.assertIsNone(p["reparacion"]["copia"])
        self.assertEqual([x["id"] for x in doc["problemas"]], ["graficos.nvidia_modulo_kernel"])

    def test_nvidia_sin_cabeceras_no_ofrece_compilar(self):
        self.archivo("proc/sys/kernel/osrelease", K2 + "\n")
        self.archivo("proc/modules", "i915 1 0 - Live 0x0\n")
        self.borrar("sys/module/nvidia")
        p = self.problema(self.comprobar(), "graficos.nvidia_modulo_kernel")
        self.assertIsNone(p["reparacion"])
        self.assertTrue(any(f"linux-headers-{K2}" in c for c in p["causas_probables"]))

    def test_nvidia_secure_boot_clave_sin_registrar(self):
        self.archivo("proc/modules", "i915 1 0 - Live 0x0\n")
        self.borrar("sys/module/nvidia")
        self.resp["mokutil --test-key"] = res("/var/lib/dkms/mok.pub is not enrolled\n")
        self.resp["mokutil --list-new"] = res("")
        p = self.problema(self.comprobar(), "graficos.nvidia_mok")
        self.assertEqual(p["titulo"], "NVIDIA SECURE BOOT WARNING")
        self.assertTrue(any("jaime0-nvidia registrar" in r for r in p["recomendacion"]))

    def test_nvidia_proximo_nucleo_sin_modulo(self):
        self.archivo(f"lib/modules/{K2}/build/Makefile", "x")
        self.archivo(f"boot/vmlinuz-{K2}", "x")
        doc = self.comprobar()
        p = self.problema(doc, "graficos.nvidia_nucleo_nuevo")
        self.assertEqual(p["reparacion"]["ordenes"], [f"sudo /usr/sbin/dkms autoinstall -k {K2}"])
        self.assertEqual(self.comprobacion(doc, "graficos.nvidia")["estado"], "WARNING")

    def test_unidades_fallidas_con_lineas_del_diario(self):
        self.resp["systemctl --user --failed"] = res("sincro.service loaded failed failed Sincronizar notas\n")
        self.resp["systemctl --user show sincro.service"] = unidad("failed", "enabled", "exit-code")
        self.resp["journalctl --user -b -u sincro.service"] = res(
            "2026-11-16T10:00:00+0100 portatil-de-maria sincro[321]: no existe /home/maria/Notas\n"
            "2026-11-16T10:00:01+0100 portatil-de-maria systemd[900]: sincro.service: Failed with result 'exit-code'.\n")
        self.resp["systemctl --failed"] = res("cups.service loaded failed failed CUPS Scheduler\n"
                                              "NetworkManager.service loaded failed failed Network Manager\n")
        self.resp["systemctl show cups.service"] = unidad("failed", "enabled", "core-dump")
        self.resp["journalctl -b -u cups.service"] = res("", error="Hint: You are currently not seeing messages "
                                                                   "from other users and the system.\n")
        self.resp["systemctl show NetworkManager.service"] = unidad("failed", "enabled", "exit-code")
        doc = self.comprobar()
        u = self.problema(doc, "sistema.unidad_usuario.sincro.service")
        self.assertEqual((u["gravedad"], u["titulo"]), ("ERROR", "SYSTEMD UNIT ERROR"))
        self.assertIn("Diario: 2026-11-16T10:00:00+0100 sincro[321]: no existe ~/Notas", u["detectado"])
        self.assertIn("Resultado: exit-code", u["detectado"])
        self.assertEqual(u["reparacion"]["ordenes"], ["systemctl --user reset-failed sincro.service",
                                                      "systemctl --user restart sincro.service"])
        self.assertIs(u["reparacion"]["root"], False)
        s = self.problema(doc, "sistema.unidad_sistema.cups.service")
        self.assertIsNone(s["reparacion"])
        self.assertIn("Diario de cups.service: sin líneas visibles (el diario del sistema necesita --sudo)", s["detectado"])
        # NetworkManager no se repite como unidad generica: lo explica (y repara) su comprobacion.
        self.assertIsNone(self.problema(doc, "sistema.unidad_sistema.NetworkManager.service"))
        nm = self.problema(doc, "conectividad.networkmanager")
        self.assertEqual(nm["gravedad"], "ERROR")
        self.assertEqual(nm["reparacion"]["ordenes"][-1], "sudo /usr/bin/systemctl restart NetworkManager.service")
        texto = json.dumps(doc, ensure_ascii=False)
        for secreto in ("maria", "portatil", "BAT-SERIE"):
            self.assertNotIn(secreto, texto)

    def test_diario_sin_permiso_no_es_sin_errores(self):
        self.resp["journalctl -b -p err -o json"] = res(
            "", error="Hint: You are currently not seeing messages from other users and the system.\n")
        c = self.comprobacion(self.comprobar(), "sistema.errores_arranque")
        self.assertEqual(c["estado"], "NO_DISPONIBLE")
        self.assertIn("comprobar --sudo", c["detalle"])
        self.assertIn("no quiere decir que no haya errores", c["detalle"])
        self.assertNotIn("Ningún mensaje", c["detalle"])
        # Con --sudo pero sudo pide contrasena: sigue sin poder leerse, y se dice por que.
        self.resp["sudo journalctl -b -p err -o json"] = D.Resultado(
            False, "", "sudo: a password is required", "sudo necesita contraseña (no se pide desde el programa)")
        c = self.comprobacion(self.comprobar("--sudo"), "sistema.errores_arranque")
        self.assertEqual(c["estado"], "NO_DISPONIBLE")
        self.assertIn("sudo -v", c["detalle"])
        # Con --sudo y sudo sin contrasena: se lee y se interpreta.
        self.resp["sudo journalctl -b -p err -o json"] = res(
            '{"PRIORITY":"3","SYSLOG_IDENTIFIER":"kernel","MESSAGE":"ACPI BIOS Error (bug)"}\n'
            '{"PRIORITY":"2","SYSLOG_IDENTIFIER":"kernel","MESSAGE":"watchdog: BUG: soft lockup"}\n')
        doc = self.comprobar("--sudo")
        self.assertEqual(self.comprobacion(doc, "sistema.errores_arranque")["estado"], "WARNING")
        self.assertEqual(self.problema(doc, "sistema.mensajes_criticos")["detectado"], ["kernel: watchdog: BUG: soft lockup"])

    def test_errores_solo_de_prioridad_err_son_un_dato(self):
        self.resp["journalctl -b -p err -o json"] = res(
            '{"PRIORITY":"3","SYSLOG_IDENTIFIER":"kernel","MESSAGE":"ACPI BIOS Error (bug)"}\n')
        doc = self.comprobar()
        self.assertEqual(self.comprobacion(doc, "sistema.errores_arranque")["estado"], "INFO")
        self.assertEqual(doc["problemas"], [])

    def test_dpkg_audit_con_paquetes_rotos(self):
        self.resp["dpkg --audit"] = res(
            "The following packages are only half configured, probably due to problems\n"
            "configuring them the first time.  The configuration should be retried using\n"
            "dpkg --configure <package> or the configure menu option in dselect:\n"
            " nvidia-kernel-dkms   NVIDIA binary kernel module DKMS source\n"
            " libfoo1              Foo library\n")
        p = self.problema(self.comprobar(), "sistema.paquetes_rotos")
        self.assertEqual((p["gravedad"], p["componente"]), ("ERROR", "DPKG"))
        self.assertIn("Paquete: nvidia-kernel-dkms", p["detectado"])
        self.assertIn("Paquete: libfoo1", p["detectado"])
        self.assertIn("dpkg --audit: 2 paquetes afectados", p["detectado"])
        self.assertTrue(any(x.startswith("The following packages are only half configured") for x in p["detectado"]))
        self.assertEqual(p["reparacion"]["ordenes"], ["sudo /usr/bin/dpkg --configure -a"])

    def test_permisos_inseguros_del_ayudante(self):
        D.stat_ruta = lambda c: (types.SimpleNamespace(st_mode=0o100775, st_uid=1000, st_gid=1000)
                                 if c.endswith("jaime0-ufw-estado") else stat_root(c))
        p = self.problema(self.comprobar(), "sistema.permisos")
        self.assertEqual((p["gravedad"], p["titulo"]), ("CRITICAL", "PERMISSIONS CRITICAL"))
        self.assertEqual(p["detectado"], ["/usr/local/libexec/jaime0-ufw-estado: propietario uid 1000, escribible por "
                                          "el grupo 1000 (permisos 0775)"])
        self.assertEqual(p["reparacion"]["ordenes"],
                         ["sudo /usr/bin/chown -h root:root -- /usr/local/libexec/jaime0-ufw-estado",
                          "sudo /usr/bin/chmod go-w -- /usr/local/libexec/jaime0-ufw-estado"])

    def test_actualizacion_interrumpida_y_seguridad_pendiente(self):
        self.resp["jaime0-update estado --json"] = res('{"ok":true,"version_instalada":"0.4.0","interrumpida":true,'
                                                       '"en_curso":null}')
        (self.estado / "actualizaciones.json").write_text(
            '{"paquetes": 4, "seguridad": ["openssl", "libc6"], "comprobado": "2026-11-16T09:00"}', encoding="utf-8")
        doc = self.comprobar()
        u = self.problema(doc, "sistema.update_interrumpida")
        self.assertEqual(u["gravedad"], "ERROR")
        self.assertEqual(u["reparacion"]["ordenes"], ["sudo /usr/local/bin/jaime0-update recuperar"])
        s = self.problema(doc, "sistema.seguridad_pendiente")
        self.assertEqual((s["gravedad"], s["componente"]), ("WARNING", "UPDATES"))
        self.assertTrue(any("UPDATES" in r for r in s["recomendacion"]))

    def test_waybar_roto_ofrece_restaurar_con_copia(self):
        (self.casa / ".config/waybar/config.jsonc").write_text('{\n  "layer": "top"\n  "height": 30\n}\n',
                                                               encoding="utf-8")
        p = self.problema(self.comprobar(), "sistema.config_waybar")
        self.assertEqual(p["gravedad"], "ERROR")
        self.assertIn("línea 3", p["detectado"][0])
        # En Windows la ruta lleva barras invertidas (y shlex la entrecomilla); en Linux, no.
        suya = r"~[/\\]\.config[/\\]waybar[/\\]config\.jsonc"
        self.assertRegex(p["detectado"][0], "^" + suya + ": JSON no válido")
        self.assertRegex(p["reparacion"]["copia"], "^" + suya + "$")
        self.assertEqual(len(p["reparacion"]["ordenes"]), 1)
        self.assertRegex(p["reparacion"]["ordenes"][0], r"^cp /etc/skel/\.config/waybar/config\.jsonc '?" + suya + "'?$")

    def test_jsonc_comentarios_dentro_de_cadenas(self):
        texto = '{\n "a": "http://x // no es comentario", /* b */ "c": [1, 2,], // fin\n}\n'
        self.assertEqual(json.loads(D.quitar_comentarios_jsonc(texto)), {"a": "http://x // no es comentario", "c": [1, 2]})

    def test_maquina_virtual_sin_bateria_ni_wifi(self):
        for d in ("sys/bus/pci/devices", "sys/class/power_supply", "sys/class/net/wlp0s20f3", "sys/class/rfkill",
                  "sys/class/bluetooth", "sys/class/hwmon", "sys/module/nvidia", "sys/firmware", "var/lib/dkms"):
            self.borrar(d)
        self.pci("0000-00-02.0", "0x15ad", "0x0405", "0x030000")
        self.archivo("sys/class/net/enp0s3/operstate", "up\n")
        self.archivo("sys/class/net/enp0s3/device/.x")
        self.archivo("proc/modules", "vmwgfx 1 0 - Live 0x0\n")
        self.archivo("sys/class/drm/card0-Virtual-1/status", "connected\n")
        self.resp["systemd-detect-virt"] = res("oracle\n")
        self.resp["dkms status"] = res("")
        self.resp["dpkg-query -W"] = res("", ok=False)
        self.resp["hyprctl monitors all -j"] = res('[{"name":"Virtual-1","width":1280,"height":800,"refreshRate":60}]')
        self.resp["nmcli -t -f TYPE,DEVICE connection show --active"] = res("802-3-ethernet:enp0s3\n")
        self.resp["powerprofilesctl"] = res("* balanced:\n    PlatformDriver: placeholder\n")
        doc = self.comprobar()
        self.assertEqual(doc["problemas"], [])
        for cid in ("hardware.bateria", "hardware.sensores", "graficos.nvidia", "conectividad.wifi",
                    "conectividad.bluetooth", "energia.cargador"):
            self.assertEqual(self.comprobacion(doc, cid)["estado"], "NO_APLICA", cid)
        self.assertEqual(self.comprobacion(doc, "graficos.aceleracion")["estado"], "INFO")
        self.assertIn("por software", self.comprobacion(doc, "graficos.aceleracion")["detalle"])

    def test_wifi_bloqueado_y_chip_sin_interfaz(self):
        self.archivo("sys/class/rfkill/rfkill0/soft", "1\n")
        p = self.problema(self.comprobar(), "conectividad.wifi_bloqueo_software")
        self.assertEqual(p["gravedad"], "INFO")
        self.assertEqual(p["reparacion"]["ordenes"], ["nmcli radio wifi on"])
        self.borrar("sys/class/net/wlp0s20f3")
        self.resp["journalctl -k -b"] = res(KERNEL_SANO + "iwlwifi 0000:00:14.3: Direct firmware load for "
                                                          "iwlwifi-QuZ-a0-hr-b0-77.ucode failed with error -2\n")
        p = self.problema(self.comprobar(), "conectividad.wifi_sin_interfaz")
        self.assertEqual(p["gravedad"], "WARNING")
        self.assertTrue(any("Direct firmware load" in x for x in p["detectado"]))

    def test_raiz_en_solo_lectura_y_llena(self):
        self.archivo("proc/mounts", "/dev/nvme0n1p2 / ext4 ro,relatime 0 0\n")
        D.uso_disco = lambda c: (500 * D.GIB, D.GIB // 2)
        doc = self.comprobar()
        self.assertEqual(self.problema(doc, "hardware.raiz_solo_lectura")["gravedad"], "CRITICAL")
        llena = self.problema(doc, "hardware.raiz_llena")
        self.assertEqual(llena["reparacion"]["ordenes"], ["sudo /usr/bin/apt-get clean"])

    def test_smart_con_sudo(self):
        self.resp["sudo smartctl -H -j /dev/nvme0n1"] = res('{"smart_status": {"passed": false}}', ok=False, codigo=8)
        doc = self.comprobar("--sudo")
        self.assertEqual(self.problema(doc, "hardware.smart")["gravedad"], "CRITICAL")
        self.resp["sudo smartctl -H -j /dev/nvme0n1"] = res('{"smart_status": {"passed": true}}')
        self.assertEqual(self.comprobacion(self.comprobar("--sudo"), "hardware.smart")["estado"], "OK")

    def test_una_comprobacion_rota_no_tumba_el_resto(self):
        self.resp["dpkg --audit"] = lambda: 1 / 0
        doc = self.comprobar()
        c = self.comprobacion(doc, "sistema.paquetes")
        self.assertEqual(c["estado"], "NO_DISPONIBLE")
        self.assertIn("ZeroDivisionError", c["detalle"])


class PruebasHistorialYReparar(BaseDiagnostico):
    def unidad_fallida(self, fallida=True):
        self.resp["systemctl --user --failed"] = lambda: res(
            "sincro.service loaded failed failed Sincronizar\n" if self.fallida else "")
        self.resp["systemctl --user show sincro.service"] = unidad("failed", "enabled", "exit-code")
        self.fallida = fallida

    def ejecutar_orden(self, argv):
        self.ordenes.append(argv)
        if argv[-2:] == ["restart", "sincro.service"]:
            self.fallida = False
        return 0

    def historial(self):
        rc, out = self.correr("historial", "--json")
        self.assertEqual(rc, 0)
        self.assertEqual(len(out.splitlines()), 1)
        return json.loads(out)

    def test_veces_y_resuelto(self):
        self.unidad_fallida()
        pid = "sistema.unidad_usuario.sincro.service"
        self.comprobar()
        doc = self.comprobar()
        self.assertEqual(self.problema(doc, pid)["veces"], 2)
        # Si la comprobacion no se puede hacer, el problema no se da por resuelto.
        self.resp["systemctl --user --failed"] = falta("systemctl")
        self.comprobar()
        h = self.historial()
        self.assertEqual(h["problemas"][0]["estado"], "activo")
        self.unidad_fallida(False)
        self.comprobar()
        h = self.historial()
        self.assertEqual(set(h), {"ok", "problemas", "ejecuciones"})
        p = h["problemas"][0]
        self.assertEqual(set(p), {"id", "titulo", "gravedad", "primera_vez", "ultima_vez", "veces", "estado",
                                  "resuelto_en", "reparaciones"})
        self.assertEqual((p["id"], p["estado"], p["veces"]), (pid, "resuelto", 2))
        self.assertIsInstance(p["resuelto_en"], int)
        self.assertEqual(len(h["ejecuciones"]), 4)
        self.assertEqual(set(h["ejecuciones"][0]), {"t", "resumen"})
        rc, out = self.correr("historial", "--json", "-n", "2")
        self.assertEqual(len(json.loads(out)["ejecuciones"]), 2)
        # Vuelve a aparecer: activo otra vez, sin fecha de resolucion y conservando la primera vez.
        self.unidad_fallida()
        self.comprobar()
        p2 = self.historial()["problemas"][0]
        self.assertEqual((p2["estado"], p2["resuelto_en"], p2["veces"], p2["primera_vez"]),
                         ("activo", None, 3, p["primera_vez"]))

    def test_historial_con_limite_de_lineas(self):
        with mock.patch.object(D, "LIMITE_EJECUCIONES", 3):
            for _ in range(5):
                self.comprobar()
        lineas = (self.estado / "diagnosticos.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lineas), 3)
        self.assertEqual(set(json.loads(lineas[0])), {"t", "duracion", "resumen", "problemas"})

    def test_reparar_con_confirmacion(self):
        self.unidad_fallida()
        self.comprobar()
        rc, out = self.correr("reparar", "sistema.unidad_usuario.sincro.service", entrada=["s"])
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.ordenes, [["systemctl", "--user", "reset-failed", "sincro.service"],
                                        ["systemctl", "--user", "restart", "sincro.service"]])
        self.assertIn("$ systemctl --user restart sincro.service", out)
        self.assertIn("Resuelto", out)
        p = self.historial()["problemas"][0]
        self.assertEqual(p["estado"], "resuelto")
        self.assertEqual([r["resultado"] for r in p["reparaciones"]], ["resuelto"])

    def test_reparar_que_no_resuelve(self):
        self.unidad_fallida()
        self.ejecutar_orden = lambda argv: self.ordenes.append(argv) or 1
        D.ejecutar_orden = self.ejecutar_orden
        rc, out = self.correr("reparar", "sistema.unidad_usuario.sincro.service", entrada=["s"])
        self.assertEqual(rc, 1)
        self.assertEqual(len(self.ordenes), 1)  # se para en la primera orden que falla
        self.assertIn("No resuelto", out)
        self.assertEqual(self.historial()["problemas"][0]["reparaciones"][0]["resultado"], "fallo")

    def test_reparar_sin_terminal_no_hace_nada(self):
        self.unidad_fallida()
        D.terminal_interactiva = lambda: False
        rc, out = self.correr("reparar", "sistema.unidad_usuario.sincro.service")
        self.assertEqual(rc, 1)
        self.assertEqual(self.ordenes, [])
        self.assertIn("Sin terminal interactiva", out)
        self.assertIn("systemctl --user restart sincro.service", out)  # muestra las ordenes exactas

    def test_reparar_cancelado(self):
        self.unidad_fallida()
        for respuesta in ("", "n", "no"):
            rc, out = self.correr("reparar", "sistema.unidad_usuario.sincro.service", entrada=[respuesta])
            self.assertEqual(rc, 1)
            self.assertIn("Cancelado", out)
        self.assertEqual(self.ordenes, [])

    def test_reparar_problema_ya_resuelto(self):
        self.unidad_fallida(False)
        rc, out = self.correr("reparar", "sistema.unidad_usuario.sincro.service", entrada=["s"])
        self.assertEqual(rc, 0)
        self.assertIn("ya no se detecta", out)
        self.assertEqual(self.ordenes, [])

    def test_reparar_problema_sin_reparacion(self):
        (self.estado / "actualizaciones.json").write_text('{"paquetes": 1, "seguridad": ["openssl"]}', encoding="utf-8")
        rc, out = self.correr("reparar", "sistema.seguridad_pendiente", entrada=["s"])
        self.assertEqual(rc, 1)
        self.assertIn("no tiene reparación automática", out)
        self.assertEqual(self.ordenes, [])

    def test_reparar_con_copia_del_archivo_del_usuario(self):
        config = self.casa / ".config/waybar/config.jsonc"
        config.write_text('{ "layer": "top" "roto": 1 }', encoding="utf-8")

        def cp(argv):
            self.ordenes.append(argv)
            shutil.copyfile(self.raiz / argv[1].lstrip("/"), argv[2])
            return 0
        D.ejecutar_orden = cp
        rc, out = self.correr("reparar", "sistema.config_waybar", entrada=["s"])
        self.assertEqual(rc, 0, out)
        copias = list(config.parent.glob("config.jsonc.antes-de-reparar-*"))
        self.assertEqual(len(copias), 1)
        self.assertEqual(copias[0].read_text(encoding="utf-8"), '{ "layer": "top" "roto": 1 }')
        self.assertEqual(config.read_text(encoding="utf-8"), SKEL_WAYBAR)

    def test_reparar_id_no_valido(self):
        rc, _ = self.correr("reparar", "nada")
        self.assertEqual(rc, 2)


class PruebasSubordenesSinSistema(unittest.TestCase):
    """Proceso aparte, raiz vacia y PATH vacio: nada que comprobar y nada debe fallar."""

    def setUp(self):
        self.e = Escenario()
        self.addCleanup(self.e.limpiar)
        self.estado = self.e.tmp / "estado"

    def ejecutar(self, *args):
        env = {k: v for k, v in os.environ.items()
               if k.upper() not in ("PATH", "HYPRLAND_INSTANCE_SIGNATURE", "XDG_RUNTIME_DIR", "XDG_STATE_HOME",
                                    "XDG_CONFIG_HOME")}
        env.update(JAIME0_RAIZ=str(self.e.raiz), HOME=str(self.e.casa), USERPROFILE=str(self.e.casa),
                   PATH=str(self.e.vacio), PYTHONIOENCODING="utf-8", USER="maria", LOGNAME="maria",
                   JAIME0_ESTADO=str(self.estado))
        r = subprocess.run([sys.executable, str(PROGRAMA), *args], env=env, capture_output=True, text=True,
                           encoding="utf-8", timeout=60, stdin=subprocess.DEVNULL)
        return r.returncode, r.stdout, r.stderr

    def test_comprobar_json_sin_nada(self):
        rc, out, err = self.ejecutar("comprobar", "--json")
        self.assertEqual(rc, 0, err)
        self.assertNotIn("Traceback", err)
        self.assertEqual(len(out.splitlines()), 1)
        doc = json.loads(out)
        self.assertIs(doc["ok"], True)
        self.assertEqual(doc["problemas"], [])
        self.assertGreater(doc["resumen"]["NO_DISPONIBLE"], 0)
        rc, out, err = self.ejecutar("historial", "--json")
        self.assertEqual(rc, 0, err)
        self.assertEqual(len(json.loads(out)["ejecuciones"]), 1)

    def test_comprobar_en_texto_y_opciones(self):
        rc, out, err = self.ejecutar("comprobar")
        self.assertEqual(rc, 0, err)
        for area in ("HARDWARE", "SYSTEM", "GRAPHICS", "CONNECTIVITY", "POWER"):
            self.assertRegex(out, rf"(?m)^{area}$")
        self.assertIn("Ningún problema detectado", out)
        rc, out, _ = self.ejecutar("comprobar", "--json", "--borrar")
        self.assertEqual(rc, 2)
        self.assertIs(json.loads(out)["ok"], False)

    def test_reparar_sin_poder_comprobar_no_hace_nada(self):
        rc, out, err = self.ejecutar("reparar", "sistema.paquetes_rotos")
        self.assertEqual(rc, 0, err)
        self.assertIn("No se detecta ahora, pero algunas comprobaciones de SYSTEM no se pudieron hacer", out)
        self.assertIn("No se hace nada", out)


if __name__ == "__main__":
    unittest.main()

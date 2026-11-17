#!/bin/bash
# Verificacion: jaime0-update dentro del chroot que deja lb build. Ejecutar con sudo desde
# la carpeta de trabajo. Corre las pruebas del actualizador con el python3 de la imagen.
export LC_ALL=C
FALLOS=0; OKS=0
ok()    { echo "[OK]    $1"; OKS=$((OKS + 1)); }
fallo() { echo "[FALLO] $1"; FALLOS=$((FALLOS + 1)); }

[ "$(id -u)" -eq 0 ] || { echo "Ejecuta con sudo."; exit 1; }
[ -d chroot/etc/apt ] || { echo "No existe ./chroot."; exit 1; }

echo "== Archivos =="
V=$(cat chroot/usr/share/jaime0/version 2>/dev/null)
[ -n "$V" ] && ok "version $V" || fallo "falta /usr/share/jaime0/version"
[ "$V" = "$(cat config/includes.chroot_after_packages/usr/share/jaime0/version)" ] && ok "version igual a la del repositorio" || fallo "version distinta de la del repositorio"
grep -qx "VERSION_ID=$V" chroot/usr/lib/os-release && ok "os-release: VERSION_ID=$V" || fallo "os-release sin VERSION_ID"
[ "$(stat -c '%a %U' chroot/usr/local/bin/jaime0-update)" = "755 root" ] && ok "jaime0-update 755 root" || fallo "permisos de jaime0-update"
chroot chroot python3 -c 'import json; m=json.load(open("/usr/share/jaime0/manifiesto.json")); print(m["version"])' 2>/dev/null | grep -qx "$V" && ok "manifiesto instalado de $V" || fallo "manifiesto instalado"
cmp -s chroot/usr/share/jaime0/manifiesto.json chroot/var/lib/jaime0/manifiesto-instalacion.json && ok "manifiesto de instalacion" || fallo "manifiesto de instalacion"
[ "$(stat -c '%a' chroot/var/backups/jaime0)" = "700" ] && ok "copias solo para root" || fallo "permisos de /var/backups/jaime0"
grep -q 'BEGIN PUBLIC KEY' chroot/usr/share/jaime0/firma-actualizaciones.pem && ! grep -rqs 'PRIVATE KEY' chroot/usr/share/jaime0 chroot/etc/jaime0 && ok "solo clave publica" || fallo "clave de firma"
grep -qx 'canal=stable' chroot/etc/jaime0/update.conf && ok "canal por defecto: stable" || fallo "canal por defecto"
command -v openssl >/dev/null && chroot chroot openssl version >/dev/null 2>&1 && ok "openssl en la imagen" || fallo "falta openssl"

echo "== Manifiesto frente al chroot =="
# Cada archivo del manifiesto debe estar en la imagen tal cual: si no, la primera
# actualizacion lo veria como personalizado.
R=$(chroot chroot python3 - <<'PY'
import hashlib, json, os
m = json.load(open("/usr/share/jaime0/manifiesto.json"))
mal = [r for r, d in m["archivos"].items()
       if not os.path.isfile("/" + r) or hashlib.sha256(open("/" + r, "rb").read()).hexdigest() != d["sha256"]]
print(len(m["archivos"]), " ".join(mal))
PY
)
N=${R%% *}; MAL=${R#* }; [ "$MAL" = "$R" ] && MAL=""
[ -z "$MAL" ] && ok "$N archivos del manifiesto identicos en la imagen" || fallo "distintos en la imagen: $MAL"

echo "== Servicio, ayudante y politica (rutas gestionadas) =="
[ "$(stat -c '%a %U:%G' chroot/usr/local/libexec/jaime0-ufw-estado)" = "755 root:root" ] && ok "ayudante 755 root:root" || fallo "permisos del ayudante"
[ "$(stat -c '%a %U:%G' chroot/usr/share/polkit-1/actions/es.jaime0.ufw-estado.policy)" = "644 root:root" ] && ok "politica 644 root:root" || fallo "permisos de la politica"
[ -z "$(find chroot/usr/local/lib/jaime0 \( -type f ! -perm 644 \) -o \( -type d ! -perm 755 \) -o ! -user root)" ] && ok "paquete del servicio root 755/644" || fallo "permisos del paquete del servicio"
! grep -q '__pycache__\|\.pyc"' chroot/usr/share/jaime0/manifiesto.json && ok "sin bytecode en el manifiesto" || fallo "bytecode en el manifiesto"
grep -q '"usr/local/lib/jaime0/jaime0_servicio/servicio.py"' chroot/usr/share/jaime0/manifiesto.json && ok "el manifiesto incluye el servicio" || fallo "servicio fuera del manifiesto"

echo "== Aviso diario =="
[ -L chroot/etc/systemd/user/timers.target.wants/actualizaciones-aviso.timer ] && ok "temporizador activado para todos" || fallo "temporizador no activado"
grep -qx 'ExecStart=-/usr/local/bin/jaime0-update comprobar --notificar --silencioso' chroot/usr/lib/systemd/user/actualizaciones-aviso.service && ok "el aviso tambien comprueba ZYRON" || fallo "servicio de aviso sin jaime0-update"
! grep -E '^ExecStart' chroot/usr/lib/systemd/user/actualizaciones-aviso.service | grep -qE 'actualizar|_sistema|--si( |$)' && ok "el aviso nunca instala" || fallo "el aviso podria instalar"
[ ! -e chroot/usr/lib/systemd/user/jaime0-update-aviso.timer ] && ok "sin la unidad retirada jaime0-update-aviso" || fallo "queda jaime0-update-aviso"

echo "== Ordenes =="
chroot chroot /usr/local/bin/jaime0-update --help >/dev/null && ok "jaime0-update --help" || fallo "--help"
chroot chroot /usr/local/bin/jaime0-update canal | grep -q 'stable' && ok "jaime0-update canal" || fallo "canal"
chroot chroot /usr/local/bin/jaime0-update estado | grep -q "$V" && ok "jaime0-update estado" || fallo "estado"

echo "== Pruebas del actualizador con el python3 de la imagen =="
mkdir -p chroot/tmp/pruebas-actualizador/config/includes.chroot_after_packages/usr/local/bin chroot/tmp/pruebas-actualizador/pruebas
cp pruebas/test_jaime0_update.py chroot/tmp/pruebas-actualizador/pruebas/
cp config/includes.chroot_after_packages/usr/local/bin/jaime0-update config/includes.chroot_after_packages/usr/local/bin/actualizaciones \
    chroot/tmp/pruebas-actualizador/config/includes.chroot_after_packages/usr/local/bin/
# Como usuario sin privilegios: con root el modo de prueba se ignora a proposito.
SALIDA=$(chroot chroot setpriv --reuid=65534 --regid=65534 --clear-groups env HOME=/tmp \
    python3 -m unittest discover -s /tmp/pruebas-actualizador/pruebas 2>&1)
echo "$SALIDA" | tail -3
echo "$SALIDA" | grep -q '^OK' && ok "pruebas del actualizador" || fallo "pruebas del actualizador"
rm -rf chroot/tmp/pruebas-actualizador

echo "RESULTADO: ${FALLOS} fallo(s), ${OKS} correctos"
[ "$FALLOS" -eq 0 ]

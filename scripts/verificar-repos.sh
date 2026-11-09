#!/bin/bash
export LC_ALL=C
FALLOS=0

ok()    { echo "[OK]    $1"; }
fallo() { echo "[FALLO] $1"; FALLOS=$((FALLOS + 1)); }

if [ "$(id -u)" -ne 0 ]; then
    echo "Ejecuta este script con sudo."
    exit 1
fi

if [ ! -d chroot/etc/apt ]; then
    echo "No existe ./chroot. Ejecuta primero lb bootstrap y lb chroot."
    exit 1
fi

echo "== Repositorios finales =="
grep -rhEv '^[[:space:]]*(#|$)' chroot/etc/apt/sources.list chroot/etc/apt/sources.list.d/ 2>/dev/null

if grep -rqs 'forky' chroot/etc/apt/sources.list chroot/etc/apt/sources.list.d/; then
    ok "Repositorio forky presente"
else
    fallo "Repositorio forky ausente"
fi

for RAMA in main contrib non-free non-free-firmware; do
    if grep -rqsE "(^|[[:space:]])${RAMA}([[:space:]]|$)" chroot/etc/apt/sources.list chroot/etc/apt/sources.list.d/; then
        ok "Rama ${RAMA} presente"
    else
        fallo "Rama ${RAMA} ausente"
    fi
done

echo "== Paquetes =="
for PAQUETE in $(cat config/package-lists/base.list.chroot config/package-lists/servicios.list.chroot); do
    if chroot chroot dpkg-query -W -f='${Status}' "${PAQUETE}" 2>/dev/null | grep -qE " ok installed"; then
        ok "${PAQUETE}"
    else
        fallo "${PAQUETE} no instalado"
    fi
done

echo "== Archivos clave =="
for RUTA in /usr/bin/nmtui /usr/bin/lxpolkit; do
    if [ -x "chroot${RUTA}" ]; then
        ok "${RUTA}"
    else
        fallo "${RUTA} no encontrado"
    fi
done

echo "== Servicios =="
for UNIDAD in NetworkManager.service bluetooth.service; do
    if [ "$(chroot chroot systemctl is-enabled "${UNIDAD}" 2>/dev/null)" = "enabled" ]; then
        ok "${UNIDAD}"
    else
        fallo "${UNIDAD} no habilitado"
    fi
done

for UNIDAD in pipewire.socket pipewire-pulse.socket wireplumber.service; do
    if [ "$(chroot chroot systemctl --global is-enabled "${UNIDAD}" 2>/dev/null)" = "enabled" ]; then
        ok "${UNIDAD} (usuario)"
    else
        fallo "${UNIDAD} (usuario) no habilitado"
    fi
done

echo "== Bloqueo de APT =="
cp /etc/resolv.conf chroot/etc/resolv.conf
chroot chroot apt-get -qq update

for PAQUETE in gnome-shell plasma-desktop xfce4 cinnamon mate-desktop-environment lxde nautilus dolphin; do
    if chroot chroot apt-cache policy "${PAQUETE}" | grep -q 'Candidate: (none)'; then
        ok "${PAQUETE} bloqueado"
    else
        fallo "${PAQUETE} NO bloqueado"
    fi
done

echo "== Simulacion: hyprland =="
if chroot chroot apt-get -s -qq install hyprland xdg-desktop-portal-hyprland qt6-wayland >/dev/null; then
    ok "Dependencias de Hyprland resolubles"
else
    fallo "Dependencias de Hyprland no resolubles"
fi

echo
echo "RESULTADO: ${FALLOS} fallo(s)"
[ "${FALLOS}" -eq 0 ]

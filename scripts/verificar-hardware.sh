#!/bin/bash
# Comprueba lo necesario para arrancar en equipos fisicos: arranque seguro, firmware,
# audio de portatil, respaldo sin GPU y el fijado de Waybar.
# Ejecutar con sudo desde la carpeta de trabajo, despues de lb build.
FALLOS=0; OK=0
ok()    { echo "[OK]    $1"; OK=$((OK+1)); }
fallo() { echo "[FALLO] $1"; FALLOS=$((FALLOS+1)); }
instalado() { chroot chroot dpkg-query -W -f='${Status}' "$1" 2>/dev/null | grep -qE " ok installed"; }

echo "== Arranque seguro =="
# live-build los retira de chroot/ al generar el arranque: se comprueba la imagen final.
for F in usr/lib/shim/shimx64.efi.signed usr/lib/grub/x86_64-efi-signed/grubx64.efi.signed; do
    unsquashfs -l binary/live/filesystem.squashfs | grep -q "squashfs-root/$F" && ok "$F en la imagen" || fallo "$F ausente en la imagen"
done
if [ -d binary/EFI ]; then
    B=$(find binary/EFI -iname 'bootx64.efi' | head -1)
    G=$(find binary/EFI -iname 'grubx64.efi' | head -1)
    [ -n "$B" ] && [ -n "$G" ] && ok "medio con shim y GRUB en EFI/boot" || fallo "faltan bootx64/grubx64 en EFI"
fi

echo "== Firmware y audio de portatil =="
for P in firmware-iwlwifi firmware-realtek firmware-atheros firmware-brcm80211 firmware-amd-graphics firmware-misc-nonfree firmware-sof-signed bluez-firmware alsa-ucm-conf alsa-topology-conf libmtp-runtime; do
    instalado "$P" && ok "$P" || fallo "$P ausente"
done
for P in libgl1-mesa-dri mesa-vulkan-drivers libegl-mesa0; do instalado "$P" && ok "$P" || fallo "$P ausente"; done

echo "== Respaldo si no hay GPU =="
[ -x chroot/usr/local/bin/iniciar-sesion ] && ok "iniciar-sesion ejecutable" || fallo "iniciar-sesion"
sh -n chroot/usr/local/bin/iniciar-sesion && ok "iniciar-sesion sin errores de sintaxis" || fallo "sintaxis de iniciar-sesion"
grep -q -- '--cmd iniciar-sesion' chroot/etc/greetd/config.toml && ok "el acceso usa iniciar-sesion" || fallo "config.toml"
grep -q 'command = "iniciar-sesion"' chroot/usr/lib/live/config/0086-greetd-vivo && ok "el vivo usa iniciar-sesion" || fallo "0086-greetd-vivo"
grep -q 'GRUB_CMDLINE_LINUX_RECOVERY="nomodeset"' chroot/etc/default/grub.d/90-hypr.cfg && ok "recuperacion con nomodeset" || fallo "recuperacion"
if [ -f binary/boot/grub/grub.cfg ]; then
    grep -q 'Modo seguro' binary/boot/grub/grub.cfg && ok "menu con Modo seguro" || fallo "menu sin Modo seguro"
    grep -A3 'Modo seguro' binary/boot/grub/grub.cfg | grep -q nomodeset && ok "Modo seguro usa nomodeset" || fallo "Modo seguro sin nomodeset"
fi

echo "== Actualizaciones de Waybar =="
chroot chroot apt-mark showhold | grep -qx waybar && ok "waybar retenido" || fallo "waybar sin retener"
grep -q 'Pin-Priority: 1001' chroot/etc/apt/preferences.d/97-waybar-local.pref && ok "waybar fijado" || fallo "preferencia de waybar"

echo "== Sesion limpia =="
grep -q "^CrashAction=reboot" chroot/etc/systemd/system.conf.d/10-reiniciar-si-falla.conf && ok "reinicio ante fallo de systemd" || fallo "CrashAction"
for S in systemd-user polkit-1; do [ -s "chroot/etc/pam.d/$S" ] && ok "PAM de $S en /etc/pam.d" || fallo "falta /etc/pam.d/$S"; done
grep -q 'bluetooth' chroot/etc/live/config.conf.d/10-grupos.conf && ! grep -qE 'powerdev|scanner|debian-tor' chroot/etc/live/config.conf.d/10-grupos.conf && ok "grupos del usuario en vivo existentes" || fallo "grupos en vivo"

echo "== Portatil y discos =="
R=$(grep -rIl 'thermal_zone' chroot/etc/skel/.config 2>/dev/null)
[ -z "$R" ] && ok "sin sensor de temperatura fijo" || fallo "sensor fijo en: $R"
R=$(grep -rIlE '/dev/(sd[a-z]|nvme)' chroot/etc/calamares chroot/usr/local/sbin 2>/dev/null)
[ -z "$R" ] && ok "instalador sin discos escritos a mano" || fallo "disco fijo en: $R"

echo
echo "RESULTADO: ${FALLOS} fallo(s), ${OK} correctos"
[ "$FALLOS" -eq 0 ]

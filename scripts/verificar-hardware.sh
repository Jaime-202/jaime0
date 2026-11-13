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

echo "== Firmware, energia y audio del portatil (Acer Nitro AN515-55) =="
for P in firmware-iwlwifi firmware-intel-graphics firmware-intel-sound firmware-intel-misc firmware-sof-signed firmware-nvidia-gsp intel-microcode intel-media-va-driver-non-free power-profiles-daemon thermald alsa-ucm-conf alsa-topology-conf libmtp-runtime; do
    instalado "$P" && ok "$P" || fallo "$P ausente"
done
for P in libgl1-mesa-dri mesa-vulkan-drivers libegl-mesa0; do instalado "$P" && ok "$P" || fallo "$P ausente"; done
# Solo el firmware de este equipo: nada del resto de fabricantes.
for P in firmware-brcm80211 firmware-amd-graphics firmware-atheros firmware-qcom-soc firmware-mediatek amd64-microcode; do
    instalado "$P" && fallo "$P no deberia estar" || ok "$P ausente"
done

echo "== NVIDIA en modo offload =="
for P in nvidia-kernel-dkms nvidia-driver-libs libnvidia-egl-wayland1 nvidia-vulkan-icd nvidia-smi mokutil linux-headers-amd64; do
    instalado "$P" && ok "$P" || fallo "$P ausente"
done
instalado xserver-xorg-video-nvidia && fallo "xserver-xorg-video-nvidia (arrastra Xorg)" || ok "sin el controlador de Xorg de NVIDIA"
for D in chroot/lib/modules/*/; do
    K=$(basename "$D")
    chroot chroot dkms status -k "$K" | grep -q ': installed' && ok "modulo de NVIDIA compilado para $K" || fallo "modulo de NVIDIA sin compilar para $K"
done
ls chroot/var/lib/dkms/mok.key chroot/var/lib/dkms/mok.pub >/dev/null 2>&1 && fallo "clave de DKMS dentro de la imagen" || ok "sin clave de firma en la imagen"
! grep -rqs 'PRIVATE KEY' chroot/var/lib/dkms chroot/etc && ok "ninguna clave privada en /var/lib/dkms ni /etc" || fallo "clave privada en la imagen"
grep -q 'options nvidia-current NVreg_DynamicPowerManagement=0x02' chroot/etc/modprobe.d/jaime0-nvidia.conf && ok "ahorro de energia de NVIDIA" || fallo "jaime0-nvidia.conf"
[ -s chroot/etc/udev/rules.d/80-jaime0-nvidia-pm.rules ] && ok "reglas udev de energia" || fallo "reglas udev de energia"
for S in jaime0-nvidia prime-run; do
    [ -x "chroot/usr/local/bin/$S" ] && sh -n "chroot/usr/local/bin/$S" && ok "$S" || fallo "$S"
done
grep -q 'jaime0-nvidia recompilar' chroot/etc/calamares/modules/shellprocess_nvidia.conf && grep -q 'shellprocess@nvidia' chroot/etc/calamares/settings.conf && ok "el instalador firma el modulo" || fallo "paso shellprocess@nvidia"

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

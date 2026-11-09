#!/bin/bash
# Verificacion: . Ejecutar con sudo desde ~/isolab, con ./chroot construido.
export LC_ALL=C
FALLOS=0
PENDIENTES=0
LUA=/etc/skel/.config/hypr/hyprland.lua

ok()        { echo "[OK]    $1"; }
fallo()     { echo "[FALLO] $1"; FALLOS=$((FALLOS + 1)); }
pendiente() { echo "[PEND]  $1"; PENDIENTES=$((PENDIENTES + 1)); }
instalado() { chroot chroot dpkg-query -W -f='${Status}' "$1" 2>/dev/null | grep -qE " ok installed"; }

[ "$(id -u)" -eq 0 ] || { echo "Ejecuta con sudo."; exit 1; }
[ -d chroot/etc/apt ] || { echo "No existe ./chroot."; exit 1; }

echo "== Paquetes de grafico.list.chroot =="
for P in $(cat config/package-lists/grafico.list.chroot); do
    if instalado "$P"; then ok "$P"; else fallo "$P no instalado"; fi
done

echo "== Paquetes que no deben estar =="
for P in xserver-xorg xserver-xorg-core gnome-shell plasma-desktop plasma-workspace xfce4 xfce4-session cinnamon cinnamon-desktop-environment mate-desktop-environment mate-session-manager lxde lxde-core lxsession nautilus dolphin; do
    if instalado "$P"; then fallo "$P esta instalado"; else ok "$P ausente"; fi
done

echo "== Archivos =="
for F in "$LUA" /usr/local/bin/captura-area /etc/greetd/config.toml /usr/lib/live/config/0086-greetd-vivo /etc/default/grub.d/90-hypr.cfg /usr/share/plymouth/themes/jaime0/jaime0.plymouth; do
    if [ -f "chroot$F" ]; then ok "$F"; else fallo "$F no existe"; fi
done
[ -x chroot/usr/local/bin/captura-area ] && ok "captura-area ejecutable" || fallo "captura-area sin permiso de ejecucion"
sh -n chroot/usr/local/bin/captura-area && ok "captura-area: sintaxis" || fallo "captura-area: sintaxis"
for F in "$LUA" /usr/local/bin/captura-area /etc/greetd/config.toml /usr/lib/live/config/0086-greetd-vivo; do
    if grep -q $'\r' "chroot$F"; then fallo "$F tiene CRLF"; else ok "$F con LF"; fi
done

echo "== Hyprland --verify-config (usuario sin privilegios) =="
rm -rf chroot/tmp/vs3; mkdir -p chroot/tmp/vs3/xdg chroot/tmp/vs3/home
cp "chroot$LUA" chroot/tmp/vs3/hyprland.lua
sed 's/size              = 5/sizeXX = 5/' "chroot$LUA" > chroot/tmp/vs3/roto.lua
chown -R nobody:nogroup chroot/tmp/vs3; chmod 700 chroot/tmp/vs3/xdg
H="chroot --userspec=nobody:nogroup chroot env XDG_RUNTIME_DIR=/tmp/vs3/xdg HOME=/tmp/vs3/home Hyprland --verify-config --config"
SALIDA=$($H /tmp/vs3/hyprland.lua 2>&1); RC=$?
echo "$SALIDA" | tail -n 2
if [ $RC -eq 0 ] && echo "$SALIDA" | grep -q '^config ok'; then ok "hyprland.lua valido"; else fallo "hyprland.lua invalido"; fi
SALIDA=$($H /tmp/vs3/roto.lua 2>&1); RC=$?
if [ $RC -ne 0 ] && echo "$SALIDA" | grep -q "unknown config key"; then ok "control negativo: detecta una opcion invalida"; else fallo "control negativo no detecto el error"; fi

echo "== Valores de la especificacion en hyprland.lua =="
for E in 'layout *= "dwindle"' 'border_size *= 2' 'rgba[(]7ab0ffff[)]' 'rgba[(]7ab0ffff[)]' 'rgba[(]7ab0ffff[)]' 'rounding *= 10' 'gaps_in *= 4' 'gaps_out *= 8' 'active_opacity *= 1.0' 'fullscreen_opacity *= 1.0' 'size *= 5' 'passes *= 2' 'new_optimizations *= true' 'xray *= false' 'enabled *= not esVirtual' 'no_hardware_cursors *= esVirtual' 'popin 85%' 'style = "slide"' 'kb_layout *= tecladoSistema[(]"XKBLAYOUT", "es"[)]' '1.0 override 1.0 override' '0.94 override 0.90 override' 'fullscreen_state_internal = 2' 'content = "video"' 'namespace = "\^waybar\$"' 'namespace = "\^rofi\$"' 'Return' 'space' '"Print"' '" [+] F1"' 'atajos-usuario.lua' 'o.description = descripcion' 'mouse:272' 'mouse:273' 'mode = "fullscreen"' 'mode = "maximized"' 'window.swap' 'for i = 1, 9' 'pavucontrol' 'blueman-manager' '/usr/bin/lxpolkit' 'aurora.jpg' 'mpv' 'vlc'; do
    if grep -qE -- "$E" "chroot$LUA"; then ok "contiene: $E"; else fallo "falta: $E"; fi
done
if grep -q windowrulev2 "chroot$LUA"; then fallo "usa windowrulev2"; else ok "sin windowrulev2"; fi

echo "== Bloqueos de APT en el sistema final =="
for F in 98-bloqueo-xorg.pref 99-bloqueo-escritorios.pref; do
    if [ -f "chroot/etc/apt/preferences.d/$F" ]; then ok "$F"; else fallo "$F no esta en el sistema final"; fi
done

echo "== Binarios de autostart y atajos =="
for B in kitty thunar grim slurp wl-copy wl-paste cliphist notify-send xdg-user-dir swaybg nmtui blueman-manager gio dbus-update-activation-environment start-hyprland atajos menu-energia notificaciones-waybar dunstctl; do
    if chroot chroot sh -c "command -v $B" >/dev/null; then ok "$B"; else fallo "$B no existe"; fi
done
[ -x chroot/usr/bin/lxpolkit ] && ok "agente polkit lxpolkit" || fallo "agente polkit"
instalado polkit-kde-agent-1 && fallo "polkit-kde-agent-1 sigue instalado" || ok "polkit-kde-agent-1 ausente"
for B in waybar dunst; do
    if chroot chroot sh -c "command -v $B" >/dev/null; then ok "$B"; else pendiente "$B: pendiente de instalar"; fi
done
if chroot chroot sh -c "command -v rofi" >/dev/null; then ok "rofi"; else pendiente "rofi: pendiente de instalar"; fi

echo "== Sesion y arranque =="
grep -q '^Exec=/usr/bin/start-hyprland' chroot/usr/share/wayland-sessions/hyprland.desktop && ok "sesion usa start-hyprland" || fallo "Exec de la sesion inesperado"
S=$(ls chroot/usr/share/wayland-sessions/ | tr '\n' ' '); [ "$S" = "hyprland.desktop " ] && ok "unica sesion: $S" || fallo "sesiones: $S"
[ "$(chroot chroot systemctl is-enabled greetd.service 2>/dev/null)" = "enabled" ] && ok "greetd habilitado" || fallo "greetd no habilitado"
[ "$(chroot chroot systemctl is-enabled getty@tty1.service 2>/dev/null)" = "masked" ] && ok "getty de tty1 enmascarado" || fallo "getty de tty1 sin enmascarar"
[ "$(chroot chroot systemctl get-default 2>/dev/null)" = "graphical.target" ] && ok "objetivo grafico" || fallo "objetivo no grafico"
for N in NetworkManager.service bluetooth.service; do
    [ "$(chroot chroot systemctl is-enabled $N 2>/dev/null)" = "enabled" ] && ok "$N sigue habilitado" || fallo "$N deshabilitado"
done

echo "== Plymouth =="
grep -q 'Theme=jaime0' chroot/etc/plymouth/plymouthd.conf && ok "tema en plymouthd.conf" || fallo "tema no fijado"
grep -q 'BackgroundStartColor=0x12141d' chroot/usr/share/plymouth/themes/jaime0/jaime0.plymouth && ok "fondo #12141d" || fallo "fondo incorrecto"
INITRD=$(ls -t chroot/boot/initrd.img-* | head -n 1)
if chroot chroot lsinitramfs "/boot/$(basename "$INITRD")" 2>/dev/null | grep -q 'plymouth/themes/jaime0/jaime0.plymouth'; then ok "tema dentro del initramfs"; else fallo "tema no esta en el initramfs"; fi
chroot chroot lsinitramfs "/boot/$(basename "$INITRD")" 2>/dev/null | grep -q 'scripts/live' && ok "live-boot dentro del initramfs" || fallo "live-boot no esta en el initramfs"
grep -q 'quiet splash' config/binary && ok "quiet splash en bootappend-live" || fallo "falta quiet splash en bootappend-live"
grep -q 'vt.default_red=0x12,0xc9,0x8f,0xc4,0x7a,0xa5,0x7f,0xe0,0x56,0xd9,0xa9,0xd9,0xa6,0xc2,0xa3,0xf2 vt.default_grn=0x14,0x6a,0xb3,0xad,0xb0,0x8a,0xb0,0xe4,0x5c,0x9a,0xc7,0xc7,0xcb,0xad,0xc8,0xf4 vt.default_blu=0x1d,0x78,0x9a,0x75,0xff,0xa8,0xbd,0xf2,0x78,0xa3,0xb3,0x96,0xff,0xc4,0xd2,0xfb' config/binary && ok "paleta de consola en bootappend-live" || fallo "falta la paleta de consola"
grep -q 'vt.default_red=0x12,0xc9,0x8f,0xc4,0x7a,0xa5,0x7f,0xe0,0x56,0xd9,0xa9,0xd9,0xa6,0xc2,0xa3,0xf2 vt.default_grn=0x14,0x6a,0xb3,0xad,0xb0,0x8a,0xb0,0xe4,0x5c,0x9a,0xc7,0xc7,0xcb,0xad,0xc8,0xf4 vt.default_blu=0x1d,0x78,0x9a,0x75,0xff,0xa8,0xbd,0xf2,0x78,0xa3,0xb3,0x96,0xff,0xc4,0xd2,0xfb' chroot/etc/default/grub.d/90-hypr.cfg && ok "paleta de consola en GRUB instalado" || fallo "falta la paleta de consola en GRUB"

echo "== Acceso con greetd y tuigreet =="
for P in sddm weston xvfb; do
    instalado "$P" && fallo "$P sigue instalado" || ok "$P ausente"
done
U=$(sed -n 's/^user = "\(.*\)"/\1/p' chroot/etc/greetd/config.toml | head -1)
chroot chroot getent passwd "$U" >/dev/null && ok "usuario del acceso: $U" || fallo "no existe el usuario del acceso: $U"
grep -q -- '--cmd iniciar-sesion' chroot/etc/greetd/config.toml && ok "tuigreet lanza start-hyprland" || fallo "tuigreet sin --cmd iniciar-sesion"
grep -q '^\[initial_session\]' chroot/etc/greetd/config.toml && fallo "config.toml de la imagen lleva autologin" || ok "config.toml de la imagen sin autologin"
CMD=$(sed -n 's/^command = "\(.*\)"$/\1/p' chroot/etc/greetd/config.toml | head -1)
BIN=$(echo "$CMD" | awk '{print $1}')
chroot chroot sh -c "command -v $BIN" >/dev/null && ok "$BIN existe" || fallo "$BIN no existe"
chroot chroot tuigreet --version >/dev/null 2>&1 && ok "tuigreet responde: $(chroot chroot tuigreet --version 2>&1 | head -1)" || fallo "tuigreet no responde"
chroot chroot python3 -c "import tomllib; tomllib.load(open('/etc/greetd/config.toml','rb'))" && ok "config.toml es TOML valido" || fallo "config.toml invalido"
printf '[terminal]
vt = 1
[default_session
command = "x"
' > chroot/tmp/vs3/roto.toml
chroot chroot python3 -c "import tomllib; tomllib.load(open('/tmp/vs3/roto.toml','rb'))" 2>/dev/null && fallo "control negativo TOML sin efecto" || ok "control negativo: detecta un TOML roto"
sh -n chroot/usr/lib/live/config/0086-greetd-vivo && ok "0086-greetd-vivo: sintaxis" || fallo "0086-greetd-vivo: sintaxis"
[ -x chroot/usr/lib/live/config/0086-greetd-vivo ] && ok "0086-greetd-vivo ejecutable" || fallo "0086-greetd-vivo sin permiso"

rm -rf chroot/tmp/vs3
echo
echo "RESULTADO: ${FALLOS} fallo(s), ${PENDIENTES} pendiente(s)"
[ "${FALLOS}" -eq 0 ]

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
sed 's/size              = 3/sizeXX = 3/' "chroot$LUA" > chroot/tmp/vs3/roto.lua
chown -R nobody:nogroup chroot/tmp/vs3; chmod 700 chroot/tmp/vs3/xdg
H="chroot --userspec=nobody:nogroup chroot env XDG_RUNTIME_DIR=/tmp/vs3/xdg HOME=/tmp/vs3/home Hyprland --verify-config --config"
SALIDA=$($H /tmp/vs3/hyprland.lua 2>&1); RC=$?
echo "$SALIDA" | tail -n 2
if [ $RC -eq 0 ] && echo "$SALIDA" | grep -q '^config ok'; then ok "hyprland.lua valido"; else fallo "hyprland.lua invalido"; fi
SALIDA=$($H /tmp/vs3/roto.lua 2>&1); RC=$?
if [ $RC -ne 0 ] && echo "$SALIDA" | grep -q "unknown config key"; then ok "control negativo: detecta una opcion invalida"; else fallo "control negativo no detecto el error"; fi

echo "== Valores de la especificacion en hyprland.lua =="
for E in 'layout *= "dwindle"' 'border_size *= ajuste[(]"borde", entero, 2[)]' 'rgba[(]" [.][.] acento [.][.] "cc[)]' 'rgba[(]26343aff[)]' 'rounding *= ajuste[(]"esquinas", entero, 8[)]' 'gaps_in *= ajuste[(]"separacion_interior", entero, 4[)]' 'gaps_out *= ajuste[(]"separacion_exterior", entero, 8[)]' 'active_opacity *= 1.0' 'inactive_opacity *= ajuste[(]"opacidad_inactiva", decimal, 1.0[)]' 'fullscreen_opacity *= 1.0' 'size *= 3' 'passes *= 1' 'new_optimizations *= true' 'xray *= false' 'ajuste[(]"desenfoque", sino, true[)] and not esVirtual' 'ajuste[(]"animaciones", sino, true[)] and not esVirtual' 'jaime0-ajustes generar; exec waybar' 'no_hardware_cursors *= esVirtual' 'popin 85%' 'style = "slide"' 'kb_layout *= tecladoSistema[(]"XKBLAYOUT", "es"[)]' '1.0 override 1.0 override' 'resize_on_border *= true' 'fullscreen_state_internal = 2' 'content = "video"' 'namespace = "\^rofi\$"' 'Return' 'space' '"Print"' '" [+] F1"' 'atajos-usuario.lua' 'o.description = descripcion' 'mouse:272' 'mouse:273' 'mode = "fullscreen"' 'mode = "maximized"' 'window.swap' 'for i = 1, 9' 'pavucontrol' 'blueman-manager' '/usr/bin/lxpolkit' 'jaime0.png' 'mpv' 'vlc'; do
    if grep -qE -- "$E" "chroot$LUA"; then ok "contiene: $E"; else fallo "falta: $E"; fi
done
# Los valores de la especificacion son los predeterminados de jaime0-ajustes.
PRED=chroot/usr/share/jaime0/ajustes.predeterminados
for E in '^acento = verde$' '^tema.verde = #54e58a$' '^tema.cian = #55cde0$' '^borde = 2$' '^esquinas = 8$' '^separacion_interior = 4$' '^separacion_exterior = 8$' '^opacidad_inactiva = 1.0$' '^desenfoque = si$' '^animaciones = si$' '^barra_altura = 26$' '^barra_posicion = arriba$' '^fondo = /usr/share/backgrounds/jaime0/jaime0.png$'; do
    if grep -qE -- "$E" "$PRED"; then ok "predeterminado: $E"; else fallo "predeterminado, falta: $E"; fi
done
[ -x chroot/usr/local/bin/jaime0-ajustes ] && ok "jaime0-ajustes ejecutable" || fallo "jaime0-ajustes sin permiso"
if grep -q windowrulev2 "chroot$LUA"; then fallo "usa windowrulev2"; else ok "sin windowrulev2"; fi
# La barra es opaca: no debe quedar una regla de blur para ella.
if grep -q 'namespace = "^waybar$"' "chroot$LUA"; then fallo "blur sobre la barra opaca"; else ok "sin blur detras de la barra"; fi
grep -qE '7ab0ff|a6cbff|2f3b52' "chroot$LUA" && fallo "quedan colores de la paleta azul" || ok "hyprland.lua sin la paleta azul"

echo "== Bloqueos de APT en el sistema final =="
for F in 98-bloqueo-xorg.pref 99-bloqueo-escritorios.pref; do
    if [ -f "chroot/etc/apt/preferences.d/$F" ]; then ok "$F"; else fallo "$F no esta en el sistema final"; fi
done

echo "== Binarios de autostart y atajos =="
for B in kitty thunar grim slurp wl-copy wl-paste cliphist notify-send xdg-user-dir swaybg nmtui blueman-manager gio dbus-update-activation-environment start-hyprland atajos menu-energia notificaciones-waybar dunstctl jaime0-ajustes; do
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
grep -q 'BackgroundStartColor=0x080b0d' chroot/usr/share/plymouth/themes/jaime0/jaime0.plymouth && ok "fondo #080b0d" || fallo "fondo incorrecto"
INITRD=$(ls -t chroot/boot/initrd.img-* | head -n 1)
if chroot chroot lsinitramfs "/boot/$(basename "$INITRD")" 2>/dev/null | grep -q 'plymouth/themes/jaime0/jaime0.plymouth'; then ok "tema dentro del initramfs"; else fallo "tema no esta en el initramfs"; fi
chroot chroot lsinitramfs "/boot/$(basename "$INITRD")" 2>/dev/null | grep -q 'scripts/live' && ok "live-boot dentro del initramfs" || fallo "live-boot no esta en el initramfs"
grep -q 'quiet splash' config/binary && ok "quiet splash en bootappend-live" || fallo "falta quiet splash en bootappend-live"
grep -q 'vt.default_red=0x08,0xd9,0x54,0xd9,0x6a,0xa6,0x55,0xa7,0x71,0xe8,0x86,0xe8,0x8f,0xc2,0x8a,0xee vt.default_grn=0x0b,0x62,0xe5,0xa5,0x9f,0x8a,0xcd,0xb4,0x81,0x90,0xef,0xc2,0xb9,0xaa,0xdc,0xf4 vt.default_blu=0x0d,0x5b,0x8a,0x4a,0xbf,0xb5,0xe0,0xbc,0x8c,0x8a,0xab,0x7a,0xd2,0xcd,0xea,0xf7' config/binary && ok "paleta de consola en bootappend-live" || fallo "falta la paleta de consola"
grep -q 'vt.default_red=0x08,0xd9,0x54,0xd9,0x6a,0xa6,0x55,0xa7,0x71,0xe8,0x86,0xe8,0x8f,0xc2,0x8a,0xee vt.default_grn=0x0b,0x62,0xe5,0xa5,0x9f,0x8a,0xcd,0xb4,0x81,0x90,0xef,0xc2,0xb9,0xaa,0xdc,0xf4 vt.default_blu=0x0d,0x5b,0x8a,0x4a,0xbf,0xb5,0xe0,0xbc,0x8c,0x8a,0xab,0x7a,0xd2,0xcd,0xea,0xf7' chroot/etc/default/grub.d/90-hypr.cfg && ok "paleta de consola en GRUB instalado" || fallo "falta la paleta de consola en GRUB"

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

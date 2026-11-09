#!/bin/bash
# Verificacion: . Ejecutar con sudo desde ~/isolab, con ./chroot construido
# y la VM con 3D activado. Instala herramientas de prueba en el chroot, asi que
# despues hay que ejecutar lb clean: nada de esto llega a la ISO.
export LC_ALL=C
SALIDA=/tmp/verificar-barra.salida
: > "$SALIDA"
SKEL=/etc/skel/.config

ok()        { echo "[OK]    $1" | tee -a "$SALIDA"; }
fallo()     { echo "[FALLO] $1" | tee -a "$SALIDA"; }
instalado() { chroot chroot dpkg-query -W -f='${Status}' "$1" 2>/dev/null | grep -qE " ok installed"; }

[ "$(id -u)" -eq 0 ] || { echo "Ejecuta con sudo."; exit 1; }
[ -d chroot/etc/apt ] || { echo "No existe ./chroot."; exit 1; }

echo "== Paquetes de ui.list.chroot =="
for P in $(cat config/package-lists/ui.list.chroot); do
    if instalado "$P"; then ok "$P"; else fallo "$P no instalado"; fi
done
V=$(chroot chroot dpkg-query -W -f='${Version}' waybar)
[ "$V" = "0.15.0-1+hypr1" ] && ok "waybar parcheado: $V" || fallo "version de waybar: $V"

echo "== Paquetes que no deben estar =="
for P in xserver-xorg xserver-xorg-core gnome-shell plasma-desktop plasma-workspace xfce4 xfce4-session cinnamon cinnamon-desktop-environment mate-desktop-environment mate-session-manager lxde lxde-core lxsession nautilus dolphin; do
    if instalado "$P"; then fallo "$P esta instalado"; else ok "$P ausente"; fi
done

echo "== Archivos =="
for F in "$SKEL/waybar/config.jsonc" "$SKEL/waybar/style.css" "$SKEL/rofi/config.rasi" "$SKEL/rofi/jaime0.rasi" "$SKEL/dunst/dunstrc" /usr/local/bin/menu-energia /usr/local/bin/notificaciones-waybar; do
    [ -f "chroot$F" ] && ok "$F" || fallo "$F no existe"
    grep -q $'\r' "chroot$F" && fallo "$F tiene CRLF"
done
[ -x chroot/usr/local/bin/menu-energia ] && ok "menu-energia ejecutable" || fallo "menu-energia sin permiso"
[ -x chroot/usr/local/bin/notificaciones-waybar ] && ok "notificaciones-waybar ejecutable" || fallo "notificaciones-waybar sin permiso"
sh -n chroot/usr/local/bin/notificaciones-waybar && ok "notificaciones-waybar: sintaxis" || fallo "notificaciones-waybar: sintaxis"
chroot chroot sh /usr/local/bin/notificaciones-waybar 2>/dev/null | python3 -c 'import json,sys; d=json.loads(sys.stdin.read()); assert d["class"] in ("activas","pausadas")' && ok "notificaciones-waybar devuelve JSON valido" || fallo "notificaciones-waybar sin JSON valido"
sh -n chroot/usr/local/bin/menu-energia && ok "menu-energia: sintaxis" || fallo "menu-energia: sintaxis"
if grep -nE '(#|//) *(a[nñ]ade aqu|resto de)|^[[:space:]]*\.\.\.[[:space:]]*$' "chroot$SKEL/waybar/config.jsonc" "chroot$SKEL/waybar/style.css" "chroot$SKEL/rofi/config.rasi" "chroot$SKEL/rofi/jaime0.rasi" "chroot$SKEL/dunst/dunstrc"; then fallo "hay marcadores"; else ok "sin marcadores"; fi

echo "== JSONC =="
if python3 - "chroot$SKEL/waybar/config.jsonc" <<'PY'
import json, re, sys
t = re.sub(r'^\s*//.*$', '', open(sys.argv[1], encoding='utf-8').read(), flags=re.M)
d = json.loads(t)
assert d['modules-left'] == ['custom/logo', 'hyprland/workspaces', 'hyprland/window']
assert d['modules-center'] == ['mpris']
assert d['modules-right'] == ['cpu', 'memory', 'pulseaudio', 'network', 'bluetooth', 'battery', 'clock', 'custom/notificaciones', 'group/bandeja', 'custom/power']
assert d['group/bandeja']['modules'] == ['custom/bandeja', 'tray']
assert 'on-click' not in d['clock'] and '{calendar}' in d['clock']['tooltip-format']
assert d['custom/notificaciones']['exec'] == 'notificaciones-waybar'
assert 'nmtui-flotante' in d['network']['on-click'] and 'nmtui' in d['network']['on-click']
assert d['bluetooth']['on-click'] == 'blueman-manager'
assert d['custom/power']['on-click'] == 'menu-energia'
assert d['custom/logo']['on-click-right'] == 'atajos --rofi'
assert d['hyprland/workspaces']['format'] == '{icon}'
assert d['hyprland/workspaces']['persistent-workspaces'] == {'*': 5}
assert d['cpu']['on-click'] == 'abrir-btop' and d['memory']['on-click'] == 'abrir-btop'
assert d['pulseaudio']['on-click'] == 'pavucontrol'
for m in ('cpu', 'memory', 'network', 'bluetooth', 'clock', 'custom/power', 'custom/logo'):
    assert any(0xe000 <= ord(ch) <= 0xf8ff for ch in str(d[m].get('format', d[m].get('format-ethernet', '')))), m
print('ok')
PY
then ok "config.jsonc valido con los modulos pedidos"; else fallo "config.jsonc invalido"; fi

echo "== Valores de la especificacion =="
for PAR in "waybar/style.css|border-radius: 9px" "waybar/style.css|rgba.18, 20, 29, 0.82." "waybar/style.css|@define-color rosa +#ff6ea9" "waybar/style.css|@define-color malva +#b59bff" "waybar/style.css|@define-color cian +#6ee7f2" "waybar/style.css|@define-color verde +#a6e87a" "waybar/style.css|@define-color amarillo +#ffe57a" "waybar/style.css|#cpu +\{ color: @verde" "waybar/style.css|#clock +\{ color: @malva" "waybar/config.jsonc|#ff6ea9" "rofi/config.rasi|Papirus-Dark" "rofi/config.rasi|show-icons: true" "rofi/jaime0.rasi|location: *center" "rofi/jaime0.rasi|border-radius: *12px" "rofi/jaime0.rasi|#12141de6" "dunst/dunstrc|origin = top-right" "dunst/dunstrc|corner_radius = 10" "dunst/dunstrc|#12141de6" "dunst/dunstrc|frame_color = \"#b59bff\"" "dunst/dunstrc|timeout = 5"; do
    A=${PAR%%|*}; E=${PAR#*|}
    grep -qE -- "$E" "chroot$SKEL/$A" && ok "$A: $E" || fallo "$A: falta $E"
done
[ "$(grep -c '^ *timeout = 5$' "chroot$SKEL/dunst/dunstrc")" = "3" ] && ok "timeout 5 s en las tres urgencias" || fallo "timeout incompleto"
grep -q "hl.dsp.exit()" chroot/usr/local/bin/menu-energia && ok "menu-energia usa hl.dsp.exit()" || fallo "dispatcher de salida"
for O in Apagar Reiniciar Suspender "Cerrar sesión"; do grep -q "$O" chroot/usr/local/bin/menu-energia && ok "menu: $O" || fallo "menu sin $O"; done

echo "== Fuente e iconos =="
N=$(chroot chroot fc-list | grep -c 'JetBrainsMono Nerd Font'); [ "$N" -gt 0 ] && ok "JetBrainsMono Nerd Font: $N estilos" || fallo "falta la fuente"
chroot chroot fc-match 'JetBrainsMono Nerd Font' | grep -q 'JetBrainsMonoNerdFont' && ok "fc-match resuelve la fuente" || fallo "fc-match no la resuelve"
[ -f chroot/usr/share/fonts/truetype/jetbrains-mono-nerd/OFL.txt ] && ok "licencia OFL incluida" || fallo "falta la licencia"
[ -f chroot/usr/share/icons/Papirus-Dark/index.theme ] && ok "Papirus-Dark instalado" || fallo "falta Papirus-Dark"

echo "== Binarios =="
chroot chroot rofi -help 2>&1 | grep -qE '^[[:space:]]*.*wayland' && ok "rofi con backend wayland" || fallo "rofi sin wayland"
chroot chroot sh -c 'rofi -help' 2>&1 | grep -iE 'drun|dmenu' | head -2 | cut -c1-100
chroot chroot rofi -dump-config >/dev/null 2>&1 && ok "rofi -dump-config" || fallo "rofi -dump-config"
chroot chroot env HOME=/etc/skel rofi -dump-theme >/tmp/vs4tema 2>&1
grep -q '#b59bff\|rgba ( 181, 155, 255' /tmp/vs4tema && ok "rofi -dump-theme analiza el tema" || { fallo "rofi -dump-theme"; head -5 /tmp/vs4tema; }
sed 's/location:         center;/location center;;;{/' "chroot$SKEL/rofi/jaime0.rasi" > chroot/tmp/roto.rasi
chroot chroot env HOME=/tmp rofi -theme /tmp/roto.rasi -dump-theme >/tmp/vs4tema 2>&1
grep -qiE 'error|fail|unexpected' /tmp/vs4tema && ok "control negativo: rofi detecta un tema roto" || fallo "control negativo de rofi sin efecto"
chroot chroot ldd /usr/bin/dunst | grep -q libwayland-client && ok "dunst enlazado con Wayland" || fallo "dunst sin Wayland"
chroot chroot sh -c "command -v nmtui" >/dev/null && ok "nmtui disponible para el clic de red" || fallo "falta nmtui"
instalado network-manager-applet && fallo "network-manager-applet sigue instalado" || ok "sin network-manager-applet"

echo "== Preparar prueba en vivo =="
cp /etc/resolv.conf chroot/etc/resolv.conf
chroot chroot apt-get -qq update
chroot chroot sh -c 'DEBIAN_FRONTEND=noninteractive apt-get -y -qq --no-install-recommends install seatd wlrctl >/dev/null 2>&1'
# rbind + rslave: los desmontajes no se propagan a /dev de la VM.
mount -t proc proc chroot/proc; mount -t sysfs sys chroot/sys
mount --rbind /dev chroot/dev; mount --make-rslave chroot/dev
mkdir -p chroot/run/udev; mount --bind /run/udev chroot/run/udev; mount --make-slave chroot/run/udev
matar_chroot() {
    R=$(readlink -f chroot)
    for D in /proc/[0-9]*; do
        [ "$(readlink "$D/root" 2>/dev/null)" = "$R" ] && kill -9 "${D#/proc/}" 2>/dev/null
    done
    sleep 2
}
trap 'matar_chroot; umount chroot/run/udev; umount -R chroot/dev; umount chroot/sys chroot/proc' EXIT
chroot chroot sh -c 'id prueba >/dev/null 2>&1 || useradd -m -k /etc/skel -G video,render,input prueba'
[ -f chroot/home/prueba/.config/waybar/config.jsonc ] && [ "$(stat -c %U chroot/home/prueba/.config/waybar/config.jsonc)" != "root" ] && ok "un usuario nuevo hereda la configuracion de /etc/skel" || fallo "usuario nuevo sin configuracion"
# El GID de render del chroot no coincide con el dispositivo de la VM, y se deja asi a proposito:
# kitty usa entonces renderizado por software. Con acceso a renderD128, kitty cae en VirtualBox
# con "invalid arguments for wl_surface.attach" (drivers SVGA3D de la VM).
chroot chroot sh -c 'mkdir -p /run; rm -f /run/seatd.sock; nohup seatd -g video >/tmp/seatd.log 2>&1 &'
chroot chroot sh -c 'mkdir -p /run/dbus; rm -f /run/dbus/system_bus_socket /run/dbus/pid; dbus-daemon --system --fork; /usr/libexec/bluetooth/bluetoothd >/dev/null 2>&1 & /usr/lib/polkit-1/polkitd --no-debug >/dev/null 2>&1 &'
sleep 2

echo "== Prueba en vivo =="
cp coords-barra.sh chroot/tmp/coords-barra.sh; chmod 644 chroot/tmp/coords-barra.sh
cp verificar-barra-en-vivo.sh chroot/tmp/vivo.sh; chmod 755 chroot/tmp/vivo.sh
rm -rf chroot/tmp/vs4x; mkdir -p chroot/tmp/vs4x; chown "$(chroot chroot id -u prueba)" chroot/tmp/vs4x
chroot --userspec=prueba:prueba chroot env HOME_PRUEBA=/home/prueba /tmp/vivo.sh 2>&1 | tee -a "$SALIDA"
mkdir -p capturas-barra; cp chroot/tmp/vs4x/*.png capturas-barra/ 2>/dev/null; chmod -R a+rX capturas-barra

echo "== dunst -print =="
chroot chroot sh -c 'grep -c "\[urgency_" /home/prueba/.config/dunst/dunstrc'

F=$(grep -c '^\[FALLO\]' "$SALIDA"); O=$(grep -c '^\[OK\]' "$SALIDA")
echo
echo "RESULTADO: ${F} fallo(s), ${O} correctos"
[ "$F" -eq 0 ]

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
# Rastro de versiones anteriores de esta misma prueba (rofi con HOME=/etc/skel).
[ -d chroot/etc/skel/.cache ] && echo "AVISO: existe chroot/etc/skel/.cache (lo dejo una ejecucion anterior de verificar-barra.sh; no esta en la ISO si se compilo antes). Borralo con: sudo rmdir chroot/etc/skel/.cache"

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
for F in "$SKEL/waybar/config.jsonc" "$SKEL/waybar/style.css" "$SKEL/rofi/config.rasi" "$SKEL/rofi/jaime0.rasi" "$SKEL/swaync/config.json" "$SKEL/swaync/style.css" /usr/local/bin/menu-energia /usr/local/bin/notificaciones; do
    [ -f "chroot$F" ] && ok "$F" || fallo "$F no existe"
    grep -q $'\r' "chroot$F" && fallo "$F tiene CRLF"
done
[ -x chroot/usr/local/bin/menu-energia ] && ok "menu-energia ejecutable" || fallo "menu-energia sin permiso"
[ -x chroot/usr/local/bin/notificaciones ] && sh -n chroot/usr/local/bin/notificaciones && ok "notificaciones: ejecutable y sintaxis" || fallo "notificaciones"
[ -e chroot/usr/local/bin/notificaciones-waybar ] && fallo "queda notificaciones-waybar (sustituido)" || ok "sin notificaciones-waybar"
python3 -c 'import json,sys; json.load(open(sys.argv[1]))' "chroot$SKEL/swaync/config.json" && ok "swaync/config.json es JSON valido" || fallo "swaync/config.json invalido"
grep -q '@import url("../jaime0/generado/swaync.css")' "chroot$SKEL/swaync/style.css" && ok "swaync usa el acento generado" || fallo "swaync sin acento generado"
sh -n chroot/usr/local/bin/menu-energia && ok "menu-energia: sintaxis" || fallo "menu-energia: sintaxis"
if grep -nE '(#|//) *(a[nñ]ade aqu|resto de)|^[[:space:]]*\.\.\.[[:space:]]*$' "chroot$SKEL/waybar/config.jsonc" "chroot$SKEL/waybar/style.css" "chroot$SKEL/rofi/config.rasi" "chroot$SKEL/rofi/jaime0.rasi" "chroot$SKEL/dunst/dunstrc"; then fallo "hay marcadores"; else ok "sin marcadores"; fi

echo "== JSONC =="
if python3 - "chroot$SKEL/waybar/config.jsonc" <<'PY'
import json, re, sys
t = re.sub(r'^\s*//.*$', '', open(sys.argv[1], encoding='utf-8').read(), flags=re.M)
d = json.loads(t)
assert d['modules-left'] == ['custom/logo', 'hyprland/workspaces']
assert d['modules-center'] == [f'custom/ancla-{n}' for n in range(1, 7)]
assert d['modules-right'] == ['cpu', 'memory', 'pulseaudio', 'network', 'bluetooth', 'custom/jaime0', 'battery', 'custom/actualizaciones', 'custom/notificaciones', 'group/bandeja', 'clock', 'custom/power']
assert d['custom/actualizaciones']['exec'] == 'actualizaciones barra' and d['custom/actualizaciones']['signal'] == 10 and 'install' not in d['custom/actualizaciones']['on-click']
# Ancladas: sin sondeo (interval once + senal 9) y clic a jaime0-anclar.
for n in range(1, 7):
    m = d[f'custom/ancla-{n}']
    assert m['interval'] == 'once' and m['signal'] == 9 and m['return-type'] == 'json', n
    assert m['on-click'] == f'jaime0-anclar abrir {n}' and f'anclas/{n}.json' in m['exec'], n
assert 'hyprland/window' not in d and 'mpris' not in d
# Altura y posicion salen de jaime0-ajustes (generado/waybar.json), no de aqui.
assert 'height' not in d and 'position' not in d
assert d['include'] == ['~/.config/jaime0/generado/waybar.json']
# Rendimiento: nada se sondea mas a menudo de lo necesario.
assert d['clock']['interval'] >= 30 and '%S' not in d['clock']['format']
assert d['cpu']['interval'] >= 5 and d['memory']['interval'] >= 10
assert d['network']['interval'] >= 10 and d['battery']['interval'] >= 60
assert d['custom/notificaciones']['on-click-right'] == 'notificaciones nomolestar'
assert d['custom/notificaciones']['on-click'] == 'notificaciones panel' and 'interval' not in d['custom/notificaciones']
assert d['group/bandeja']['modules'] == ['custom/bandeja', 'tray']
assert 'on-click' not in d['clock'] and '{calendar}' in d['clock']['tooltip-format']
assert d['custom/notificaciones']['exec'] == 'notificaciones barra'
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
for PAR in "waybar/style.css|@define-color fondo +#080b0d" "waybar/style.css|border-bottom: 1px solid @borde" "waybar/style.css|@import url\(\"../jaime0/generado/waybar.css\"\)" "waybar/style.css|window#waybar.bottom" "waybar/style.css|\.ancla\.abierta" "rofi/jaime0.rasi|\?import \"~/.config/jaime0/generado/rofi.rasi\"" "rofi/jaime0.rasi|acento: +#54e58a" "waybar/style.css|#cpu +\{ color: @gris" "waybar/style.css|#workspaces button.active" "waybar/style.css|#clock +\{ color: @texto" "waybar/config.jsonc|#54e58a" "rofi/config.rasi|Papirus-Dark" "rofi/config.rasi|show-icons: true" "rofi/jaime0.rasi|location: *center" "rofi/jaime0.rasi|border: *1px" "rofi/jaime0.rasi|#080b0df0" "swaync/style.css|@acento"; do
    A=${PAR%%|*}; E=${PAR#*|}
    grep -qE -- "$E" "chroot$SKEL/$A" && ok "$A: $E" || fallo "$A: falta $E"
done
python3 - "chroot$SKEL/waybar/style.css" <<'PY' && ok "style.css: llaves equilibradas y colores definidos" || fallo "style.css: llaves o colores sin definir"
import re, sys
t = re.sub(r'/\*.*?\*/', '', open(sys.argv[1], encoding='utf-8').read(), flags=re.S)
assert t.count('{') == t.count('}')
definidos = set(re.findall(r'@define-color\s+([\w-]+)', t))
usados = set(re.findall(r'@([\w-]+)', t)) - {'define-color', 'import'}
definidos.add('acento')  # lo define generado/waybar.css (jaime0-ajustes)
assert usados <= definidos, usados - definidos
PY
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
# XDG_CACHE_HOME aparte: si no, rofi crea /etc/skel/.cache (700) en el chroot, que todo usuario
# nuevo heredaria y que verificar-software detecta como "directorio sin 755".
chroot chroot env HOME=/etc/skel XDG_CACHE_HOME=/tmp/vs4cache rofi -dump-theme >/tmp/vs4tema 2>&1
grep -qi '#54e58a\|rgba ( 84, 229, 138' /tmp/vs4tema && ok "rofi -dump-theme analiza el tema" || { fallo "rofi -dump-theme"; head -5 /tmp/vs4tema; }
sed 's/location:         center;/location center;;;{/' "chroot$SKEL/rofi/jaime0.rasi" > chroot/tmp/roto.rasi
chroot chroot env HOME=/tmp rofi -theme /tmp/roto.rasi -dump-theme >/tmp/vs4tema 2>&1
grep -qiE 'error|fail|unexpected' /tmp/vs4tema && ok "control negativo: rofi detecta un tema roto" || fallo "control negativo de rofi sin efecto"
instalado dunst && fallo "dunst sigue instalado (sustituido por swaync)" || ok "sin dunst: un solo sistema de notificaciones"
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


F=$(grep -c '^\[FALLO\]' "$SALIDA"); O=$(grep -c '^\[OK\]' "$SALIDA"); P=$(grep -c '^\[PEND\]' "$SALIDA")
echo
echo "RESULTADO: ${F} fallo(s), ${P} pendiente(s), ${O} correctos"
[ "$F" -eq 0 ]

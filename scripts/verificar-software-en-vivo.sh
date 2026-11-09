#!/bin/bash
# Parte en vivo de verificar-software.sh. Se ejecuta DENTRO del chroot como usuario nuevo y
# arranca Hyprland de verdad. Uso: verificar-software-en-vivo.sh corta|completa
MODO="$1"
X=/tmp/vs6x-$(id -un)
export XDG_RUNTIME_DIR=$X HOME="$HOME_PRUEBA" LANG=es_ES.UTF-8
export LIBSEAT_BACKEND=seatd SEATD_SOCK=/run/seatd.sock
export HYPRLAND_NO_CRASHREPORTER=1 HYPRLAND_NO_SD_NOTIFY=1
export PATH=/usr/local/bin:/usr/bin:/bin
export SHELL="$(getent passwd "$(id -un)" | cut -d: -f7)"
unset LIBGL_ALWAYS_SOFTWARE GSK_RENDERER LC_ALL

ok()    { echo "[OK]    $1"; }
fallo() { echo "[FALLO] $1"; }
clientes() { hyprctl clients | grep -E '^[[:space:]]+class:' | awk '{print $2}'; }
foto()     { grim -c "$X/$1.png"; }
escritorio() { hyprctl dispatch "hl.dsp.focus({ workspace = $1 })" >/dev/null; sleep 1; }
lanzar()   { hyprctl dispatch "hl.dsp.exec_cmd(\"$1\")" >/dev/null; }

chmod 700 "$X"; cd "$HOME"
export DBUS_SESSION_BUS_ADDRESS="unix:path=$X/bus"
dbus-daemon --session --address="$DBUS_SESSION_BUS_ADDRESS" --fork --nopidfile
(pipewire >/dev/null 2>&1 &)
(wireplumber >/dev/null 2>&1 &)
(pipewire-pulse >/dev/null 2>&1 &)
sleep 2

# Config heredada de /etc/skel, sin --config.
timeout 700 Hyprland > "$X/hypr.log" 2>&1 &
sleep 15
export HYPRLAND_INSTANCE_SIGNATURE=$(ls "$X/hypr" | head -1)
export WAYLAND_DISPLAY=$(ls "$X" | grep -E '^wayland-[0-9]+$' | head -1)

[ -n "$HYPRLAND_INSTANCE_SIGNATURE" ] && hyprctl monitors | grep -q '^Monitor' && ok "$(id -un): Hyprland arranca con la config heredada" || fallo "$(id -un): Hyprland no arranca"
E=$(hyprctl configerrors | grep -v '^$' | grep -vi 'no errors' | head -3)
[ -z "$E" ] && ok "$(id -un): sin errores de configuracion" || fallo "$(id -un): configerrors: $E"
hyprctl eval 'hl.monitor({ output = "", mode = "preferred", position = "auto", scale = 1 })' >/dev/null
sleep 2
pgrep -x waybar >/dev/null && ok "$(id -un): waybar corre" || fallo "$(id -un): waybar no corre"

salir() {
    R=$(hyprctl dispatch 'hl.dsp.exit()'); sleep 4
    [ "$R" = "ok" ] && ! pgrep -u "$(id -u)" -x Hyprland >/dev/null && ok "$(id -un): la sesion termina limpia" || fallo "$(id -un): cerrar sesion: '$R'"
    pkill -u "$(id -u)" -x pipewire-pulse; pkill -u "$(id -u)" -x wireplumber; pkill -u "$(id -u)" -x pipewire; pkill -u "$(id -u)" -x dbus-daemon
}

if [ "$MODO" = corta ]; then
    foto "sesion-$(id -un)"
    salir
    exit 0
fi

echo "-- Carpetas de usuario --"
grep -q '^XDG_PICTURES_DIR="$HOME/Imágenes"' "$HOME/.config/user-dirs.dirs" && ok "xdg-user-dirs en espanol: Imágenes" || fallo "user-dirs: $(grep PICTURES "$HOME/.config/user-dirs.dirs" 2>&1)"
[ -d "$HOME/Imágenes" ] && [ -d "$HOME/Descargas" ] && [ -d "$HOME/Documentos" ] && ok "carpetas creadas: $(ls "$HOME" | tr '\n' ' ')" || fallo "faltan carpetas: $(ls "$HOME" | tr '\n' ' ')"
[ "$(xdg-user-dir PICTURES)" = "$HOME/Imágenes" ] && ok "xdg-user-dir PICTURES" || fallo "xdg-user-dir PICTURES: $(xdg-user-dir PICTURES)"
mkdir -p "$X/stub"; printf '#!/bin/sh\necho "10,10 200x120"\n' > "$X/stub/slurp"; chmod 755 "$X/stub/slurp"
PATH="$X/stub:$PATH" captura-area; sleep 1
ls "$HOME/Imágenes/Capturas/"captura-*.png >/dev/null 2>&1 && ok "captura-area crea el archivo en Imágenes/Capturas" || fallo "captura-area no creo el archivo"
wl-paste --list-types 2>/dev/null | grep -q image/png && ok "captura-area copia al portapapeles" || fallo "captura-area sin portapapeles"

echo "-- Archivos de prueba --"
P="$HOME/pruebas"; mkdir -p "$P/carpeta"
echo "contenido de prueba" > "$P/nota.txt"

echo "-- Asociaciones --"
for PAR in "inode/directory|thunar.desktop" "text/plain|nvim.desktop"; do
    M=${PAR%%|*}; D=${PAR#*|}
    R=$(xdg-mime query default "$M")
    [ "$R" = "$D" ] && ok "xdg-mime $M = $R" || fallo "xdg-mime $M = '$R', se esperaba $D"
done
R=$(xdg-mime query filetype "$P/nota.txt")
[ "$R" = "text/plain" ] && ok "tipo de nota.txt = $R (sin libfile-mimeinfo-perl)" || fallo "tipo de nota.txt = '$R'"
R=$(xdg-mime query filetype "$P/carpeta")
[ "$R" = "inode/directory" ] && ok "tipo de carpeta = $R (sin libfile-mimeinfo-perl)" || fallo "tipo de carpeta = '$R'"

echo "-- Aplicaciones --"
escritorio 2
lanzar "xdg-open '$P/carpeta' > $X/carpeta.log 2>&1"
sleep 7
clientes | grep -qiE '^thunar$' && ok "xdg-open carpeta abre Thunar" || fallo "xdg-open carpeta: $(clientes | tr '\n' ' '). Log: $(tail -2 "$X/carpeta.log" | cut -c1-160)"
foto s6-carpeta
xfconf-query -c thunar -p /hidden-bookmarks 2>/dev/null | grep -q 'trash:///' && ok "Thunar: Papelera oculta en xfconf" || fallo "Thunar: hidden-bookmarks: $(xfconf-query -c thunar -p /hidden-bookmarks 2>&1 | tr '\n' ' ')"
pkill -u "$(id -u)" -f '(^|/)[Tt]hunar'; sleep 3

escritorio 3
lanzar "kitty -e nvim '$P/nota.txt'"
sleep 7
hyprctl clients | grep -q 'title: .*nota.txt.*\|title: .*nvim' && ok "Neovim abre en kitty" || fallo "Neovim no abre: $(hyprctl clients | grep title: | cut -c1-80)"
foto s6-nvim
pkill -u "$(id -u)" -x nvim; sleep 3

for B in firefox-esr galculator imv zathura file-roller gsimplecal; do
    command -v "$B" >/dev/null && fallo "$B sigue instalado" || ok "$B no esta"
done

echo "-- Montaje: componentes --"
gio mount -l >/dev/null 2>&1 && ok "gio mount responde en la sesion" || fallo "gio mount no responde"

escritorio 1
lanzar "thunar '$P'"; sleep 6; lanzar "kitty"; sleep 6
foto s6-escritorio
pkill -u "$(id -u)" -f '(^|/)[Tt]hunar'; pkill -u "$(id -u)" -x kitty; sleep 2
salir
exit 0

#!/bin/bash
# Verificacion: . Ejecutar con sudo desde ~/isolab, con ./chroot construido y la VM
# con 3D activado. Instala herramientas de prueba en el chroot y crea dos usuarios nuevos,
# asi que despues hay que ejecutar lb clean: nada de esto llega a la ISO.
export LC_ALL=C
SALIDA=/tmp/verificar-software.salida
: > "$SALIDA"
SKEL=chroot/etc/skel

ok()        { echo "[OK]    $1" | tee -a "$SALIDA"; }
fallo()     { echo "[FALLO] $1" | tee -a "$SALIDA"; }
instalado() { chroot chroot dpkg-query -W -f='${Status}' "$1" 2>/dev/null | grep -qE " ok installed"; }

[ "$(id -u)" -eq 0 ] || { echo "Ejecuta con sudo."; exit 1; }
[ -d chroot/etc/apt ] || { echo "No existe ./chroot."; exit 1; }

echo "== Paquetes de software.list.chroot =="
for P in $(cat config/package-lists/software.list.chroot); do
    if instalado "$P"; then ok "$P"; else fallo "$P no instalado"; fi
done
for P in nautilus dolphin xserver-xorg xserver-xorg-core gnome-shell plasma-desktop xfce4 cinnamon mate-desktop-environment lxde chromium xfdesktop4 nemo pcmanfm firefox firefox-esr firefox-esr-l10n-es-es galculator gsimplecal thunar-archive-plugin zip build-essential yelp tumbler; do
    if instalado "$P"; then fallo "$P instalado"; else ok "$P ausente"; fi
done

echo "== Ordenes =="
for C in thunar git curl wget unzip tar nvim ssh xdg-open xdg-mime xdg-user-dirs-update; do
    chroot chroot sh -c "PATH=/usr/local/bin:/usr/bin:/bin command -v $C" >/dev/null && ok "orden $C" || fallo "falta la orden $C"
done

echo "== Asociaciones: cada .desktop existe =="
for D in $(grep '=' "$SKEL/.config/mimeapps.list" | cut -d= -f2 | sort -u); do
    if [ -f "chroot/usr/share/applications/$D" ]; then
        ok "$D existe: $(grep -m1 '^Exec=' "chroot/usr/share/applications/$D")"
    else
        fallo "$D no existe"
    fi
done

echo "== Menu de Thunar y montaje =="
[ -x chroot/usr/libexec/gvfs-udisks2-volume-monitor ] && ok "gvfs-udisks2-volume-monitor" || fallo "falta gvfs-udisks2-volume-monitor"
[ -x chroot/usr/libexec/udisks2/udisksd ] && ok "udisksd" || fallo "falta udisksd"
[ -x chroot/usr/bin/udiskie ] && fallo "udiskie sigue instalado (Thunar monta con gvfs)" || ok "sin udiskie residente: Thunar monta con gvfs"
grep -q 'udiskie' "$SKEL/.config/hypr/hyprland.lua" && fallo "udiskie en el autostart" || ok "udiskie fuera del autostart"
[ -f chroot/usr/lib/x86_64-linux-gnu/thunarx-3/thunar-sendto-email.so ] && echo "Aviso: sendto-email presente"

echo "== Idioma y carpetas =="
chroot chroot locale -a | grep -qix 'es_ES.utf8' && ok "locale es_ES.UTF-8 generado" || fallo "locale es_ES no generado"
grep -qx 'LANG=es_ES.UTF-8' chroot/etc/default/locale && ok "LANG por defecto" || fallo "LANG por defecto: $(cat chroot/etc/default/locale)"
[ -f chroot/usr/share/locale/es/LC_MESSAGES/xdg-user-dirs.mo ] && ok "traduccion de xdg-user-dirs" || fallo "falta la traduccion de xdg-user-dirs"
grep -q 'xdg-user-dirs-update' "$SKEL/.config/hypr/hyprland.lua" && ok "xdg-user-dirs-update en el autostart" || fallo "xdg-user-dirs-update fuera del autostart"
echo "xdg-user-dirs.service: $(chroot chroot systemctl --global is-enabled xdg-user-dirs.service 2>&1)"

echo "== Auditoria de /etc/skel =="
for F in .config/hypr/hyprland.lua .config/waybar/config.jsonc .config/waybar/style.css .config/kitty/kitty.conf .config/rofi/config.rasi .config/rofi/jaime0.rasi .config/swaync/config.json .config/hypr/hyprlock.conf .config/hypr/hypridle.conf .config/btop/btop.conf .config/btop/themes/jaime0.theme .config/fastfetch/config.jsonc .config/gtk-3.0/settings.ini .config/gtk-3.0/gtk.css .config/gtk-4.0/settings.ini .config/gtk-4.0/gtk.css .config/qt6ct/qt6ct.conf .config/starship.toml .config/mimeapps.list .config/xfce4/xfconf/xfce-perchannel-xml/thunar.xml .config/nvim/init.lua .zshrc; do
    [ -f "$SKEL/$F" ] && ok "$F" || fallo "$F no existe"
done
M=$(find "$SKEL" ! -user root -o ! -group root | wc -l); [ "$M" -eq 0 ] && ok "todo /etc/skel es de root" || fallo "$M entradas no son de root"
M=$(find "$SKEL" -type d ! -perm 755 | wc -l); [ "$M" -eq 0 ] && ok "directorios 755: $(find "$SKEL" -type d | wc -l)" || fallo "$M directorios sin 755"
MALOS=0; EJEC=0
while IFS= read -r A; do
    if [ "$(head -c 2 "$A")" = '#!' ]; then ESP=755; EJEC=$((EJEC + 1)); else ESP=644; fi
    [ "$(stat -c %a "$A")" = "$ESP" ] || { fallo "$A tiene $(stat -c %a "$A"), se esperaba $ESP"; MALOS=$((MALOS + 1)); }
done < <(find "$SKEL" -type f)
[ "$MALOS" -eq 0 ] && ok "archivos: $(find "$SKEL" -type f | wc -l) con modo correcto, $EJEC scripts 755" || fallo "$MALOS archivos con modo incorrecto"
[ "$(find "$SKEL" -type l | wc -l)" -eq 0 ] && ok "sin enlaces simbolicos" || fallo "hay enlaces simbolicos en skel"
grep -rlE '/home/builder|builder@' "$SKEL" && fallo "referencias a builder en skel" || ok "sin referencias a builder"
grep -rlP '\r' "$SKEL" && fallo "CRLF en skel" || ok "todas las lineas son LF"
python3 - "$SKEL/.config/mimeapps.list" <<'PY' && ok "mimeapps.list valido" || fallo "mimeapps.list invalido"
import configparser, sys
c = configparser.ConfigParser(); c.optionxform = str; c.read(sys.argv[1], encoding="utf-8")
assert c["Default Applications"]["inode/directory"] == "thunar.desktop"
d = c["Default Applications"]
assert d["video/mp4"] == "mpv.desktop" and d["image/png"] == "imv.desktop" and d["text/html"] == "brave-browser.desktop"
assert d["application/pdf"] == "org.pwmt.zathura-pdf-poppler.desktop" and d["application/zip"] == "org.gnome.FileRoller.desktop"
PY
for B in captura-area menu-energia; do
    [ "$(stat -c '%a %U' chroot/usr/local/bin/$B)" = "755 root" ] && ok "$B 755 root" || fallo "$B: $(stat -c '%a %U' chroot/usr/local/bin/$B)"
done

echo "== Modulo de tiempo (retirado) =="
[ -e chroot/usr/local/bin/tiempo-waybar ] && fallo "tiempo-waybar sigue en el sistema" || ok "sin tiempo-waybar: la barra no consulta servicios externos"

echo "== Preparar pruebas =="
cp /etc/resolv.conf chroot/etc/resolv.conf
chroot chroot apt-get -qq update
chroot chroot sh -c 'DEBIAN_FRONTEND=noninteractive apt-get -y -qq --no-install-recommends install seatd wlrctl python3-pil >/dev/null 2>&1'
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

GID_RENDER=$(stat -c %g /dev/dri/renderD128)
chroot chroot sh -c "getent group rendervm >/dev/null || groupadd -o -g $GID_RENDER rendervm"

echo "== Usuarios nuevos: useradd y adduser =="
chroot chroot sh -c 'userdel -r pruebau 2>/dev/null; userdel -r pruebaa 2>/dev/null; true'
chroot chroot useradd -m pruebau
chroot chroot adduser --disabled-password --comment 'Prueba' pruebaa >/dev/null
for U in pruebau pruebaa; do
    chroot chroot usermod -aG video,render,input,rendervm "$U"
    [ "$(chroot chroot getent passwd $U | cut -d: -f7)" = "/bin/zsh" ] && ok "$U: shell /bin/zsh" || fallo "$U: shell $(chroot chroot getent passwd $U | cut -d: -f7)"
    H=chroot/home/$U; UID_U=$(chroot chroot id -u $U); GID_U=$(chroot chroot id -g $U)
    N=$(find "$H/.config" "$H/.zshrc" ! -uid "$UID_U" -o ! -gid "$GID_U" | wc -l)
    [ "$N" -eq 0 ] && ok "$U: propietario correcto en ~/.config y ~/.zshrc" || fallo "$U: $N entradas con otro propietario"
    D=$(diff <(cd "$SKEL" && find .config .zshrc -printf '%p %y %m\n' | sort) <(cd "$H" && find .config .zshrc -printf '%p %y %m\n' | sort) | head -5)
    [ -z "$D" ] && ok "$U: ~/.config identico a skel en rutas y modos ($(find "$H/.config" | wc -l) entradas)" || fallo "$U: difiere de skel: $D"
    [ -f "$H/.config/hypr/hyprland.lua" ] && [ "$(stat -c %a "$H/.config")" = 755 ] && ok "$U: ~/.config 755 con hyprland.lua" || fallo "$U: ~/.config incorrecto"
    chroot --userspec=$U:$U chroot env HOME=/home/$U zsh -ic 'echo zsh-ok-$ZSH_VERSION' 2>/dev/null | grep -q zsh-ok && ok "$U: zsh interactivo carga .zshrc" || fallo "$U: zsh interactivo"
    chroot --userspec=$U:$U chroot env HOME=/home/$U XDG_RUNTIME_DIR=/tmp/vc$U sh -c "mkdir -p /tmp/vc$U; chmod 700 /tmp/vc$U; Hyprland --verify-config --config /home/$U/.config/hypr/hyprland.lua" 2>&1 | tail -1 | grep -q 'config ok' && ok "$U: --verify-config da config ok" || fallo "$U: --verify-config"
done

echo "== Herramientas sin interfaz =="
CMD='cd "$HOME"; mkdir -p t; cd t
git init -q r && cd r && git config user.email p@p && git config user.name p && echo a > a && git add a && git commit -qm a && git log --oneline | grep -q . && echo GIT; cd ..
curl -fsS -o /dev/null https://deb.debian.org/debian/dists/forky/Release && echo CURL
wget -q -O /dev/null https://deb.debian.org/debian/dists/forky/Release && echo WGET
git clone -q --depth 1 https://salsa.debian.org/live-team/live-config.git c && echo CLONA
nvim --headless -c "wq! n.txt" >/dev/null 2>&1; [ -f n.txt ] && echo NVIM
'
R=$(chroot --userspec=pruebau:pruebau chroot env HOME=/home/pruebau PATH=/usr/local/bin:/usr/bin:/bin bash -c "$CMD" 2>&1 | tr '\n' ' ')
echo "Salida: $R"
for T in GIT CURL WGET CLONA NVIM; do
    case " $R " in *" $T "*) ok "$T" ;; *) fallo "$T" ;; esac
done

echo "== Prueba en vivo =="
chroot chroot sh -c 'rm -f /run/seatd.sock; nohup seatd -g video >/tmp/seatd.log 2>&1 &'
chroot chroot sh -c 'mkdir -p /run/dbus; rm -f /run/dbus/system_bus_socket /run/dbus/pid; dbus-daemon --system --fork; /usr/libexec/bluetooth/bluetoothd >/dev/null 2>&1 &'
sleep 2
cp verificar-software-en-vivo.sh chroot/tmp/vivo6.sh; chmod 755 chroot/tmp/vivo6.sh
for PAR in pruebau:corta pruebaa:completa; do
    U=${PAR%%:*}; M=${PAR#*:}
    rm -rf chroot/tmp/vs6x-$U; mkdir -p chroot/tmp/vs6x-$U; chown "$(chroot chroot id -u $U)" chroot/tmp/vs6x-$U
    chroot --userspec=$U:$U chroot env HOME_PRUEBA=/home/$U /tmp/vivo6.sh "$M" 2>&1 | tee -a "$SALIDA"
done
mkdir -p capturas-software; cp chroot/tmp/vs6x-*/*.png capturas-software/ 2>/dev/null; cp chroot/tmp/vs6x-*/*.log capturas-software/ 2>/dev/null; chmod -R a+rX capturas-software

F=$(grep -c '^\[FALLO\]' "$SALIDA"); O=$(grep -c '^\[OK\]' "$SALIDA"); P=$(grep -c '^\[PEND\]' "$SALIDA")
echo
echo "RESULTADO: ${F} fallo(s), ${P} pendiente(s), ${O} correctos"
[ "$F" -eq 0 ]

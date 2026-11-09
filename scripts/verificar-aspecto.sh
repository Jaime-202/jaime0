#!/bin/bash
# Verificacion: . Ejecutar con sudo desde ~/isolab, con ./chroot construido y la VM
# con 3D activado. Instala herramientas de prueba en el chroot y crea un usuario nuevo,
# asi que despues hay que ejecutar lb clean: nada de esto llega a la ISO.
export LC_ALL=C
SALIDA=/tmp/verificar-aspecto.salida
: > "$SALIDA"
SKEL=chroot/etc/skel

ok()        { echo "[OK]    $1" | tee -a "$SALIDA"; }
fallo()     { echo "[FALLO] $1" | tee -a "$SALIDA"; }
instalado() { chroot chroot dpkg-query -W -f='${Status}' "$1" 2>/dev/null | grep -qE " ok installed"; }

[ "$(id -u)" -eq 0 ] || { echo "Ejecuta con sudo."; exit 1; }
[ -d chroot/etc/apt ] || { echo "No existe ./chroot."; exit 1; }

echo "== Paquetes de ricing.list.chroot =="
for P in $(cat config/package-lists/ricing.list.chroot); do
    if instalado "$P"; then ok "$P"; else fallo "$P no instalado"; fi
done
for P in xserver-xorg xserver-xorg-core gnome-shell plasma-desktop plasma-workspace xfce4 cinnamon mate-desktop-environment lxde nautilus dolphin; do
    if instalado "$P"; then fallo "$P instalado"; else ok "$P ausente"; fi
done

echo "== Archivos de usuario =="
for F in .zshrc .config/kitty/kitty.conf .config/starship.toml .config/fastfetch/config.jsonc .config/fastfetch/logo.txt .config/nvim/init.lua .config/btop/btop.conf .config/btop/themes/jaime0.theme .config/gtk-3.0/settings.ini .config/gtk-3.0/gtk.css .config/gtk-4.0/settings.ini .config/gtk-4.0/gtk.css .config/qt6ct/qt6ct.conf; do
    [ -f "$SKEL/$F" ] && ok "$F" || fallo "$F no existe"
    grep -q $'\r' "$SKEL/$F" && fallo "$F tiene CRLF"
    grep -nE '(#|//) *(a[nñ]ade aqu|resto de)|^[[:space:]]*\.\.\.[[:space:]]*$' "$SKEL/$F" && fallo "$F con marcadores"
done

echo "== Valores de la especificacion =="
for PAR in ".config/kitty/kitty.conf|^font_family +JetBrainsMono Nerd Font$" ".config/kitty/kitty.conf|^font_size +11" ".config/kitty/kitty.conf|^hide_window_decorations +yes$" ".config/kitty/kitty.conf|^window_padding_width +8$" ".config/kitty/kitty.conf|^background_opacity +0.72$" ".config/kitty/kitty.conf|^background +#12141d$" ".config/kitty/kitty.conf|^foreground +#e0e4f2$" ".config/kitty/kitty.conf|^tab_bar_edge +bottom$" ".config/kitty/kitty.conf|^tab_bar_min_tabs +1$" ".config/kitty/kitty.conf|^color5 +#ff6ea9$" ".config/btop/btop.conf|^color_theme = \"jaime0\"$" ".config/btop/btop.conf|^rounded_corners = True$" ".config/btop/themes/jaime0.theme|^theme.cpu_box.=\"#a6e87a\"$" ".zshrc|_titulo_orden" ".zshrc|COLUMNS >= 86" ".config/fastfetch/logo.txt|^.1 .*.2" ".config/gtk-3.0/settings.ini|^gtk-icon-theme-name=Papirus-Dark$" ".config/gtk-4.0/settings.ini|^gtk-icon-theme-name=Papirus-Dark$" ".config/qt6ct/qt6ct.conf|^icon_theme=Papirus-Dark$"; do
    A=${PAR%%|*}; E=${PAR#*|}
    grep -qE -- "$E" "$SKEL/$A" && ok "$A: $E" || fallo "$A: falta $E"
done
python3 - "$SKEL/.config/fastfetch/config.jsonc" <<'PY' && ok "fastfetch: JSONC valido con grupos OS, WM y PC en arbol" || fallo "fastfetch: JSONC invalido"
import json, re, sys
d = json.loads(re.sub(r'^\s*//.*$', '', open(sys.argv[1], encoding='utf-8').read(), flags=re.M))
claves = [m.get('key', '') for m in d['modules'] if isinstance(m, dict)]
assert 'OS' in claves and 'WM' in claves and 'PC' in claves
assert sum(1 for k in claves if k.startswith('│ ├')) >= 8 and sum(1 for k in claves if k.startswith('│ └')) == 3
assert d['logo']['color'] == {'1': '35', '2': '36'}
PY
python3 - "$SKEL/.config/starship.toml" <<'PY' && ok "starship.toml valido" || fallo "starship.toml invalido"
import sys, tomllib
d = tomllib.load(open(sys.argv[1], 'rb'))
assert d['palettes']['jaime0']['pink'] == '#ff6ea9'
assert d['add_newline'] is True and '$time' in d['right_format'] and '$status' in d['right_format'] and d['time']['disabled'] is False
assert '❯' in d['character']['success_symbol'] and '$directory' in d['format']
PY

echo "== Paleta: solo colores de la paleta jaime0 =="
python3 - chroot <<'PY' | tee -a "$SALIDA"
import pathlib, re, sys
MARINO = set("12141d 0b0d14 171a26 252939 343a52 2e3350 b59bff 7ab0ff 6ee7f2 e0e4f2 f2f4fb b6bcd4 9aa0bc 7a819e 565c78 454a64 ff5c72 ff8a99 ffe57a ffab6e a6e87a ff6ea9 a6cbff a2f0f7 c3f2a0 fff0a8 ffb3cf".split())
raiz = pathlib.Path(sys.argv[1])
rutas = []
for base in ["etc/skel/.config", "usr/share/qt6ct/colors/jaime0.conf", "etc/greetd/config.toml", "etc/calamares/branding/hypr/stylesheet.qss", "etc/calamares/branding/hypr/branding.desc", "etc/calamares/branding/hypr/logo.svg", "usr/share/grub/themes/hypr/theme.txt"]:
    p = raiz / base
    rutas += [p] if p.is_file() else [f for f in p.rglob("*") if f.is_file()]
ajenos = 0
for f in rutas:
    t = f.read_text(encoding="utf-8", errors="replace")
    if f.name in ("hyprland.lua",):
        t = re.sub(r"--.*", "", t)
    for m in re.finditer(r"(?:#|rgba\(|0x)(?:[0-9a-fA-F]{2})?([0-9a-fA-F]{6})(?:[0-9a-fA-F]{2})?(?![0-9a-fA-F])", t):
        c = m.group(1).lower()
        entero = re.sub(r"^(#|rgba\(|0x)", "", m.group(0)).lower()
        candidatos = {entero[:6], entero[2:8]} if len(entero) == 8 else {entero}
        if entero == "00000000":  # totalmente transparente: no aporta color
            continue
        if not (candidatos & MARINO):
            print(f"[FALLO] color ajeno {m.group(0)} en {f.relative_to(raiz)}")
            ajenos += 1
print(f"[OK]    {len(rutas)} archivos revisados" if not ajenos else f"[FALLO] {ajenos} colores ajenos")
PY

echo "== Fondo y cursores =="
FONDO=chroot/usr/share/backgrounds/jaime0/aurora.jpg
python3 - "$FONDO" <<'PY' && ok "fondo: JPEG 2560x1440" || fallo "fondo invalido"
import struct, sys
d = open(sys.argv[1], 'rb').read()
assert d[:3] == bytes([0xff, 0xd8, 0xff])
i = 2
while i < len(d):
    assert d[i] == 0xff
    marca = d[i + 1]
    largo = struct.unpack('>H', d[i + 2:i + 4])[0]
    if marca in (0xc0, 0xc1, 0xc2):
        alto, ancho = struct.unpack('>HH', d[i + 5:i + 9])
        assert (ancho, alto) == (2560, 1440), (ancho, alto)
        break
    i += 2 + largo
else:
    raise SystemExit(1)
PY
grep -q 'Tim Rains' chroot/usr/share/backgrounds/jaime0/CREDITOS.txt && grep -qi 'dominio publico' chroot/usr/share/backgrounds/jaime0/CREDITOS.txt && ok "creditos del fondo" || fallo "faltan los creditos del fondo"
grep -q '3380b169c328dd23a9ed4e991581c02185e09783cb1fb28b447c4c891f4282a1' config/hooks/normal/0350-fondo.hook.chroot && grep -q 'sha256sum -c' config/hooks/normal/0350-fondo.hook.chroot && ok "descarga del fondo fijada por SHA256" || fallo "descarga del fondo sin fijar"
grep -q 'local fondo       = "/usr/share/backgrounds/jaime0/aurora.jpg"' "$SKEL/.config/hypr/hyprland.lua" && grep -q 'swaybg --image " .. fondo .. " --mode fill' "$SKEL/.config/hypr/hyprland.lua" && ok "swaybg usa el fondo en el autostart" || fallo "swaybg sin el fondo"
C=chroot/usr/share/icons/Adwaita
[ -f "$C/index.theme" ] && [ "$(ls "$C/cursors" | wc -l)" -gt 50 ] && ok "cursor Adwaita: $(ls "$C/cursors" | wc -l) entradas" || fallo "cursores Adwaita incompletos"
[ -d chroot/usr/share/icons/catppuccin-mocha-blue-cursors ] && fallo "sigue el cursor Catppuccin" || ok "sin el cursor llamativo de antes"
chroot chroot cat /usr/share/icons/default/index.theme | grep -q 'Inherits=Adwaita' && ok "cursor por defecto del sistema: Adwaita" || fallo "cursor por defecto"
chroot chroot update-alternatives --query x-cursor-theme | grep -qE '^Value: /usr/share/icons/(Adwaita|jaime0-cursor)/cursor.theme$' && ok "alternativa x-cursor-theme apunta a Adwaita" || fallo "alternativa x-cursor-theme"
chroot chroot sh -c 'grep -q catppuccin /usr/share/icons/Adwaita/cursor.theme' && fallo "se altero el cursor.theme de Adwaita" || ok "cursor.theme de Adwaita intacto"
grep -q 'hl.env("XCURSOR_THEME", "Adwaita")' "$SKEL/.config/hypr/hyprland.lua" && ok "XCURSOR_THEME = Adwaita" || fallo "XCURSOR_THEME no es Adwaita"
for V in XCURSOR_THEME XCURSOR_SIZE QT_QPA_PLATFORMTHEME; do grep -q "hl.env(\"$V\"" "$SKEL/.config/hypr/hyprland.lua" && ok "hyprland.lua define $V" || fallo "falta $V"; done
chroot chroot sh -c 'fc-match sans-serif' | grep -qi jetbrains && ok "sans-serif resuelve a JetBrainsMono" || fallo "sans-serif no es JetBrainsMono"
grep -q '^fonts-inter' chroot.packages.live && fallo "fonts-inter sigue en la ISO" || ok "sin fonts-inter"
chroot chroot gsettings get org.gnome.desktop.interface font-name 2>/dev/null | grep -q 'JetBrainsMono' && ok "gsettings font-name monoespaciada" || fallo "gsettings font-name"
grep -q 'general="JetBrainsMono' "$SKEL/.config/qt6ct/qt6ct.conf" && ok "qt6ct con fuente monoespaciada" || fallo "qt6ct sin fuente monoespaciada"
readlink chroot/usr/share/icons/Papirus/48x48/places/folder.svg | grep -q 'folder-bluegrey' && ok "carpetas sobrias en Papirus" || fallo "carpetas de Papirus sin cambiar"
chroot chroot sh -c 'test -s /usr/share/icons/Papirus/48x48/places/folder.svg' && ok "enlace de carpeta valido" || fallo "enlace de carpeta roto"
chroot chroot sh -c 'fc-match monospace' | grep -qi jetbrains && ok "monospace resuelve a JetBrainsMono" || fallo "monospace no es JetBrainsMono"
for P in "gtk-theme|Adwaita-dark" "icon-theme|Papirus-Dark" "cursor-theme|Adwaita" "color-scheme|prefer-dark"; do
    K=${P%%|*}; V=${P#*|}
    chroot chroot gsettings get org.gnome.desktop.interface "$K" 2>/dev/null | grep -q "$V" && ok "gsettings $K = $V" || fallo "gsettings $K"
done

echo "== Fondo y acceso =="
[ -d chroot/usr/local/share/hypr ] && fallo "restos del generador antiguo del fondo" || ok "sin restos del generador antiguo"
grep -q "^python3-pil" chroot.packages.live && fallo "Pillow en la ISO" || ok "Pillow retirado tras preparar el fondo"
grep -q "^librsvg2-bin" chroot.packages.live && fallo "librsvg2-bin en la ISO" || ok "librsvg2-bin retirado tras generar la marca"
grep -q "border=magenta" chroot/etc/greetd/config.toml && grep -q "container=black" chroot/etc/greetd/config.toml && ok "tuigreet con colores de la paleta" || fallo "tuigreet sin tema"
grep -q -- "--greeting 'Jaime0'" chroot/etc/greetd/config.toml && ok "tuigreet saluda con Jaime0" || fallo "tuigreet sin saludo Jaime0"

echo "== Zsh por defecto =="
grep -qx 'SHELL=/bin/zsh' chroot/etc/default/useradd && ok "useradd: SHELL=/bin/zsh" || fallo "useradd"
grep -qx 'DSHELL=/bin/zsh' chroot/etc/adduser.conf && ok "adduser: DSHELL=/bin/zsh" || fallo "adduser"
grep -qx '/bin/zsh' chroot/etc/shells && ok "/bin/zsh en /etc/shells" || fallo "/etc/shells"

echo "== Deteccion de VM =="
[ "$(systemd-detect-virt --vm)" = "oracle" ] && ok "esta VM se detecta como oracle" || fallo "deteccion de VM: $(systemd-detect-virt --vm)"
grep -q 'systemd-detect-virt --vm' "$SKEL/.config/hypr/hyprland.lua" && ok "hyprland.lua detecta la VM" || fallo "hyprland.lua no detecta la VM"
# Para la prueba de hardware real: un detector falso que responde "none".
mkdir -p chroot/tmp/falso
printf '#!/bin/sh\necho none\nexit 1\n' > chroot/tmp/falso/systemd-detect-virt
chmod 755 chroot/tmp/falso chroot/tmp/falso/systemd-detect-virt

echo "== Preparar prueba en vivo =="
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

# Usuario nuevo real: sin -s, debe recibir zsh; con el GID real de render de la VM,
# igual que daria logind en un sistema de verdad.
GID_RENDER=$(stat -c %g /dev/dri/renderD128)
chroot chroot sh -c "getent group rendervm >/dev/null || groupadd -o -g $GID_RENDER rendervm"
chroot chroot sh -c 'userdel -r ricer 2>/dev/null; useradd -m -k /etc/skel -G video,render,input,rendervm ricer'
[ "$(chroot chroot getent passwd ricer | cut -d: -f7)" = "/bin/zsh" ] && ok "useradd sin -s da zsh" || fallo "shell del usuario nuevo: $(chroot chroot getent passwd ricer | cut -d: -f7)"
[ -f chroot/home/ricer/.zshrc ] && [ "$(stat -c %U chroot/home/ricer/.zshrc)" != "root" ] && ok "el usuario nuevo hereda /etc/skel" || fallo "usuario nuevo sin /etc/skel"
chroot chroot sh -c 'rm -f /run/seatd.sock; nohup seatd -g video >/tmp/seatd.log 2>&1 &'
chroot chroot sh -c 'mkdir -p /run/dbus; rm -f /run/dbus/system_bus_socket /run/dbus/pid; dbus-daemon --system --fork; /usr/libexec/bluetooth/bluetoothd >/dev/null 2>&1 &'
sleep 2

echo "== Prueba en vivo =="
cp verificar-aspecto-en-vivo.sh chroot/tmp/vivo5.sh; chmod 755 chroot/tmp/vivo5.sh
rm -rf chroot/tmp/vs5x; mkdir -p chroot/tmp/vs5x; chown "$(chroot chroot id -u ricer)" chroot/tmp/vs5x
chroot --userspec=ricer:ricer chroot env HOME_PRUEBA=/home/ricer /tmp/vivo5.sh 2>&1 | tee -a "$SALIDA"
mkdir -p capturas-aspecto; cp chroot/tmp/vs5x/*.png capturas-aspecto/ 2>/dev/null; cp chroot/tmp/vs5x/*.log chroot/tmp/vs5x/*.txt capturas-aspecto/ 2>/dev/null; chmod -R a+rX capturas-aspecto

F=$(grep -c '^\[FALLO\]' "$SALIDA"); O=$(grep -c '^\[OK\]' "$SALIDA")
echo
echo "RESULTADO: ${F} fallo(s), ${O} correctos"
[ "$F" -eq 0 ]

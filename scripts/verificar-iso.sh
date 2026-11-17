#!/bin/bash
# Verifica una ISO de ZYRON YA GENERADA, sin arrancarla: que una ISO se haya creado sin
# errores no basta para darla por buena. No necesita root ni modifica la ISO.
#
#     scripts/verificar-iso.sh ZYRON.iso                 comprobaciones de la imagen
#     scripts/verificar-iso.sh ZYRON.iso --repo .        ademas, comparada con el repositorio
#
# Comprueba: arranque BIOS y UEFI (El Torito, shim, GRUB, nucleo e initrd), que el sistema
# de archivos se lee entero, los archivos imprescindibles y sus permisos, que no haya claves
# privadas, la version, y con --repo que esten los paquetes de config/package-lists y los
# archivos de config/includes.chroot_after_packages (las diferencias se listan).
# Necesita: xorriso, unsquashfs (squashfs-tools) y sha256sum.
set -u
ISO=${1:-}
REPO=""
[ "${2:-}" = "--repo" ] && REPO=$(readlink -f "${3:-.}")
[ -f "$ISO" ] || { echo "Uso: $0 ZYRON.iso [--repo CARPETA]" >&2; exit 2; }
for H in xorriso unsquashfs sha256sum; do
    command -v "$H" >/dev/null 2>&1 || { echo "falta $H" >&2; exit 2; }
done

FALLOS=0; OKS=0
ok()     { printf '[OK]    %s\n' "$*"; OKS=$((OKS + 1)); }
fallo()  { printf '[FALLO] %s\n' "$*"; FALLOS=$((FALLOS + 1)); }
aviso()  { printf '[AVISO] %s\n' "$*"; }
seccion() { printf '\n== %s ==\n' "$*"; }

T=$(mktemp -d)
trap 'rm -rf "$T"' EXIT

seccion "Imagen"
printf 'Archivo: %s\nTamano:  %s bytes\nSHA-256: %s\n' "$ISO" "$(stat -c %s "$ISO")" "$(sha256sum "$ISO" | cut -d' ' -f1)"
for S in "$ISO.sha256" "$(dirname "$ISO")/SHA256SUMS"; do
    if [ -f "$S" ]; then
        ESPERADO=$(grep -oE '^[0-9a-f]{64}' "$S" | head -n 1)
        [ "$ESPERADO" = "$(sha256sum "$ISO" | cut -d' ' -f1)" ] && ok "la suma coincide con $S" || fallo "la suma no coincide con $S"
    fi
done
[ "$(stat -c %s "$ISO")" -gt 500000000 ] && ok "tamano razonable" || fallo "la ISO es sospechosamente pequena"

seccion "Arranque"
xorriso -indev "$ISO" -report_el_torito plain > "$T/torito" 2>/dev/null
grep -qiE 'El Torito boot img.*BIOS' "$T/torito" && ok "arranque BIOS (El Torito)" || fallo "sin entrada de arranque BIOS"
grep -qiE 'El Torito boot img.*UEFI' "$T/torito" && ok "arranque UEFI (El Torito)" || fallo "sin entrada de arranque UEFI"
xorriso -indev "$ISO" -find / -type f 2>/dev/null | sed "s/^'//; s/'$//" > "$T/archivos"
for F in /live/filesystem.squashfs /boot/grub/grub.cfg /EFI/boot/bootx64.efi /EFI/boot/grubx64.efi; do
    grep -qixF "$F" "$T/archivos" && ok "$F" || fallo "falta $F en la ISO"
done
grep -qE '^/live/vmlinuz' "$T/archivos" && ok "nucleo en /live" || fallo "falta el nucleo (/live/vmlinuz*)"
grep -qE '^/live/initrd' "$T/archivos" && ok "initrd en /live" || fallo "falta el initrd (/live/initrd*)"
xorriso -osirrox on -indev "$ISO" -extract /boot/grub/grub.cfg "$T/grub.cfg" >/dev/null 2>&1
grep -q 'ZYRON' "$T/grub.cfg" 2>/dev/null && ok "menu de arranque con ZYRON" || fallo "menu de arranque sin ZYRON"

seccion "Sistema de archivos"
if ! xorriso -osirrox on -indev "$ISO" -extract /live/filesystem.squashfs "$T/fs.squashfs" >/dev/null 2>&1; then
    fallo "no se pudo extraer filesystem.squashfs"
    printf '\nRESULTADO: %s fallo(s), %s correctos\n' "$FALLOS" "$OKS"; exit 1
fi
if unsquashfs -lls -d "" "$T/fs.squashfs" > "$T/lista" 2>"$T/err" && [ -s "$T/lista" ]; then
    ok "squashfs legible ($(wc -l < "$T/lista") entradas)"
else
    fallo "squashfs ilegible: $(head -n 2 "$T/err")"
fi
# "permisos usuario/grupo tamano fecha hora /ruta" -> por ruta
awk '{ r = $6; for (i = 7; i <= NF; i++) r = r " " $i; print $1 "\t" $2 "\t" r }' "$T/lista" > "$T/rutas"
esta()     { grep -qP "\t\Q$1\E$" "$T/rutas"; }
permisos() { grep -P "\t\Q$1\E$" "$T/rutas" | head -n 1 | cut -f1; }
duenyo()   { grep -P "\t\Q$1\E$" "$T/rutas" | head -n 1 | cut -f2; }

seccion "Archivos imprescindibles y permisos"
for P in jaime0-servicio jaime0-salud jaime0-control jaime0-perfil jaime0-privacidad jaime0-reglas jaime0-ajustes \
         jaime0-diagnostico jaime0-nvidia jaime0-widgets jaime0-osd actualizaciones inactividad bloqueo bloquear prime-run instalar-sistema; do
    [ "$P" = bloqueo ] && continue
    if esta "/usr/local/bin/$P"; then
        case "$(permisos "/usr/local/bin/$P")" in -rwxr-xr-x) ok "/usr/local/bin/$P (755)" ;; *) fallo "/usr/local/bin/$P con permisos $(permisos "/usr/local/bin/$P")" ;; esac
    else
        fallo "falta /usr/local/bin/$P"
    fi
done
for F in /etc/skel/.config/hypr/hyprland.lua /etc/skel/.config/hypr/hypridle.conf /etc/skel/.config/waybar/config.jsonc \
         /usr/share/jaime0/ajustes.predeterminados /usr/share/jaime0/version /usr/share/jaime0/control/shell.qml \
         /usr/lib/systemd/user/jaime0-servicio.service /etc/calamares/settings.conf /usr/local/sbin/hypr-instalar-grub \
         /usr/local/libexec/jaime0-ufw-estado /usr/share/polkit-1/actions/es.jaime0.ufw-estado.policy; do
    esta "$F" && ok "$F" || fallo "falta $F"
done
# Lo que se ejecuta como root no puede ser de otro usuario ni escribible por otros.
for F in /usr/local/libexec/jaime0-ufw-estado /usr/local/sbin/hypr-instalar-grub /usr/local/sbin/hypr-limpiar-vivo; do
    if esta "$F"; then
        [ "$(duenyo "$F")" = "root/root" ] && ok "$F es de root" || fallo "$F es de $(duenyo "$F")"
        case "$(permisos "$F")" in ?????w????|????????w?) fallo "$F escribible por el grupo u otros" ;; esac
    fi
done
if grep -P '\t/usr/local/lib/jaime0' "$T/rutas" | cut -f1 | grep -qE '^d.......w.|^-.......w.'; then
    fallo "hay archivos de /usr/local/lib/jaime0 escribibles por todos"
else
    ok "/usr/local/lib/jaime0 sin permisos de escritura para otros"
fi

seccion "Secretos"
for F in /var/lib/dkms/mok.key /var/lib/dkms/mok.pub; do
    esta "$F" && fallo "$F dentro de la imagen" || ok "sin $F"
done
unsquashfs -q -n -d "$T/raiz" "$T/fs.squashfs" etc usr/share/jaime0 usr/local >/dev/null 2>&1
if grep -rlE -- '-----BEGIN ([A-Z0-9]+ )?PRIVATE KEY-----' "$T/raiz/etc" "$T/raiz/usr/share/jaime0" "$T/raiz/usr/local" 2>/dev/null \
        | grep -vE '/etc/ssl/' | sed "s|$T/raiz||" > "$T/claves" && [ -s "$T/claves" ]; then
    fallo "claves privadas en la imagen: $(tr '\n' ' ' < "$T/claves")"
else
    ok "sin claves privadas en /etc, /usr/share/jaime0 ni /usr/local"
fi

seccion "Version"
V=$(cat "$T/raiz/usr/share/jaime0/version" 2>/dev/null | head -n 1)
if [ -n "$V" ]; then
    ok "version $V"
    case "$(basename "$ISO")" in *"$V"*) ok "el nombre de la ISO lleva la version" ;; *-amd64.hybrid.iso) aviso "ISO sin renombrar (la de lb build): no se comprueba el nombre" ;; *) fallo "el nombre de la ISO no lleva la version $V" ;; esac
else
    fallo "sin /usr/share/jaime0/version"
fi

if [ -n "$REPO" ]; then
    seccion "Paquetes de config/package-lists"
    unsquashfs -q -n -d "$T/dpkg" "$T/fs.squashfs" var/lib/dpkg/status >/dev/null 2>&1
    awk '/^Package: /{p=$2} /^Status: (install|hold) ok installed/{print p}' "$T/dpkg/var/lib/dpkg/status" 2>/dev/null | sort -u > "$T/instalados"
    if [ -s "$T/instalados" ]; then
        FALTAN=$(grep -hvE '^\s*(#|$)' "$REPO"/config/package-lists/*.list.chroot | sort -u | comm -23 - "$T/instalados")
        [ -z "$FALTAN" ] && ok "todos los paquetes de las listas instalados ($(wc -l < "$T/instalados") en total)" \
            || fallo "paquetes de las listas que no estan: $(echo "$FALTAN" | tr '\n' ' ')"
    else
        fallo "no se pudo leer el estado de dpkg de la imagen"
    fi

    seccion "Archivos del repositorio frente a la ISO"
    I="$REPO/config/includes.chroot_after_packages"
    (cd "$I" && find . -type f ! -name '*.pyc' | sed 's|^\.||' | sort) > "$T/repo"
    cut -f3 "$T/rutas" | sort -u > "$T/iso"
    comm -23 "$T/repo" "$T/iso" > "$T/solo_repo"
    if [ -s "$T/solo_repo" ]; then
        aviso "$(wc -l < "$T/solo_repo") archivo(s) del repositorio que esta ISO no tiene (normal si la ISO es anterior):"
        sed 's/^/          /' "$T/solo_repo" | head -n 40
    else
        ok "todos los archivos del repositorio estan en la ISO"
    fi
    DIST=0
    while read -r F; do
        [ -f "$T/raiz$F" ] || continue
        cmp -s "$I$F" "$T/raiz$F" || { [ "$DIST" -lt 40 ] && echo "          distinto: $F"; DIST=$((DIST + 1)); }
    done < <(grep -E '^/(etc|usr/share/jaime0|usr/local)/' "$T/repo")
    [ "$DIST" -eq 0 ] && ok "los archivos comunes son identicos" || aviso "$DIST archivo(s) distintos entre el repositorio y la ISO"
fi

printf '\nRESULTADO: %s fallo(s), %s correctos\n' "$FALLOS" "$OKS"
[ "$FALLOS" -eq 0 ]

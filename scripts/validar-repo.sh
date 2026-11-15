#!/bin/bash
# Comprobaciones del repositorio que no necesitan compilar la ISO. Las ejecuta GitHub
# Actions en cada push y solicitud de integracion (.github/workflows/validar.yml) y se
# pueden lanzar a mano desde la raiz del repositorio:
#     scripts/validar-repo.sh
# Necesita: git, python3 (>= 3.11), shellcheck y luac (lua5.4). No publica nada.
set -u
cd "$(dirname "$(readlink -f "$0")")/.." || exit 1

FALLOS=0
ok()     { printf '[OK]    %s\n' "$*"; }
fallo()  { printf '[FALLO] %s\n' "$*"; FALLOS=$((FALLOS + 1)); }
aviso()  { printf '[AVISO] %s\n' "$*"; }
seccion() { printf '\n== %s ==\n' "$*"; }

I=config/includes.chroot_after_packages

# Archivos que se ejecutan: programas, hooks, live-config, auto/ y scripts de prueba.
ejecutables() {
    git ls-files "$I/usr/local/bin" "$I/usr/local/sbin" "$I/usr/lib/live/config" config/hooks auto scripts \
        | grep -vE '^scripts/coords-[a-z]+\.sh$|\.py$'
}
# "#!/bin/sh", "#!/usr/bin/python3 -I" o "#!/usr/bin/env python3" -> sh, python3...
interprete() {
    head -n 1 "$1" | sed -nE -e 's|^#! *(/usr)?/bin/env +([a-z0-9]+).*|\2|p;t' -e 's|^#! *(/usr)?/bin/([a-z0-9]+).*|\2|p'
}

seccion "Permisos de ejecucion (en git)"
N=0
while read -r F; do
    M=$(git ls-files -s -- "$F" | cut -d' ' -f1)
    [ "$M" = "100755" ] || { fallo "$F no es ejecutable en git ($M)"; N=$((N + 1)); }
done < <(ejecutables)
[ "$N" -eq 0 ] && ok "todos los programas, hooks y scripts son ejecutables"

seccion "Finales de linea y secretos"
CRLF=$(git ls-files -z | xargs -0 grep -IlU $'\r' 2>/dev/null || true)
[ -z "$CRLF" ] && ok "sin CRLF" || fallo "archivos con CRLF: $CRLF"
if grep -rIlE -- '-----BEGIN ([A-Z0-9]+ )?PRIVATE KEY-----' config/ >/dev/null; then
    fallo "hay una clave privada dentro de config/"
else
    ok "sin claves privadas en config/"
fi

seccion "Shell (shellcheck)"
if command -v shellcheck >/dev/null 2>&1; then
    PRODUCTO=() PRUEBAS=()
    while read -r F; do
        case "$(interprete "$F")" in
            sh|bash|dash) case "$F" in scripts/*) PRUEBAS+=("$F") ;; *) PRODUCTO+=("$F") ;; esac ;;
        esac
    done < <(ejecutables)
    # Lo que va en la ISO: sin avisos. Las pruebas: sin errores (los avisos se muestran).
    if shellcheck -S warning "${PRODUCTO[@]}"; then ok "${#PRODUCTO[@]} scripts de la ISO sin avisos"; else fallo "shellcheck en scripts de la ISO"; fi
    if shellcheck -S error "${PRUEBAS[@]}"; then ok "${#PRUEBAS[@]} scripts de prueba sin errores"; else fallo "shellcheck en scripts de prueba"; fi
    AV=$(shellcheck -S warning -f gcc "${PRUEBAS[@]}" 2>/dev/null | wc -l)
    [ "$AV" -gt 0 ] && aviso "$AV avisos de shellcheck en scripts de prueba (no bloquean)"
else
    fallo "falta shellcheck"
fi

seccion "Python"
PY=()
while read -r F; do [ "$(interprete "$F")" = "python3" ] && PY+=("$F"); done < <(ejecutables)
PY+=(scripts/*.py pruebas/*.py)
if python3 - "${PY[@]}" <<'FIN'
import sys
for f in sys.argv[1:]:
    compile(open(f, encoding="utf-8").read(), f, "exec")
FIN
then ok "${#PY[@]} archivos Python sin errores de sintaxis"; else fallo "sintaxis de Python"; fi
if python3 -m unittest discover -s pruebas 2>&1 | tail -n 3 | tee /tmp/validar-pruebas.$$ | grep -q '^OK'; then
    ok "pruebas automaticas: $(grep -E '^OK' /tmp/validar-pruebas.$$)"
else
    fallo "pruebas automaticas"; cat /tmp/validar-pruebas.$$
fi
rm -f /tmp/validar-pruebas.$$

seccion "Configuraciones"
python3 - "$I/etc/skel/.config" publicaciones <<'FIN' && ok "JSON, JSONC y TOML validos" || fallo "JSON, JSONC o TOML invalido"
import json, pathlib, re, sys, tomllib
skel, pub = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
error = False
def jsonc(p):
    # Comentarios de linea completa (//) como los de Waybar y fastfetch.
    return json.loads(re.sub(r"^\s*//.*$", "", p.read_text(encoding="utf-8"), flags=re.M))
for p in sorted(skel.rglob("*.json")) + sorted(skel.rglob("*.jsonc")):
    try:
        (json.loads(p.read_text(encoding="utf-8")) if p.suffix == ".json" else jsonc(p))
    except ValueError as e:
        print(f"  {p}: {e}"); error = True
for p in sorted(pub.glob("*.toml")):
    try:
        tomllib.loads(p.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as e:
        print(f"  {p}: {e}"); error = True
sys.exit(1 if error else 0)
FIN
if command -v luac >/dev/null 2>&1 || command -v luac5.4 >/dev/null 2>&1; then
    LUAC=$(command -v luac || command -v luac5.4)
    for F in "$I/etc/skel/.config/hypr/hyprland.lua" "$I/etc/skel/.config/nvim/init.lua"; do
        "$LUAC" -p "$F" && ok "Lua: $F" || fallo "Lua con errores: $F"
    done
else
    fallo "falta luac"
fi
# Cada lista de paquetes: un nombre de paquete por linea.
if grep -vhE '^([a-z0-9][a-z0-9.+-]*|#.*|)$' config/package-lists/*.list.chroot; then
    fallo "lineas raras en config/package-lists"
else
    ok "listas de paquetes bien formadas"
fi

seccion "QML"
# Cada componente que se carga por nombre de archivo existe junto a quien lo usa.
N=0
for D in "$I/usr/share/jaime0/ajustes-gui" "$I/usr/share/jaime0/widgets"; do
    [ -f "$D/shell.qml" ] || { fallo "falta $D/shell.qml"; N=$((N + 1)); }
    for Q in $(grep -ohE '"[A-Z][A-Za-z]+\.qml"' "$D"/*.qml | tr -d '"' | sort -u); do
        [ -f "$D/$Q" ] || { fallo "$D: falta $Q"; N=$((N + 1)); }
    done
done
[ "$N" -eq 0 ] && ok "componentes QML presentes"

seccion "Archivos imprescindibles"
for F in auto/config auto/build \
         "$I/etc/skel/.config/hypr/hyprland.lua" "$I/etc/skel/.config/hypr/hyprlock.conf" "$I/etc/skel/.config/hypr/hypridle.conf" \
         "$I/etc/skel/.config/waybar/config.jsonc" "$I/etc/skel/.config/waybar/style.css" \
         "$I/etc/skel/.config/swaync/config.json" "$I/etc/skel/.config/swaync/style.css" \
         "$I/usr/share/jaime0/ajustes.predeterminados" "$I/usr/share/jaime0/version" \
         "$I/usr/share/backgrounds/jaime0/jaime0.png"; do
    [ -f "$F" ] || fallo "falta $F"
done
for P in actualizaciones jaime0-servicio jaime0-salud jaime0-control jaime0-perfil jaime0-ajustes jaime0-anclar jaime0-widgets jaime0-tiempo jaime0-osd jaime0-diagnostico jaime0-nvidia prime-run notificaciones bloquear inactividad atajos; do
    [ -f "$I/usr/local/bin/$P" ] || fallo "falta el programa $P"
done
ok "archivos imprescindibles revisados"

printf '\nRESULTADO: %s fallo(s)\n' "$FALLOS"
[ "$FALLOS" -eq 0 ]

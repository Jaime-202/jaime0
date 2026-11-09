#!/bin/bash
# Prueba de "atajos" dentro de una sesion real de Hyprland (la lanza s11-previa-dentro.sh
# en modo "prueba"). Escribe [OK]/[FALLO] en la salida.
ok()    { echo "[OK]    $1"; }
fallo() { echo "[FALLO] $1"; }
tiene() { hyprctl binds -j | python3 -c "import json,sys; d=json.load(sys.stdin); sys.exit(0 if any(b.get('modmask')==64 and (b.get('key') or '').lower()=='o' and b.get('description')=='Abrir btop' for b in d) else 1)"; }

S=$(atajos 2>&1); N=$(echo "$S" | grep -c 'SUPER')
[ "$N" -ge 35 ] && ok "atajos lista $N atajos de la configuracion real" || fallo "atajos lista $N"
echo "$S" | grep -q 'Ver todos los atajos' && ok "la lista muestra las descripciones" || fallo "lista sin descripciones"
echo "$S" | head -6

S=$(atajos añadir "SUPER+Q" "kitty" "duplicado" 2>&1); RC=$?
[ $RC -eq 3 ] && echo "$S" | grep -q 'ya está en uso: Cerrar la ventana' && ok "avisa de que SUPER+Q ya existe" || fallo "duplicado del sistema: rc=$RC $S"

S=$(atajos añadir "SUPER+O" "kitty -e btop" "Abrir btop" 2>&1); RC=$?
[ $RC -eq 0 ] && ok "añade SUPER+O: $S" || fallo "añadir: rc=$RC $S"
sleep 2
tiene && ok "Hyprland recargado: SUPER+O activo con su descripcion" || fallo "SUPER+O no aparece en hyprctl binds"
atajos | grep -q 'SUPER + O .*Abrir btop.*★' && ok "la lista marca SUPER+O como propio" || fallo "lista sin SUPER+O propio"

S=$(atajos quitar "SUPER+O" 2>&1); RC=$?
[ $RC -eq 0 ] && ok "quita SUPER+O" || fallo "quitar: rc=$RC $S"
sleep 2
tiene && fallo "SUPER+O sigue activo tras quitarlo" || ok "SUPER+O ya no esta activo"
E=$(hyprctl configerrors | grep -v '^$' | grep -vi 'no errors' | head -3)
[ -z "$E" ] && ok "sin errores de configuracion tras las recargas" || fallo "configerrors: $E"

#!/bin/bash
# Ejecuta todas las verificaciones sobre el chroot que deja lb build. Desde la carpeta de
# trabajo y con sudo disponible. Instalan herramientas de prueba en chroot/: la ISO debe
# generarse antes, nunca despues. Resumen en verificar-todo.log.
cd "$(dirname "$(readlink -f "$0")")" || exit 1
T=verificar-todo.log; : > "$T"
FALLOS=0
for n in repos software aspecto grafico barra instalador identidad atajos hardware actualizador; do
    sudo ./verificar-$n.sh > verificar-$n.log 2>&1; R=$?
    [ "$R" -ne 0 ] && FALLOS=$((FALLOS+1))
    echo "$n rc=$R $(date +%T) $(grep RESULTADO verificar-$n.log)" | tee -a "$T"
done
echo "SCRIPTS_CON_FALLOS=$FALLOS" | tee -a "$T"
[ "$FALLOS" -eq 0 ]

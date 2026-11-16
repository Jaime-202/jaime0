# Evolución del sistema (fases 1 a 10)

Auditoría, refactorización y evolución de Jaime0 sobre la 0.4.0-beta.1, hecha en noviembre de 2026. Objetivo: que cada función, nueva o existente, sea útil, estable, coherente y esté bien integrada, sin añadir funciones por tenerlas. Este documento resume qué cambió y por qué; el detalle de cada parte está en su guía.

## Resumen por fase

| Fase | Qué se hizo | Guía |
|---|---|---|
| 1 · Auditoría | Revisión de arquitectura, servicio, reglas, actualizaciones, diagnóstico, energía, interfaz, instalador, hardware y accesibilidad; problemas priorizados | — |
| 2 · Servicio desacoplado | `jaime0-servicio` pasa de un archivo de 5 000 líneas a un paquete por módulos en un solo proceso, con un hilo de efectos para todo lo que puede colgarse: el socket ya no espera (3,05 s → 0,00 s con `swaync-client` colgado) | [control-center.md](control-center.md) |
| 3 · Reglas | Conflictos resueltos por prioridad (alta, normal, baja) con motivo visible, reglas duplicadas rechazadas, resumen y próxima ejecución | [control-center.md](control-center.md) |
| 4 · Update Manager | `jaime0-update` recuperado (manifiesto firmado, tres sumas por archivo, copias y reversión) e integrado como sección UPDATES; instalar y revertir piden autorización en una terminal | [actualizaciones.md](actualizaciones.md) |
| 5 · Diagnostics | `jaime0-diagnostico comprobar`: problemas con gravedad, lo detectado, causas posibles (no confirmadas), consecuencias y qué hacer; reparaciones con órdenes visibles, confirmación y copia; historial con repeticiones; sección DIAGNOSTICS y aviso en SYSTEM | [diagnostico.md](diagnostico.md) |
| 6 · Power Manager | Sección POWER: batería en detalle con el origen de cada dato (medido, calculado, estimado, N/D), gráficas y PRIME sin despertar la NVIDIA, inactividad configurable, histórico por perfil de energía; un único dueño por ajuste | [energia.md](energia.md) |
| 7 · Reorganización | Una responsabilidad por sección: SYSTEM resume, PERFORMANCE lo de ahora (tabla de procesos), HEALTH la evolución, PRIVACY en tres categorías con cinco estados | [control-center.md](control-center.md) |
| 8 · Instalador y hardware | Pruebas de integridad del instalador y de dependencias en GitHub Actions, verificación de la ISO terminada (`verificar-iso.sh`), sesión ampliada y capa de detección de hardware | [pruebas.md](pruebas.md) |
| 9 · Accesibilidad | Contraste ≥ 4,5:1, texto ≥ 10 px, todo con teclado (Tab, Intro, Ctrl+Tab), escala de la ventana, leyendas y marcas además del color, movimiento solo con «suave» | [control-center.md](control-center.md) |
| 10 · Validación final | Pruebas completas, medidas, dependencias, documentación, ISO nueva verificada, arrancada e instalada en una VM | este documento |

## Decisiones de arquitectura

- **Un solo proceso, sin servicios nuevos.** Todo lo nuevo (actualizaciones, diagnóstico, energía, hardware) son módulos de `jaime0-servicio` o programas que se ejecutan y terminan. Lo lento va en hilos propios (comprobación de actualizaciones, diagnóstico) o en el hilo de efectos; el bucle de medidas y el socket nunca esperan.
- **Nada se repara ni se instala sin permiso.** Las acciones con privilegios (instalar, revertir, reparar) abren una terminal que enseña las órdenes y pide confirmación.
- **Un dueño por ajuste.** El perfil de energía lo pone el perfil de Jaime0; la inactividad, `jaime0-ajustes`; las reacciones a la batería y al cargador, las reglas. POWER muestra y elige, no duplica.
- **Datos reales o nada.** Cada dato dice si es medido, calculado o estimado; lo que no existe sale como N/D, NO DISPONIBLE o NOT APPLICABLE, nunca como un problema ni como una protección.

## Medidas finales (VM, 4 GiB, 4 CPU, sesión en vivo con todos los cambios)

| Medida | Resultado |
|---|---|
| `jaime0-servicio`, Control Center cerrado | 0,16 % de CPU, 41 MiB, 5 hilos |
| `jaime0-servicio`, ventana abierta (muestra cada 2 s) | 0,87 % de CPU, 45 MiB |
| Ventana del Control Center | 0,68 % de CPU, 133 MiB |
| Procesos propios en segundo plano | `jaime0-servicio`, `jaime0-anclar`, `notificaciones` e `iniciar-sesion` (los mismos que antes de la evolución) |
| Órdenes del socket | estado 3 ms, instante 1 ms, serie 2 ms, procesos 2 ms, hardware 4 ms, energía 71 ms, privacidad 184 ms, actualizaciones 183 ms, reglas 101 ms, diagnóstico completo 0,94 s |
| Pruebas automáticas | 775, en Windows y en Linux (20 pasadas seguidas sin fallos) |

## ISO e instalación (16-11-2026)

ISO de prueba compilada con todo lo de las fases 2 a 9 (no es una versión nueva: sigue llamándose 0.4.0-beta.1). La compilación tardó 19 min.

| Prueba | Resultado |
|---|---|
| `verificar-iso.sh --repo` | 48 correctos, 0 fallos: arranque BIOS y UEFI, sistema de archivos, permisos, sin claves, los 1 083 paquetes de las listas; solo difieren los archivos cambiados después de compilar |
| Sesión en vivo, `verificar-sesion.sh` | 49 correctos, 0 fallos |
| Instalación con el instalador gráfico (UEFI, disco entero, ext4) | Terminada en 5 min 30 s, los 38 pasos, incluido el módulo de NVIDIA |
| Primer arranque del sistema instalado | Hasta tuigreet y la sesión; 0 servicios fallidos |
| Tiempo de arranque | 11,7 s (5,3 s núcleo + 6,4 s sistema). El primer arranque dio 65 s por una parada de 45 s de la CPU virtual (`soft lockup` en el registro del núcleo); en el siguiente no se repitió |
| Sistema instalado, `verificar-sesion.sh` | 49 correctos, 0 fallos; hypridle usa los tiempos generados por `jaime0-ajustes` |
| Memoria con la sesión abierta | 632 MiB (la 0.3 usaba 815 MiB en la misma prueba) |

Encontrado al instalar: el paso `hwclock` del instalador fallaba (sin consecuencias, pero el reloj del equipo no se ajustaba) porque `hwclock` está en `util-linux-extra`, que no se instalaba. Añadido a `base.list.chroot`, con una prueba que exige el paquete de cada herramienta que usan los pasos del instalador. Este cambio no está en la ISO probada.

## Lo que queda

- **Probar en el portátil** (Acer Nitro AN515-55): NVIDIA y PRIME, batería real (descarga, consumo, comparación por perfil), sensores y ventiladores, suspensión, escala 1,25 y el 115/130 % del Control Center.
- **Instalador gráfico:** la instalación con Calamares no está automatizada; se prueba a mano en una VM. Su configuración y su resultado sí se comprueban solos.
- **Publicar:** los commits de la evolución son locales; subirlos, compilar la ISO de la próxima versión y publicarla es decisión del autor.

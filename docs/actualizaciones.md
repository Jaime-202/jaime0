# Actualizaciones: `jaime0-update`

`jaime0-update` actualiza un Jaime0 ya instalado sin descargar la ISO ni reinstalar. Se encarga de dos cosas distintas:

| Qué | Cómo se actualiza |
|---|---|
| **Componentes propios de Jaime0**: configuración de Hyprland, Waybar y demás programas (`/etc/skel` y tu `~/.config`), scripts de `/usr/local/bin`, temas, fondo, unidades de systemd propias | Publicaciones firmadas de GitHub Releases |
| **Paquetes de Debian**: kernel, Hyprland, Waybar, programas y bibliotecas | `apt`, el gestor oficial de Debian. `jaime0-update` solo te lo ofrece al final |

No hay un gestor de paquetes paralelo ni `git pull` sobre el sistema.

## Uso

```bash
jaime0-update
```

Busca la versión más nueva de tu canal y te enseña la versión, el canal, la fecha, los cambios, los componentes afectados, los requisitos y los problemas conocidos. Después lista qué archivos cambian y te pide confirmación. Instala la parte del sistema (pide la clave de `sudo`), luego tu configuración personal y, por último, te ofrece actualizar los paquetes con `apt`.

| Orden | Para qué |
|---|---|
| `jaime0-update` | Buscar, revisar e instalar |
| `jaime0-update --revisar` | Igual, pero muestra las diferencias de cada archivo antes de preguntar |
| `jaime0-update --detalle` | Lista todos los archivos que cambian |
| `jaime0-update --sin-paquetes` | No ofrece `apt` al final |
| `jaime0-update comprobar` | Solo mira si hay versión nueva (código 100 si la hay) |
| `jaime0-update cambios [VERSIÓN]` | Notas de la versión disponible o de una concreta |
| `jaime0-update estado` | Versión instalada, canal, conflictos y si quedó algo a medias |
| `jaime0-update canal [stable\|beta\|experimental]` | Ver o cambiar el canal |
| `jaime0-update conflictos` | Archivos tuyos que no se han sobrescrito |
| `jaime0-update resolver RUTA --diferencias\|--usar-nueva\|--mantener` | Resolver un conflicto |
| `jaime0-update historial` | Registro de operaciones |
| `jaime0-update barra` | Estado para el icono de la barra (sin red) |
| `jaime0-update revertir [--usuario]` | Deshacer la última actualización de los archivos de Jaime0 |
| `jaime0-update recuperar` | Deshacer una actualización que se cortó a medias |
| `jaime0-update usuario` | Aplicar a tu carpeta la configuración nueva (útil para otros usuarios del equipo) |

`-s` / `--si` responde que sí a todo. Sin terminal interactiva, si no lo pones, no se instala nada.

## Canales

| Canal | Recibe | Etiqueta en GitHub |
|---|---|---|
| `stable` (por defecto) | Solo versiones estables | `vX.Y.Z` |
| `beta` | Estables y beta | `vX.Y.Z-beta.N` (pre-release) |
| `experimental` | Todo, incluidas las experimentales | `vX.Y.Z-exp.N` (pre-release) |

El canal está en `/etc/jaime0/update.conf` y se cambia con `jaime0-update canal`. Un sistema en `stable` nunca recibe una beta ni una experimental: el canal va **dentro del manifiesto firmado** y se comprueba que corresponda a la versión. Al volver a un canal más estable no se desinstala nada: recibes la siguiente versión de ese canal cuando sea más nueva que la tuya.

Orden de versiones: `0.3.0-exp.1 < 0.3.0-beta.1 < 0.3.0 < 0.3.1`.

## Aviso de versiones nuevas

El temporizador de usuario `jaime0-update-aviso.timer` comprueba una vez al día (y 10 minutos después de entrar) si hay versión nueva en tu canal. Si la hay, muestra **una sola notificación por versión** con el número y el canal. El botón *Ver los cambios* abre una terminal con las notas. **Nunca instala nada.**

Además, un icono discreto aparece en la barra (a la izquierda de la campana) mientras haya una versión más nueva que la instalada. **Solo informa:** al pulsarlo se abre una terminal con `jaime0-update comprobar`, que muestra los cambios; para instalar hay que ejecutar `jaime0-update` y confirmar. La barra no consulta la red: lee lo que encontró la última comprobación (`jaime0-update barra`) y, al actualizar, el icono desaparece solo.

Para desactivarlo: `systemctl --user disable --now jaime0-update-aviso.timer`.

## Tus personalizaciones están protegidas

Cada archivo se clasifica comparando tres huellas SHA-256: la del archivo en tu disco, la de la versión nueva y las de **todas las versiones oficiales anteriores** (el manifiesto lleva ese histórico).

| Situación | Qué hace |
|---|---|
| Está como en alguna versión oficial (no lo has tocado) | Se reemplaza por el nuevo (con copia) |
| Lo has cambiado tú | **No se toca.** El nuevo se deja al lado como `ARCHIVO.jaime0-nuevo` y queda anotado como conflicto |
| Es nuevo en esta versión | Se crea |
| Lo borraste tú (en tu carpeta o en `/etc`) | No se vuelve a crear |
| Un archivo de sistema de `/usr` borrado | Se repone |
| Jaime0 lo retira y no lo has tocado | Se borra (con copia) |
| Jaime0 lo retira pero lo has cambiado | Se conserva |
| Es un enlace simbólico, o su carpeta apunta fuera de tu carpeta personal | No se toca |
| `/etc/jaime0/update.conf` | Solo se crea si falta: tu canal no cambia |

Para resolver un conflicto:

```bash
jaime0-update conflictos
jaime0-update resolver ~/.config/hypr/hyprland.lua --diferencias
jaime0-update resolver ~/.config/hypr/hyprland.lua --usar-nueva   # guarda copia de la tuya
jaime0-update resolver ~/.config/hypr/hyprland.lua --mantener     # borra el .jaime0-nuevo
```

Nunca se tocan documentos, datos personales ni programas que hayas instalado: solo las rutas que lista el manifiesto, y solo dentro de `/etc/skel`, `/etc/jaime0`, `/etc/default/grub.d`, `/etc/fonts`, `/etc/systemd`, `/usr/local/bin`, `/usr/local/share/marca`, `/usr/local/share/dbus-1/services`, `/usr/lib/systemd/user`, `/usr/share/jaime0`, `/usr/share/backgrounds/jaime0`, `/usr/share/glib-2.0/schemas`, `/usr/share/grub/themes`, `/usr/share/qt6ct` y tu carpeta personal. Aunque un manifiesto firmado pidiera otra ruta, se rechaza.

## Seguridad

- **Firma:** cada `manifiesto.json` va firmado con Ed25519. La clave pública está en `/usr/share/jaime0/firma-actualizaciones.pem` y se comprueba con `openssl`. Sin firma válida no se instala nada.
- **Integridad:** el manifiesto lleva el SHA-256 de la carga y de cada archivo. La carga debe contener exactamente esos archivos; se rechazan enlaces, dispositivos y rutas con `..`.
- **Sin reversiones forzadas:** no se instala una versión igual o anterior a la que tienes, ni una de otro canal. (Un administrador puede forzarlo a propósito con `sudo jaime0-update _sistema VERSIÓN --reinstalar`.)
- **Lo que revisas es lo que se instala:** la fase de sistema recibe la huella del manifiesto que viste en la vista previa y se niega a seguir si la publicación ha cambiado entretanto.
- **Límites:** la firma no puede pasar de 1 KiB, el manifiesto y la lista de GitHub de 8 MiB, y la carga del tamaño que dice el manifiesto firmado. Ninguna descarga puede durar más de 15 minutos.
- **Solo HTTPS**, comprobado en cada redirección y no solo en la dirección final.
- **Diarios de confianza:** un diario de copias solo se usa si es del usuario que lo ejecuta, y solo puede restaurar rutas gestionadas por Jaime0 (o de tu carpeta personal) desde su propia carpeta de copias.
- **Privilegios mínimos:** la consulta, la vista previa y tu configuración se hacen como tu usuario. Solo la fase de sistema usa `sudo`, y ejecuta siempre `/usr/local/bin/jaime0-update`, que vuelve a descargar y verificar por su cuenta: no se fía de lo que preparó el proceso sin privilegios.
- **Un solo proceso a la vez** (cerrojo en `/run/jaime0-update.lock`, solo de root; no sigue enlaces).

## Copias, registro y recuperación

- Antes de cambiar un archivo se copia, y se anota en un diario (`diario.json`) que llega al disco **antes** del cambio. Cada archivo se escribe en un temporal y se renombra: nunca queda uno a medias.
- Copias del sistema: `/var/backups/jaime0/` (solo root). Las tuyas: `~/.local/state/jaime0/copias/`. Se conservan las 5 últimas.
- Registro: `/var/log/jaime0-update.log` y `~/.local/state/jaime0/registro.log` (`jaime0-update historial`).
- **Corte a mitad** (apagón, Ctrl+C, error): la siguiente ejecución deshace lo que quedó a medias antes de seguir. También se puede pedir con `jaime0-update recuperar`. La versión instalada se escribe la última, así que hasta el final el sistema sigue diciendo la versión anterior.
- **`jaime0-update revertir`** devuelve los archivos de Jaime0 a como estaban antes de la última actualización (y guarda antes lo que había, por si quieres deshacer la reversión). Después vuelve a ejecutar lo que dependa de esos archivos (`update-grub`, esquemas de GLib, `systemctl daemon-reload`, versión de `/etc/os-release`).

### Qué NO se puede revertir

`revertir` es real para los **archivos de Jaime0**, pero **no** deshace:

- Los paquetes de Debian que se actualizaron con `apt`. Debian no guarda versiones anteriores; si una actualización de paquetes rompe algo, la vía es `apt` (instalar una versión concreta si sigue en los repositorios) o reinstalar desde la ISO.
- Los paquetes que una versión pida instalar (campo `paquetes` del manifiesto).
- Lo que generan los hooks al compilar la ISO (tema de Plymouth, fuentes descargadas, cursores...). Esos cambios solo llegan con una ISO nueva.

Jaime0 no usa instantáneas del sistema de archivos (Btrfs/Snapper), así que no hay un rollback completo del sistema.

## Si vienes de Jaime0 0.1.x

Las versiones 0.1.x no traen `jaime0-update`. Para instalarlo una vez a mano, verificando la firma (sustituye `V` por la versión publicada):

```bash
V=0.2.0-beta.1
cd "$(mktemp -d)"
for f in manifiesto.json manifiesto.json.sig "jaime0-$V.tar.gz"; do curl -fLO "https://github.com/Jaime-202/jaime0/releases/download/v$V/$f"; done
curl -fsSL -o firma.pem https://raw.githubusercontent.com/Jaime-202/jaime0/main/config/includes.chroot_after_packages/usr/share/jaime0/firma-actualizaciones.pem
openssl pkeyutl -verify -pubin -inkey firma.pem -rawin -in manifiesto.json -sigfile manifiesto.json.sig
python3 -c 'import hashlib,json,sys; m=json.load(open("manifiesto.json")); assert hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest()==m["carga"]["sha256"]; print("Carga verificada")' "jaime0-$V.tar.gz"
tar -xzf "jaime0-$V.tar.gz" usr/local/bin/jaime0-update usr/share/jaime0/firma-actualizaciones.pem etc/jaime0/update.conf
sudo install -m 755 usr/local/bin/jaime0-update /usr/local/bin/jaime0-update
sudo install -D -m 644 usr/share/jaime0/firma-actualizaciones.pem /usr/share/jaime0/firma-actualizaciones.pem
sudo install -D -m 644 etc/jaime0/update.conf /etc/jaime0/update.conf
jaime0-update canal beta
jaime0-update
```

Si la firma no se verifica (`Signature Verification Failure`), para: no sigas. Comprueba también que la clave pública descargada es la buena; su huella SHA-256 (formato DER) es:

```
2143a86fac133152b40587618b3db70a1a7a182f2772908c048ff235d90ed727
```

```bash
openssl pkey -pubin -in firma.pem -outform DER | sha256sum
```

Sin manifiesto previo, los archivos que no has tocado se reconocen por el histórico de huellas de la 0.1.2; si tu ISO no salió exactamente de esa etiqueta, algunos aparecerán como conflicto (se conservan los tuyos).

## Publicar una versión (mantenimiento)

La versión vive en un solo sitio: `config/includes.chroot_after_packages/usr/share/jaime0/version`. De ahí la toman la ISO (`/etc/os-release`), el manifiesto y `jaime0-update`.

1. Cambia la versión y escribe sus notas en `publicaciones/VERSIÓN.toml` (`cambios`, `problemas_conocidos`, `paquetes`, `[requisitos] version_minima`, `[compatibilidad]`).
2. Haz commit y crea la etiqueta: `git tag vVERSIÓN`. El histórico de huellas sale de las etiquetas anteriores.
3. Empaqueta y firma (la clave privada **nunca** dentro del repositorio):

   ```bash
   python3 scripts/empaquetar-actualizacion.py --clave ~/.jaime0/firma-actualizaciones.pem
   ```

   Deja en `dist/VERSIÓN/` el manifiesto, su firma, la carga y `notas.md`, y escribe la orden `gh release create` exacta (con `--prerelease` si no es estable).
4. Compila la ISO de esa misma versión: `auto/build` genera antes el manifiesto que la ISO instala como punto de partida.

ISO y actualizaciones salen de la misma carpeta (`config/includes.chroot_after_packages`), la misma versión y las mismas reglas: la ISO es para instalar desde cero o reinstalar; `jaime0-update` hace evolucionar lo instalado.

### La clave de firma

`openssl genpkey -algorithm ed25519 -out ~/.jaime0/firma-actualizaciones.pem` crea la privada; `openssl pkey -in ... -pubout` saca la pública que va en el repositorio. Guarda una copia de la privada fuera del equipo. Si se pierde, hay que publicar una ISO nueva con otra clave: los sistemas instalados no pueden verificar firmas de una clave que no conocen. Para cambiar de clave sin ISO, publica antes una versión firmada con la clave vieja que traiga la pública nueva. El empaquetador se niega a usar una clave que esté dentro del repositorio o en OneDrive, `.gitignore` excluye nombres típicos de claves privadas y `auto/build` aborta si encuentra una dentro de `config/`.

Límite conocido: no hay caducidad de publicaciones. Quien controle la cuenta de GitHub, aunque no tenga la clave, puede ocultar publicaciones y dejar a los equipos sin enterarse de versiones nuevas (no puede instalarles nada).

## Pruebas

```bash
python3 -m unittest discover -s pruebas -v
```

Montan un sistema de mentira (`JAIME0_RAIZ`) con publicaciones locales firmadas de verdad. Cubren: flujo completo con personalizaciones, conflictos, borrados, archivos nuevos y retirados, resolución de conflictos, reversión, canales, firma falsa, carga alterada, rutas fuera de lo permitido aunque estén firmadas, cortes a mitad con recuperación, no retroceder de versión, versión mínima y enlaces simbólicos. `JAIME0_RAIZ` se ignora siempre que el programa corre como root.

# Biblioteca Chinoppo

Biblioteca de películas y series al estilo de los reproductores R_volution para el **Chinoppo M9201**, un clon del Oppo UDP-203 sin lector de discos. Muestra un muro de carátulas con sus formatos (4K, Dolby Vision, HDR10+, Atmos, DTS:X, 3D), páginas de detalle, temporadas y episodios. Las películas se reproducen desde tu NAS con un solo botón del control.

*An R_volution-style movie library for the Chinoppo M9201 (Oppo UDP-203 clone), built as a BD-J disc plus a small Docker service. Docs are in Spanish.*

> Proyecto de la comunidad, sin relación con Oppo, Dolby ni TMDb. Úsalo bajo tu propio riesgo.

## Cómo funciona

El Chinoppo reproduce discos Blu-ray con **BD-Live**, que son discos con un programa Java dentro y permiso para usar la red. Este proyecto es un disco así (`Biblioteca.iso`) que vive en una memoria USB:

1. **Control** → eliges una película en el muro.
2. **Disco Biblioteca** (BD-J, Java 1.3, 1280×720) → pide las carátulas al servicio y le avisa qué elegiste.
3. **Servicio** (Flask en Docker, puerto 8095) → lee el NAS, consulta TMDb, detecta formatos con ffprobe y 7-Zip, y dibuja las carátulas y las franjas.
4. **Chinoppo** → recibe la orden por su API (puerto 436), monta la carpeta del NAS por NFS y reproduce.

Unos scripts en la USB (AutoScript, una función del firmware liberado) abren la Biblioteca al encender, al despertar del standby y al elegir el ícono **Disco** del menú.

## Lo que necesitas

| | |
|---|---|
| Chinoppo M9201 | Con el firmware liberado **RU 20XRU-65-0131** (por AutoScript) |
| NAS con NFS | Probado con Synology DS423+ (DSM 7.3) |
| Servidor con Docker | Cualquier PC o mini PC Linux siempre encendido |
| PC con Windows + WSL Ubuntu | Para compilar el disco con bdj-sdk |
| Memoria USB FAT32 | Se queda conectada al reproductor |
| Clave de TMDb | Gratis en themoviedb.org |

Todos en la misma red y con IP fija.

## Instalación

### 1. Reproductor
- Firmware RU 65-0131.
- **Configuración → Red → Acceso red BD-Live = Activado**.

### 2. NAS
- Comparte por NFS la carpeta de películas, con lectura para la IP del Chinoppo y la del servidor.
- Usa una carpeta por sección. Por ejemplo `Library/Movies`, `Library/ATMOS`, `Library/3D`, `Library/SERIES` (las series como `Serie/Season 01/…`).

### 3. Servicio
Monta el mismo NFS en el servidor, por ejemplo en `/etc/fstab`:
```
IP-DEL-NAS:/volume1/Plex/Library  /mnt/nas/media  nfs  ro,defaults  0 0
```
Luego:
```bash
cp .env.example .env      # pon tu clave de TMDb, las IPs y MEDIA_PATH
docker compose up -d --build
```
Abre `http://IP-DEL-SERVIDOR:8095`, configura las secciones y espera el primer análisis.

### 4. Disco
- Instala **bdj-sdk** en WSL Ubuntu, en `~/bdj/bdj-sdk`. Se probó con el commit `9c48049`.
- En `disc/src/org/biblio/Net.java` cambia `BASE` por `http://IP-DEL-SERVIDOR:8095`.
- Desde Git Bash:
```bash
bash disc/build.sh        # -> disc/out/Biblioteca.iso
```

### 5. Memoria USB
En la raíz de una USB FAT32 copia:
```
Biblioteca.iso
AutoScript/        <- copia de tools/autoscript/AutoScript
```
- En `AutoScript/vigilante.sh` cambia `CHINOPPO_IP`.
- Compila el binario `consola` y ponlo en `AutoScript/`. Lo necesita el vigilante para saber cuándo eliges el ícono Disco. Con [zig](https://ziglang.org) 0.13, en Linux o WSL:
  ```bash
  zig cc -target arm-linux-musleabihf -mcpu=cortex_a7 -static -O2 -o consola tools/autoscript/consola/consola.c
  ```
- **SSH (opcional, solo con llave):**
  - Compila dropbear con `AutoScript/ssh/build_dropbear.sh`.
  - Pon tu llave pública en `AutoScript/ssh/authorized_keys` (ver el `.example`).
  - Crea un archivo vacío `SSH` en la raíz.
- Para detener el vigilante, crea un archivo `PARAR` en la raíz.

Conecta la USB y enciende. A los ~40 s se abre la Biblioteca.

### Controles
| Tecla | Acción |
|---|---|
| Flechas | Moverse |
| OK | Detalle / reproducir |
| Colores | Secciones (rojo = atrás) |
| POP-UP | Atrás / menú |

RETURN, TOP MENU e INFO no le llegan al disco. Detalle en [disc/KEYS.md](disc/KEYS.md).

## Extras

- **Dolby Vision en MKV:** usa [fandangos/oppo-dv-mkv](https://github.com/fandangos/oppo-dv-mkv). Se probó en el firmware RU 65-0131. Recomendamos el zip `mkv-subtitles` de la versión más reciente (la v1.7.1 al escribir esto), que también mejora los subtítulos. Instálalo con **otra** USB, siguiendo su README. Pon tu TV en modo Dolby Vision *TV-led*.
- **Fondo de "cargando"** para el ícono Disco: `tools/wallpaper/fondo_cargando.py`.
- **Barra del menú oscura:** `tools/tema/`. Necesita SSH y el parche de Dolby Vision instalado. Es lo más delicado: haz respaldo antes.
- **Estuches:** `static/cases` trae plantillas simples, generadas con `tools/cases/make_cases.py`. Puedes cambiarlas por fotos de estuches reales: un PNG con la ventana de la portada transparente.

## Limitaciones conocidas

- **Primera película de cada carpeta:** el reproductor tarda unos 40 s en montar la carpeta del NAS. Solo puede tener una montada a la vez, y no se puede montar por adelantado mientras el disco está abierto.
- **Standby:** el standby es un apagado real. El vigilante reabre la Biblioteca cuando el reproductor vuelve a encender.
- **Un "play" a la vez:** dos órdenes de reproducción simultáneas traban la API del reproductor.

## Desarrollo

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt pytest
python -m pytest tests -q
```

## Aviso

Este producto usa la API de TMDb, pero TMDb no lo respalda ni lo certifica.

La guía completa, con los equipos de prueba, está en [docs/guia.html](docs/guia.html).

# Biblioteca Chinoppo

**[Español](#español) · [English](#english)**

> Proyecto de la comunidad, sin relación con Oppo, Dolby ni TMDb. Úsalo bajo tu propio riesgo.
> *Community project, not affiliated with Oppo, Dolby or TMDb. Use at your own risk.*

---

## Español

Biblioteca de películas y series al estilo de los reproductores R_volution para el **Chinoppo M9201**, un clon del Oppo UDP-203 sin lector de discos. Al encenderlo aparece un muro de carátulas con sus formatos (4K, Dolby Vision, HDR10+, Atmos, DTS:X, 3D), páginas de detalle, temporadas y episodios. Eliges con el control y la película se reproduce desde tu NAS.

### 👉 Guía paso a paso

**[Abre la guía para principiantes](docs/guia.html)** (en GitHub se ve como código: descarga el archivo y ábrelo en el navegador).

Solo necesitas tu Chinoppo con el firmware liberado RU 65-0131, un NAS con NFS y una app para Docker (Container Manager, Container Station, Portainer…), una memoria USB y una cuenta gratis de TMDb. No hay que programar ni usar la terminal.

### En resumen

1. **Chinoppo:** Configuración → Red → **Acceso red BD-Live = Activado**. Anota su IP.
2. **TMDb:** saca tu clave de la API (gratis).
3. **NAS:** NFS activado y con permiso para la IP del Chinoppo. Anota la ruta de tu carpeta compartida.
4. **Docker en el NAS:** sube este proyecto (Code → Download ZIP) al NAS y crea con él un proyecto/stack de docker-compose. En el `compose.yaml` cambia solo las líneas marcadas con `<--`.
5. Abre **`http://IP-DEL-NAS:8095`** y elige tus carpetas de películas y series.
6. En esa misma página, **Descargar archivos para la USB**. Descomprime el ZIP en la raíz de una USB FAT32.
7. Conecta la USB al Chinoppo y enciéndelo: entre 20 y 40 s después aparece la Biblioteca.

### Cómo funciona

El Chinoppo reproduce discos Blu-ray con **BD-Live**: discos con un programa Java dentro y permiso para usar la red.

1. **Disco Biblioteca** (`static/usb/Biblioteca.iso`, BD-J, Java 1.3): muestra el muro y le pide todo al servicio. Lee la dirección del servicio de `BIBLIO.TXT`, un archivo dentro de la ISO que el servicio rellena al generar el ZIP para la USB.
2. **Servicio** (Flask en Docker, puerto 8095): lee el NAS, consulta TMDb, detecta formatos con ffprobe y 7-Zip, y dibuja carátulas y franjas.
3. **Chinoppo:** recibe la orden por su API (puerto 436), monta la carpeta del NAS por NFS y reproduce.
4. **AutoScript** (función del firmware liberado) en la USB: abre la Biblioteca al encender, al despertar y al elegir el ícono **Disco**.

### Controles

| Tecla | Acción |
|---|---|
| Flechas | Moverse |
| OK | Detalle / reproducir |
| Colores | Secciones (rojo = atrás) |
| POP-UP | Atrás / menú |

RETURN, TOP MENU e INFO no le llegan al disco. Detalle en [disc/KEYS.md](disc/KEYS.md).

### Extras

- **Dolby Vision en MKV:** [fandangos/oppo-dv-mkv](https://github.com/fandangos/oppo-dv-mkv), zip `mkv-subtitles` de la versión más reciente (probado v1.7.1 en RU 65-0131). Se instala con **otra** USB. TV en modo Dolby Vision *TV-led*.
- **PC o servidor Linux en vez del NAS**, **compilar el disco**, **SSH** y **barra oscura del menú:** en la sección *Avanzado* de la guía.
- **Estuches:** `static/cases` trae plantillas simples (`tools/cases/make_cases.py`). Puedes cambiarlas por fotos reales: un PNG con la ventana de la portada transparente.

### Limitaciones conocidas

- La primera película de cada carpeta tarda unos 40 s: el reproductor monta la carpeta del NAS y solo puede tener una montada a la vez.
- El standby es un apagado real; la Biblioteca se vuelve a abrir sola al encender.
- Dos órdenes de reproducción simultáneas traban la API del reproductor; el servicio descarta las repetidas. Ten **un solo** servicio corriendo por Chinoppo.

---

## English

An R_volution-style movie and TV library for the **Chinoppo M9201**, a disc-less Oppo UDP-203 clone. When you switch it on, a wall of posters appears with each title's formats (4K, Dolby Vision, HDR10+, Atmos, DTS:X, 3D), detail pages, seasons and episodes. Pick one with the remote and it plays from your NAS.

### 👉 Step-by-step guide

**[Open the beginner's guide](docs/guide-en.html)** (GitHub shows it as code: download the file and open it in your browser).

All you need is your Chinoppo with the jailbroken RU 65-0131 firmware, a NAS with NFS and a Docker app (Container Manager, Container Station, Portainer…), a USB stick and a free TMDb account. No programming, no command line. The Biblioteca's own screens and web page are in Spanish; the guide translates every button.

### In short

1. **Chinoppo:** Setup → Network → **BD-Live Network Access = On**. Note its IP.
2. **TMDb:** get your API key (free).
3. **NAS:** NFS on, with access for the Chinoppo's IP. Note your shared folder's path.
4. **Docker on the NAS:** upload this project (Code → Download ZIP) to the NAS and create a docker-compose project/stack from it. In `compose.yaml` change only the lines marked `<--`.
5. Open **`http://NAS-IP:8095`** and choose your movie and TV folders.
6. On that page, click **Descargar archivos para la USB** (download files for the USB). Unzip it to the root of a FAT32 USB stick.
7. Plug the stick into the Chinoppo and switch it on: the Biblioteca appears 20 to 40 s later.

### How it works

1. **Biblioteca disc** (`static/usb/Biblioteca.iso`, BD-J, Java 1.3): draws the wall and asks the service for everything. It reads the service address from `BIBLIO.TXT`, a file inside the ISO that the service fills in when it builds the USB ZIP.
2. **Service** (Flask in Docker, port 8095): reads the NAS, queries TMDb, detects formats with ffprobe and 7-Zip, and renders posters and badges.
3. **Chinoppo:** receives the play order through its API (port 436), mounts the NAS folder over NFS and plays.
4. **AutoScript** (a jailbroken-firmware feature) on the stick: opens the Biblioteca at power-on, after standby and when you pick the **Disc** icon.

### Known limitations

- The first movie of each folder takes about 40 s: the player mounts the NAS folder and can only keep one mounted.
- Standby is a real power-off; the Biblioteca reopens by itself at power-on.
- Two simultaneous play orders lock up the player's API; the service drops repeats. Run **only one** service per Chinoppo.

---

## Desarrollo · Development

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt pytest
python -m pytest tests -q
bash disc/build.sh      # bdj-sdk in WSL; copy disc/out/Biblioteca.iso to static/usb/
```

`consola` (in `tools/autoscript/AutoScript/`) is built with `zig cc -target arm-linux-musleabihf -mcpu=cortex_a7 -static -O2 -o consola tools/autoscript/consola/consola.c`.

Este producto usa la API de TMDb, pero TMDb no lo respalda ni lo certifica. · *This product uses the TMDb API but is not endorsed or certified by TMDb.*

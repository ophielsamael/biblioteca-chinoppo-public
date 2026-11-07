# Biblioteca Chinoppo

Biblioteca de películas y series al estilo de los reproductores R_volution para el **Chinoppo M9201**, un clon del Oppo UDP-203 sin lector de discos. Al encenderlo aparece un muro de carátulas con sus formatos (4K, Dolby Vision, HDR10+, Atmos, DTS:X, 3D), páginas de detalle, temporadas y episodios. Eliges con el control y la película se reproduce desde tu NAS.

*An R_volution-style movie library for the Chinoppo M9201 (Oppo UDP-203 clone), built as a BD-J disc plus a small Docker service. Docs are in Spanish.*

> Proyecto de la comunidad, sin relación con Oppo, Dolby ni TMDb. Úsalo bajo tu propio riesgo.

## 👉 Guía paso a paso

**[Abre la guía para principiantes](docs/guia.html)** (en GitHub se ve como código: descarga el archivo y ábrelo en el navegador).

Solo necesitas tu Chinoppo con el firmware liberado RU 65-0131, un NAS con NFS y una app para Docker (Container Manager, Container Station, Portainer…), una memoria USB y una cuenta gratis de TMDb. No hay que programar ni usar la terminal.

## En resumen

1. **Chinoppo:** Configuración → Red → **Acceso red BD-Live = Activado**. Anota su IP.
2. **TMDb:** saca tu clave de la API (gratis).
3. **NAS:** NFS activado y con permiso para la IP del Chinoppo. Anota la ruta de tu carpeta de películas.
4. **Docker en el NAS:** sube este proyecto (Code → Download ZIP) al NAS y crea con él un proyecto/stack de docker-compose. En el `compose.yaml` cambia solo las líneas marcadas con `<--`.
5. Abre **`http://IP-DEL-NAS:8095`** y elige tus carpetas de películas y series.
6. En esa misma página, **Descargar archivos para la USB**. Descomprime el ZIP en la raíz de una USB FAT32.
7. Conecta la USB al Chinoppo y enciéndelo: a los ~40 s aparece la Biblioteca.

## Cómo funciona

El Chinoppo reproduce discos Blu-ray con **BD-Live**: discos con un programa Java dentro y permiso para usar la red.

1. **Disco Biblioteca** (`static/usb/Biblioteca.iso`, BD-J, Java 1.3): muestra el muro y le pide todo al servicio. Lee la dirección del servicio de `BIBLIO.TXT`, un archivo dentro de la ISO que el servicio rellena al generar el ZIP para la USB.
2. **Servicio** (Flask en Docker, puerto 8095): lee el NAS, consulta TMDb, detecta formatos con ffprobe y 7-Zip, y dibuja carátulas y franjas.
3. **Chinoppo:** recibe la orden por su API (puerto 436), monta la carpeta del NAS por NFS y reproduce.
4. **AutoScript** (función del firmware liberado) en la USB: abre la Biblioteca al encender, al despertar y al elegir el ícono **Disco**.

## Controles

| Tecla | Acción |
|---|---|
| Flechas | Moverse |
| OK | Detalle / reproducir |
| Colores | Secciones (rojo = atrás) |
| POP-UP | Atrás / menú |

RETURN, TOP MENU e INFO no le llegan al disco. Detalle en [disc/KEYS.md](disc/KEYS.md).

## Extras

- **Dolby Vision en MKV:** [fandangos/oppo-dv-mkv](https://github.com/fandangos/oppo-dv-mkv), zip `mkv-subtitles` de la versión más reciente (probado v1.7.1 en RU 65-0131). Se instala con **otra** USB. TV en modo Dolby Vision *TV-led*.
- **Servidor Linux en vez del Synology**, **compilar el disco**, **SSH** y **barra oscura del menú:** en la sección *Avanzado* de la guía.
- **Estuches:** `static/cases` trae plantillas simples (`tools/cases/make_cases.py`). Puedes cambiarlas por fotos reales: un PNG con la ventana de la portada transparente.

## Limitaciones conocidas

- La primera película de cada carpeta tarda unos 40 s: el reproductor monta la carpeta del NAS y solo puede tener una montada a la vez.
- El standby es un apagado real; la Biblioteca se vuelve a abrir sola al encender.
- Dos órdenes de reproducción simultáneas traban la API del reproductor; el servicio descarta las repetidas.

## Desarrollo

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt pytest
python -m pytest tests -q
bash disc/build.sh      # recompila el disco (bdj-sdk en WSL); copia disc/out/Biblioteca.iso a static/usb/
```

`consola` (en `tools/autoscript/AutoScript/`) se compila con `zig cc -target arm-linux-musleabihf -mcpu=cortex_a7 -static -O2 -o consola tools/autoscript/consola/consola.c`.

## Aviso

Este producto usa la API de TMDb, pero TMDb no lo respalda ni lo certifica.

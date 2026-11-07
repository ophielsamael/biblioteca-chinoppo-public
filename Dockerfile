FROM python:3.12-slim-trixie

ENV PYTHONUNBUFFERED=1 DATA_DIR=/app/data MEDIA_ROOT=/media/Plex
WORKDIR /app
COPY requirements.txt .
# ffprobe + 7-Zip: format detection (biblio/formats.py) reads ISOs without mounting them.
# trixie: ffmpeg 7 names Atmos / DTS:X in the audio profile (bookworm's 5.1 does not)
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg xz-utils \
    && rm -rf /var/lib/apt/lists/*
# 7-Zip from 7-zip.org (26.00, the PC's version): Debian's 7zip listed no files in some UDF 2.50
# ISOs that this one reads (seen 2026-11-04: Super 8, Predator Badlands, the 3D discs)
RUN set -e; case "$(dpkg --print-architecture)" in \
      amd64) a=x64; sum=c74dc4a48492cde43f5fec10d53fb2a66f520e4a62a69d630c44cb22c477edc6 ;; \
      arm64) a=arm64; sum=aa8f3d0a19af9674d3af0ec788b4e261501071e626cd75ad149f1c2c176cc87d ;; \
      *) echo "no 7-Zip build for this CPU"; exit 1 ;; esac; \
    python -c "import urllib.request; urllib.request.urlretrieve('https://www.7-zip.org/a/7z2600-linux-$a.tar.xz', '/tmp/7z.tar.xz')"; \
    echo "$sum  /tmp/7z.tar.xz" | sha256sum -c -; \
    tar -xJf /tmp/7z.tar.xz -C /usr/local/bin 7zz; rm /tmp/7z.tar.xz; 7zz | head -2
RUN pip install --no-cache-dir -r requirements.txt \
    && groupadd -r biblio && useradd -r -g biblio -d /app biblio \
    && mkdir -p /app/data && chown biblio:biblio /app/data
COPY --chown=biblio:biblio app.py ./
COPY --chown=biblio:biblio biblio ./biblio
COPY --chown=biblio:biblio templates ./templates
COPY --chown=biblio:biblio static ./static
# the files of the USB ZIP (biblio/usbpack.py)
COPY --chown=biblio:biblio tools/autoscript/AutoScript ./tools/autoscript/AutoScript
USER biblio
CMD ["python", "app.py"]

import sharp from 'sharp';

// TMDb backdrop as a 1920x1080 wallpaper, e.g. for the Chinoppo home menu (its UI is drawn
// at 1080p; files go to /mnt/ubi_boot/<icon> as plain RGB PNG). With fade=1 the lower part
// darkens so the player's icon bar on top of it stays readable.
const W = 1920;
const H = 1080;
const TMDB_PATH = /^\/[A-Za-z0-9_-]+\.(jpg|jpeg|png)$/;   // only TMDb file paths: no open proxy

export async function GET(req: Request) {
  const params = new URL(req.url).searchParams;
  const path = params.get('path') ?? '';
  const format = params.get('format') === 'png' ? 'png' : 'jpg';
  const fade = params.get('fade') !== '0';
  const name = (params.get('name') || 'fondo').replace(/[\\/:*?"<>|]/g, '').trim() || 'fondo';

  if (!TMDB_PATH.test(path)) {
    return new Response('Invalid backdrop path', { status: 400 });
  }

  const tmdb = await fetch(`https://image.tmdb.org/t/p/original${path}`, { headers: { Accept: 'image/*' } });
  if (!tmdb.ok) {
    return new Response('Failed to download backdrop from TMDb', { status: 502 });
  }

  let image = sharp(Buffer.from(await tmdb.arrayBuffer())).resize(W, H, { fit: 'cover' });
  if (fade) {
    // clear in the top half, black at the bottom edge
    const gradient = Buffer.from(
      `<svg width="${W}" height="${H}"><defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1">` +
      `<stop offset="0.45" stop-color="#000" stop-opacity="0"/>` +
      `<stop offset="1" stop-color="#000" stop-opacity="0.9"/>` +
      `</linearGradient></defs><rect width="100%" height="100%" fill="url(#g)"/></svg>`
    );
    image = image.composite([{ input: gradient }]);
  }
  image = image.removeAlpha();   // the player wants plain RGB
  const body = format === 'png' ? await image.png().toBuffer() : await image.jpeg({ quality: 92 }).toBuffer();

  return new Response(new Uint8Array(body), {
    headers: {
      'Content-Type': format === 'png' ? 'image/png' : 'image/jpeg',
      'Content-Disposition': `attachment; filename*=UTF-8''${encodeURIComponent(`${name} 1080p.${format}`)}`,
    },
  });
}

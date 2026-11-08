import sharp from 'sharp';

// TMDb title logo as a transparent PNG file (SVG logos are rasterized).
const TMDB_PATH = /^\/[A-Za-z0-9_-]+\.(png|svg)$/;   // only TMDb file paths: no open proxy

export async function GET(req: Request) {
  const params = new URL(req.url).searchParams;
  const path = params.get('path') ?? '';
  const name = (params.get('name') || 'logo').replace(/[\\/:*?"<>|]/g, '').trim() || 'logo';

  if (!TMDB_PATH.test(path)) {
    return new Response('Invalid logo path', { status: 400 });
  }
  const tmdb = await fetch(`https://image.tmdb.org/t/p/original${path}`, { headers: { Accept: 'image/*' } });
  if (!tmdb.ok) {
    return new Response('Failed to download logo from TMDb', { status: 502 });
  }
  const png = await sharp(Buffer.from(await tmdb.arrayBuffer())).png().toBuffer();
  return new Response(new Uint8Array(png), {
    headers: {
      'Content-Type': 'image/png',
      'Content-Disposition': `attachment; filename*=UTF-8''${encodeURIComponent(`${name} logo.png`)}`,
    },
  });
}

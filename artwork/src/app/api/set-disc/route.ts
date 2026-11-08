import { NextResponse } from 'next/server';
import sharp from 'sharp';
import { pushToBiblioteca } from '../../../actions/biblioteca';

// Disc art from fanart.tv for the Biblioteca (it slides out of the case on the detail page).
// PNG, so the round transparency stays.
export async function POST(req: Request) {
  try {
    const { discUrl, tmdbId, itemId, media } = await req.json();
    let host = '', https = false;
    try { const u = new URL(discUrl); host = u.hostname; https = u.protocol === 'https:'; } catch {}
    // exactly fanart.tv or a subdomain of it ("evilfanart.tv" must not pass)
    if (!(tmdbId || itemId) || !https || !(host === 'fanart.tv' || host.endsWith('.fanart.tv'))) {   // only fanart.tv images: no open proxy
      return NextResponse.json({ error: 'Invalid disc url' }, { status: 400 });
    }
    const resp = await fetch(discUrl, { headers: { Accept: 'image/*' } });
    if (!resp.ok) throw new Error('Failed to download disc from fanart.tv');
    const png = await sharp(Buffer.from(await resp.arrayBuffer())).png().toBuffer();
    const biblioteca = await pushToBiblioteca('disc', { tmdbId, itemId, media }, png, 'image/png');
    return NextResponse.json({ success: biblioteca, biblioteca }, { status: biblioteca ? 200 : 502 });
  } catch (error: any) {
    console.error('API /set-disc error:', error);
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}

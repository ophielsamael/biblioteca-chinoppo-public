import { NextResponse } from 'next/server';
import sharp from 'sharp';
import { pushToBiblioteca } from '../../../actions/biblioteca';

// A TMDb title logo for the Biblioteca's detail page. PNG, so the transparency stays.
export async function POST(req: Request) {
  try {
    const { tmdbLogoUrl, tmdbId, itemId, media } = await req.json();
    if (!(tmdbId || itemId) || !tmdbLogoUrl || !String(tmdbLogoUrl).startsWith('https://image.tmdb.org/')) {
      return NextResponse.json({ error: 'Missing required fields' }, { status: 400 });
    }
    const resp = await fetch(tmdbLogoUrl, { headers: { Accept: 'image/*' } });
    if (!resp.ok) throw new Error('Failed to download logo from TMDb');
    const png = await sharp(Buffer.from(await resp.arrayBuffer())).png().toBuffer();   // SVG logos too
    const biblioteca = await pushToBiblioteca('logo', { tmdbId, itemId, media }, png, 'image/png');
    return NextResponse.json({ success: biblioteca, biblioteca }, { status: biblioteca ? 200 : 502 });
  } catch (error: any) {
    console.error('API /set-logo error:', error);
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}

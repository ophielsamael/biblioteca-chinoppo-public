import { NextResponse } from 'next/server';
import sharp from 'sharp';
import { pushToBiblioteca } from '../../../actions/biblioteca';

// A TMDb backdrop for the title's detail page in the Biblioteca.
export async function POST(req: Request) {
  try {
    const { tmdbBackdropUrl, tmdbId, itemId, media } = await req.json();
    if (!(tmdbId || itemId) || !tmdbBackdropUrl || !String(tmdbBackdropUrl).startsWith('https://image.tmdb.org/')) {
      return NextResponse.json({ error: 'Missing required fields' }, { status: 400 });
    }
    const resp = await fetch(tmdbBackdropUrl, { headers: { Accept: 'image/*' } });
    if (!resp.ok) throw new Error('Failed to download backdrop from TMDb');
    const jpeg = await sharp(Buffer.from(await resp.arrayBuffer())).jpeg({ quality: 90 }).toBuffer();
    const biblioteca = await pushToBiblioteca('backdrop', { tmdbId, itemId, media }, jpeg, 'image/jpeg');
    return NextResponse.json({ success: biblioteca, biblioteca }, { status: biblioteca ? 200 : 502 });
  } catch (error: any) {
    console.error('API /set-backdrop error:', error);
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}

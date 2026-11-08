import { NextResponse } from 'next/server';
import sharp from 'sharp';
import { pushToBiblioteca } from '../../../actions/biblioteca';

// A series' season poster for the Biblioteca: a TMDb image or one uploaded from the PC (data: URL).
export async function POST(req: Request) {
  try {
    const { posterUrl, tmdbId, itemId, season } = await req.json();
    const n = Number(season);
    if (!(tmdbId || itemId) || !Number.isInteger(n) || n < 0 || n > 999
        || !/^(https:\/\/image\.tmdb\.org\/|data:image\/)/.test(String(posterUrl || ''))) {
      return NextResponse.json({ error: 'Missing or invalid fields' }, { status: 400 });
    }
    const resp = await fetch(posterUrl, { headers: { Accept: 'image/*' } });
    if (!resp.ok) throw new Error('Failed to download the season poster');
    const jpeg = await sharp(Buffer.from(await resp.arrayBuffer()))
      .resize(1000, 1500, { fit: 'cover' }).jpeg({ quality: 90 }).toBuffer();
    const biblioteca = await pushToBiblioteca(`season${n}`, { tmdbId, itemId, media: 'tv' }, jpeg, 'image/jpeg');
    return NextResponse.json({ success: biblioteca, biblioteca }, { status: biblioteca ? 200 : 502 });
  } catch (error: any) {
    console.error('API /set-season error:', error);
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}

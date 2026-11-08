import { NextResponse } from 'next/server';
import { BIBLIOTECA_URL } from '../../../actions/biblioteca';

// A sample format row in one badge style, from the Biblioteca (the browser can't reach 127.0.0.1).
export async function GET(request: Request) {
  const id = new URL(request.url).searchParams.get('id') || '';
  if (!/^[a-z0-9-]{1,40}$/.test(id)) return new NextResponse('bad id', { status: 400 });
  try {
    const r = await fetch(`${BIBLIOTECA_URL}/api/badge-styles/${id}.png`, { signal: AbortSignal.timeout(60000) });
    if (!r.ok) return new NextResponse('unavailable', { status: r.status });
    return new NextResponse(await r.arrayBuffer(), {
      headers: { 'Content-Type': 'image/png', 'Cache-Control': 'max-age=3600' },
    });
  } catch {
    return new NextResponse('unavailable', { status: 502 });
  }
}

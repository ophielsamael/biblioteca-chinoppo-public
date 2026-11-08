import { NextResponse } from 'next/server';
import { BIBLIOTECA_URL } from '../../../actions/biblioteca';

export const dynamic = 'force-dynamic';   // a poster can change at any time

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const itemId = searchParams.get('itemId');

    if (!itemId) {
      return new NextResponse('Missing itemId', { status: 400 });
    }

    // the title's current poster in the Biblioteca (the one applied here, else TMDb's)
    const season = searchParams.get('season');
    const src = season
      ? `${BIBLIOTECA_URL}/d/img/season?id=${encodeURIComponent(itemId)}&season=${encodeURIComponent(season)}&w=400&h=600`
      : `${BIBLIOTECA_URL}/api/poster?id=${encodeURIComponent(itemId)}`;
    const response = await fetch(src, {
      cache: 'no-store',
      method: 'GET',
      headers: {
        'Accept': 'image/*'
      }
    });

    if (!response.ok) {
      return new NextResponse('Image not found or access denied', { status: response.status });
    }

    const imageBuffer = await response.arrayBuffer();

    // Pass the image directly back to the client
    return new NextResponse(imageBuffer, {
      headers: {
        'Content-Type': response.headers.get('content-type') || 'image/jpeg',
        'Cache-Control': 'no-cache'
      }
    });
  } catch (error) {
    console.error('Proxy Image Error:', error);
    return new NextResponse('Internal Server Error', { status: 500 });
  }
}

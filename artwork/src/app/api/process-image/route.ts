import { NextResponse } from 'next/server';
import sharp from 'sharp';
import path from 'path';
import fs from 'fs';
import { overlayKey, saveAppliedOverlay } from '../../../actions/db';
import { BIBLIOTECA_URL, caseFromBiblioteca, dropFromBiblioteca, pushToBiblioteca } from '../../../actions/biblioteca';

export async function POST(req: Request) {
  try {
    const { tmdbPosterUrl, overlayType, itemId, tmdbId, media, caseType, title } = await req.json();
    const target = { tmdbId, itemId, media };

    if (!tmdbPosterUrl) {
      return NextResponse.json({ error: 'tmdbPosterUrl is required' }, { status: 400 });
    }

    if (!itemId) {
      return NextResponse.json({ error: 'itemId is required' }, { status: 400 });
    }
    // tmdbPosterUrl: a TMDb image, our own proxy of the current poster (relative), or an image
    // uploaded from the PC (data: URL)
    if (!/^(https:\/\/image\.tmdb\.org\/|\/|data:image\/)/.test(tmdbPosterUrl)) {
      return NextResponse.json({ error: 'Unsupported poster source' }, { status: 400 });
    }

    // 1. Download Base Poster
    let baseImageBuffer: Buffer;
    let fetchUrl = tmdbPosterUrl;
    
    // a relative URL is our own proxy of the current poster: read it from the Biblioteca
    if (tmdbPosterUrl.startsWith('/')) {
      fetchUrl = `${BIBLIOTECA_URL}/api/poster?id=${encodeURIComponent(itemId)}`;
    }

    const resp = await fetch(fetchUrl, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
      }
    });
    if (!resp.ok) throw new Error(`Failed to fetch remote poster: ${resp.status}`);
    const arrayBuffer = await resp.arrayBuffer();
    baseImageBuffer = Buffer.from(arrayBuffer);

    // 2. Resize base poster to exactly 1000x1500 px
    let sharpInstance = sharp(baseImageBuffer).resize(1000, 1500, {
      fit: 'cover',
    });
    // the clean cover (no banner): what goes inside the Blu-ray / 4K case
    const cleanCover = await sharpInstance.clone().jpeg({ quality: 90 }).toBuffer();

    // 3. Composite Overlay if provided and not "Sin Overlay"
    if (overlayType && overlayType !== "Sin Overlay") {
      const cleanName = overlayType
        .toLowerCase()
        .replace(/ with /g, "-")
        .replace(/ and /g, "-")
        .replace(/\s+/g, "-");
      
      const overlayPath = path.join(process.cwd(), 'public', 'overlays', `${cleanName}.png`);
      
      if (fs.existsSync(overlayPath)) {
        // Forzamos el ancho a exactamente 1000px, dejando que el alto fluya proporcionalmente.
        // Esto asegura que si es un banner o una capa 1000x1500, se expanda al borde perfecto.
        const overlayBuffer = await sharp(overlayPath).resize({ width: 1000 }).toBuffer();
        
        sharpInstance = sharpInstance.composite([
          { input: overlayBuffer, top: 0, left: 0 }
        ]);
      } else {
        console.warn(`Overlay file not found: ${overlayPath}`);
      }
    }

    // Generate Final Output in JPEG format
    const finalBuffer = await sharpInstance.jpeg({ quality: 90 }).toBuffer();
    const mime = 'image/jpeg';
    // Biblioteca: the poster (with its banner) is for the wall; the case, if chosen, is a
    // separate image for the detail page only: 4K -> black UHD case, HD -> blue Blu-ray case
    let biblioteca = await pushToBiblioteca('poster', target, finalBuffer, mime);
    if (caseType === 'bluray' || caseType === 'uhd') {
      const boxed = await caseFromBiblioteca(cleanCover, caseType, title || '');
      biblioteca = biblioteca && !!boxed && await pushToBiblioteca('case', target, boxed, 'image/png');
    } else if (caseType === 'none') {
      biblioteca = biblioteca && await dropFromBiblioteca('case', target);
    }

    if (!biblioteca) {
      return NextResponse.json({ error: 'The Biblioteca did not take the poster' }, { status: 502 });
    }
    saveAppliedOverlay(overlayKey(itemId), overlayType);
    return NextResponse.json({ success: true, biblioteca });

  } catch (error: any) {
    console.error("Image processing error:", error);
    try {
      fs.writeFileSync(path.join(process.env.DATA_DIR || process.cwd(), 'error.log'), error.stack || error.toString());
    } catch(e) {}
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}

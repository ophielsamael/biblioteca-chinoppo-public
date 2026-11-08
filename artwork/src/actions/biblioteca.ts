// The Chinoppo Biblioteca is where everything made here goes (its catalog keys titles by
// TMDb id). Never throws: returns whether it took it.
export const BIBLIOTECA_URL = process.env.BIBLIOTECA_URL || 'http://127.0.0.1:8095';

// The cover inside a Blu-ray / 4K UHD case photo, as a transparent PNG. The perspective warp
// is done by the Biblioteca (Pillow); null when it can't be reached.
export async function caseFromBiblioteca(cover: Buffer, kind: 'bluray' | 'uhd', title: string): Promise<Buffer | null> {
  try {
    const r = await fetch(`${BIBLIOTECA_URL}/tools/case?kind=${kind}&title=${encodeURIComponent(title)}`, {
      method: 'POST',
      headers: { 'Content-Type': 'image/jpeg' },
      body: new Uint8Array(cover),
      signal: AbortSignal.timeout(30000),
    });
    return r.ok ? Buffer.from(await r.arrayBuffer()) : null;
  } catch (e) {
    console.warn('Biblioteca unreachable for the case:', e);
    return null;
  }
}

type ArtKind = 'poster' | 'backdrop' | 'logo' | 'case' | 'disc'   // case, disc: detail page only
  | `season${number}`;                                             // a series' season poster

// Which title the image is for: by TMDb id (every copy of the title), else by the Biblioteca's
// item id (videos TMDb doesn't know). media: 'movie' or 'tv' (their TMDb ids overlap).
export interface ArtTarget {
  tmdbId?: string | number | null;
  itemId?: string | number | null;
  media?: string | null;
}

function artQuery(t: ArtTarget): string | null {
  if (t.tmdbId) return `tmdb=${encodeURIComponent(String(t.tmdbId))}&media=${t.media === 'tv' ? 'tv' : 'movie'}`;
  if (t.itemId) return `item=${encodeURIComponent(String(t.itemId))}`;
  return null;
}

export async function dropFromBiblioteca(kind: ArtKind, target: ArtTarget): Promise<boolean> {
  const q = artQuery(target);
  if (!q) return false;
  try {
    const r = await fetch(`${BIBLIOTECA_URL}/art/${kind}?${q}`, { method: 'DELETE', signal: AbortSignal.timeout(10000) });
    return r.ok;
  } catch (e) {
    console.warn('Biblioteca unreachable:', e);
    return false;
  }
}

export async function pushToBiblioteca(kind: ArtKind, target: ArtTarget, image: Buffer, contentType: string): Promise<boolean> {
  const q = artQuery(target);
  if (!q) return false;
  try {
    const r = await fetch(`${BIBLIOTECA_URL}/art/${kind}?${q}`, {
      method: 'POST',
      headers: { 'Content-Type': contentType },
      body: new Uint8Array(image),
      signal: AbortSignal.timeout(10000),
    });
    if (!r.ok) console.warn(`Biblioteca /art/${kind} answered ${r.status}`);
    return r.ok;
  } catch (e) {
    console.warn('Biblioteca unreachable:', e);
    return false;
  }
}

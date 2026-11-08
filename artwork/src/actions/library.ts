'use server'

// The catalog Artwork Studio edits: the Chinoppo Biblioteca's own (its folders and titles),
// nothing else. Ids are the Biblioteca's item ids.
import { BIBLIOTECA_URL } from './biblioteca';
import { getAppliedOverlays, overlayKey } from './db';

export async function fetchLibraries() {
  try {
    const r = await fetch(`${BIBLIOTECA_URL}/api/folders`, { cache: 'no-store' });
    if (!r.ok) throw new Error(`Biblioteca /api/folders answered ${r.status}`);
    const folders = await r.json();
    return folders.map((f: any) => ({ id: f.id, name: f.name, collectionType: f.kind }));
  } catch (error) {
    console.error('Error fetching the Biblioteca folders:', error);
    return [];
  }
}

export async function fetchLibraryItems(folderId: string) {
  try {
    const r = await fetch(`${BIBLIOTECA_URL}/api/items?folder=${encodeURIComponent(folderId)}`, { cache: 'no-store' });
    if (!r.ok) throw new Error(`Biblioteca /api/items answered ${r.status}`);
    const items = await r.json();
    const overlays = getAppliedOverlays();
    return items.map((it: any) => ({
      id: it.id,
      title: it.title || 'Unknown Title',
      year: it.year || 0,
      genre: it.genres?.length ? it.genres.join(' / ') : 'Desconocido',
      rating: it.rating || 0,
      tmdbId: it.tmdb_id ? String(it.tmdb_id) : null,
      path: it.path,
      media: it.media,
      seasons: it.seasons || [],
      badges: it.badges || [],
      format: it.format || null,
      // ?v= so a poster just applied is not served from the browser cache
      currentPoster: `/api/image-proxy?itemId=${it.id}&v=${Date.now()}`,
      posters: [`/api/image-proxy?itemId=${it.id}`],
      selectedOverlay: overlays[overlayKey(it.id)] || null,
      backdrop: 'rgba(82, 181, 75, 0.15)',
    }));
  } catch (error) {
    console.error('Error fetching the Biblioteca titles:', error);
    return [];
  }
}

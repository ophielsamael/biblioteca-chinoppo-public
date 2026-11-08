'use server'

// "Metadatos" tab: fix which TMDb title a Biblioteca file is matched to (kept locked there).
import { getDynamicConfig } from './config';
import { BIBLIOTECA_URL } from './biblioteca';

export type Media = 'movie' | 'tv';

export interface TmdbHit {
  id: number;
  title: string;
  originalTitle: string;
  year: string;
  poster: string | null;
  votes: number;
  overview: string;
}

export interface BibliotecaMatch {
  id: number;
  title: string;
  year: number | null;
  tmdb_id: number | null;
  media: Media;
  locked: boolean;
}

export async function searchTmdb(query: string, year: string, media: Media): Promise<TmdbHit[]> {
  const { tmdbApiKey } = await getDynamicConfig();
  if (!query.trim() || !tmdbApiKey) return [];
  const p = new URLSearchParams({ api_key: tmdbApiKey, language: 'es-ES', query: query.trim() });
  if (/^\d{4}$/.test(year)) p.set(media === 'tv' ? 'first_air_date_year' : 'year', year);
  try {
    const r = await fetch(`https://api.themoviedb.org/3/search/${media}?${p}`, { cache: 'no-store' });
    if (!r.ok) return [];
    const data = await r.json();
    return (data.results || []).slice(0, 12).map((x: any) => ({
      id: x.id,
      title: x.title || x.name || '',
      originalTitle: x.original_title || x.original_name || '',
      year: (x.release_date || x.first_air_date || '').slice(0, 4),
      poster: x.poster_path || null,
      votes: x.vote_count || 0,
      overview: x.overview || '',
    }));
  } catch (e) {
    console.error('TMDb search failed:', e);
    return [];
  }
}

export async function getBibliotecaMatch(path: string | null | undefined): Promise<BibliotecaMatch | null> {
  if (!path) return null;
  try {
    const r = await fetch(`${BIBLIOTECA_URL}/match?path=${encodeURIComponent(path)}`,
                          { cache: 'no-store', signal: AbortSignal.timeout(10000) });
    return r.ok ? await r.json() : null;
  } catch {
    return null;   // Biblioteca down, or the file isn't in one of its folders
  }
}

export async function applyMatch(path: string | null | undefined, tmdbId: number): Promise<BibliotecaMatch | null> {
  if (!path) return null;
  try {
    const r = await fetch(`${BIBLIOTECA_URL}/match?path=${encodeURIComponent(path)}&tmdb=${tmdbId}`,
                          { method: 'POST', signal: AbortSignal.timeout(30000) });
    return r.ok ? await r.json() : null;
  } catch (e) {
    console.warn('Biblioteca unreachable:', e);
    return null;
  }
}

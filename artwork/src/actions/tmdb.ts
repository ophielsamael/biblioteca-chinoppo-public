'use server'

import { getDynamicConfig } from './config';

export async function fetchTmdbPosters(tmdbId: string | number, media: string = 'movie') {
  const { tmdbApiKey } = await getDynamicConfig();

  if (!tmdbId || !tmdbApiKey) {
    return [];
  }

  try {
    const url = `https://api.themoviedb.org/3/${media === 'tv' ? 'tv' : 'movie'}/${tmdbId}/images?api_key=${tmdbApiKey}&include_image_language=en,es,it,null`;
    
    const response = await fetch(url, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json'
      },
      // Cache the image list per movie for a long time (1 hour) since movie posters rarely change
      next: { revalidate: 3600 } 
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch from TMDb: ${response.statusText}`);
    }

    const data = await response.json();

    if (!data || !data.posters) {
      return [];
    }

    // We return just the file_path array to keep the payload small
    return data.posters.map((p: any) => p.file_path);
  } catch (error) {
    console.error(`Error fetching TMDb posters for ID ${tmdbId}:`, error);
    return [];
  }
}

export async function fetchTmdbBackdrops(tmdbId: string | number, media: string = 'movie') {
  const { tmdbApiKey } = await getDynamicConfig();

  if (!tmdbId || !tmdbApiKey) {
    return [];
  }

  try {
    const url = `https://api.themoviedb.org/3/${media === 'tv' ? 'tv' : 'movie'}/${tmdbId}/images?api_key=${tmdbApiKey}&include_image_language=en,es,it,null`;
    
    const response = await fetch(url, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json'
      },
      next: { revalidate: 3600 } 
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch from TMDb: ${response.statusText}`);
    }

    const data = await response.json();

    if (!data || !data.backdrops) {
      return [];
    }

    // Return the file_path array for backdrops
    return data.backdrops.map((b: any) => b.file_path);
  } catch (error) {
    console.error(`Error fetching TMDb backdrops for ID ${tmdbId}:`, error);
    return [];
  }
}

export type TmdbLogo = { path: string; lang: string | null };

// Title logos (transparent PNG/SVG), Spanish first, then English, then language-less: the
// same order the Chinoppo Biblioteca uses when it picks one by itself.
export async function fetchTmdbLogos(tmdbId: string | number, media: string = 'movie'): Promise<TmdbLogo[]> {
  const { tmdbApiKey } = await getDynamicConfig();

  if (!tmdbId || !tmdbApiKey) {
    return [];
  }

  try {
    const url = `https://api.themoviedb.org/3/${media === 'tv' ? 'tv' : 'movie'}/${tmdbId}/images?api_key=${tmdbApiKey}&include_image_language=es,en,null`;
    const response = await fetch(url, { headers: { 'Content-Type': 'application/json' }, next: { revalidate: 3600 } });
    if (!response.ok) {
      throw new Error(`Failed to fetch from TMDb: ${response.statusText}`);
    }
    const data = await response.json();
    const rank = (lang: string | null) => (lang === 'es' ? 0 : lang === 'en' ? 1 : lang === null ? 2 : 3);
    return (data?.logos ?? [])
      .sort((a: any, b: any) => rank(a.iso_639_1) - rank(b.iso_639_1) || (b.vote_average ?? 0) - (a.vote_average ?? 0))
      .map((l: any) => ({ path: l.file_path, lang: l.iso_639_1 }));
  } catch (error) {
    console.error(`Error fetching TMDb logos for ID ${tmdbId}:`, error);
    return [];
  }
}

// The posters of one season of a series (TMDb /tv/<id>/season/<n>/images)
export async function fetchTmdbSeasonPosters(tmdbId: string | number, season: number): Promise<string[]> {
  const { tmdbApiKey } = await getDynamicConfig();
  if (!tmdbId || !tmdbApiKey) return [];
  try {
    const url = `https://api.themoviedb.org/3/tv/${tmdbId}/season/${season}/images?api_key=${tmdbApiKey}&include_image_language=es,en,null`;
    const response = await fetch(url, { next: { revalidate: 3600 } });
    if (!response.ok) return [];
    const data = await response.json();
    return (data.posters || []).map((p: any) => p.file_path);
  } catch (error) {
    console.error(`Error fetching TMDb season posters for ${tmdbId} S${season}:`, error);
    return [];
  }
}

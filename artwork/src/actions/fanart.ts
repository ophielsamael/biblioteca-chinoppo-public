'use server'

import { getDynamicConfig } from './config';

export type FanartDisc = { url: string; type: string; lang: string };

// Disc art ("moviedisc": round transparent PNGs) of a movie on fanart.tv, by TMDb id.
// hasKey=false tells the page to ask for the key instead of saying "no discs".
export async function fetchFanartDiscs(tmdbId: string | number): Promise<{ hasKey: boolean; discs: FanartDisc[] }> {
  const { fanartApiKey } = await getDynamicConfig();
  if (!fanartApiKey) return { hasKey: false, discs: [] };
  if (!tmdbId) return { hasKey: true, discs: [] };
  try {
    const r = await fetch(`https://webservice.fanart.tv/v3/movies/${tmdbId}?api_key=${fanartApiKey}`,
                          { next: { revalidate: 3600 } });
    if (!r.ok) return { hasKey: true, discs: [] };   // 404: fanart.tv has nothing for this film
    const data = await r.json();
    const rank = (lang: string) => (lang === 'es' ? 0 : lang === 'en' ? 1 : 2);
    const discs: FanartDisc[] = (data?.moviedisc ?? [])
      .map((d: any) => ({ url: d.url, type: d.disc_type || '', lang: d.lang || '' }))
      .sort((a: FanartDisc, b: FanartDisc) => rank(a.lang) - rank(b.lang));
    return { hasKey: true, discs };
  } catch (error) {
    console.error(`Error fetching fanart.tv discs for ID ${tmdbId}:`, error);
    return { hasKey: true, discs: [] };
  }
}

'use server'

import { getDynamicConfig } from './config';

export type FanartDisc = { url: string; type: string; lang: string };

// A movie's art on fanart.tv, by TMDb id: disc art ("moviedisc": round transparent PNGs) and
// extra posters ("movieposter"), Spanish first. hasKey=false tells the page to ask for the key.
export async function fetchFanartDiscs(tmdbId: string | number): Promise<{ hasKey: boolean; discs: FanartDisc[]; posters: string[] }> {
  const { fanartApiKey } = await getDynamicConfig();
  if (!fanartApiKey) return { hasKey: false, discs: [], posters: [] };
  if (!tmdbId) return { hasKey: true, discs: [], posters: [] };
  try {
    const r = await fetch(`https://webservice.fanart.tv/v3/movies/${tmdbId}?api_key=${fanartApiKey}`,
                          { next: { revalidate: 3600 } });
    if (!r.ok) return { hasKey: true, discs: [], posters: [] };   // 404: fanart.tv has nothing for this film
    const data = await r.json();
    const rank = (lang: string) => (lang === 'es' ? 0 : lang === 'en' ? 1 : 2);
    const discs: FanartDisc[] = (data?.moviedisc ?? [])
      .map((d: any) => ({ url: d.url, type: d.disc_type || '', lang: d.lang || '' }))
      .sort((a: FanartDisc, b: FanartDisc) => rank(a.lang) - rank(b.lang));
    const posters: string[] = (data?.movieposter ?? [])
      .slice()
      .sort((a: any, b: any) => rank(a.lang || '') - rank(b.lang || ''))
      .map((p: any) => String(p.url))
      .filter((u: string) => u.startsWith('https://assets.fanart.tv/'));
    return { hasKey: true, discs, posters };
  } catch (error) {
    console.error(`Error fetching fanart.tv art for ID ${tmdbId}:`, error);
    return { hasKey: true, discs: [], posters: [] };
  }
}

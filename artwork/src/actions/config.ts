'use server'

import { cookies } from 'next/headers';
import { TMDB_API_KEY as DEFAULT_TMDB_API_KEY } from '../config/tmdb';
import { readKeys } from '../config/keys';

const PLACEHOLDER = /^(pon_aqui|tu_|YOUR_)/i;
const real = (v?: string) => (v && !PLACEHOLDER.test(v) ? v : '');

// Keys: the ones saved on the NAS (Ajustes window) first, then compose.yaml's, then, for people
// who used older versions, whatever an old browser cookie still holds.
export async function getDynamicConfig() {
  const saved = readKeys();
  const config = {
    tmdbApiKey: real(saved.tmdb) || DEFAULT_TMDB_API_KEY,
    fanartApiKey: real(saved.fanart) || real(process.env.FANART_API_KEY),
  };

  const cookie = (await cookies()).get('artwork_studio_config')?.value;
  if (cookie && (!config.tmdbApiKey || !config.fanartApiKey)) {
    try {
      const parsed = JSON.parse(decodeURIComponent(cookie));
      config.tmdbApiKey = config.tmdbApiKey || real(parsed.TMDB_API_KEY);
      config.fanartApiKey = config.fanartApiKey || real(parsed.FANART_API_KEY);
    } catch (e) {}
  }
  return config;
}

export async function getConfigStatus() {
  const config = await getDynamicConfig();
  const isTmdbConfigured = Boolean(config.tmdbApiKey);
  return {
    isTmdbConfigured,
    isFanartConfigured: Boolean(config.fanartApiKey),
    isFullyConfigured: isTmdbConfigured,   // posters, backdrops and logos all come from TMDb
  };
}

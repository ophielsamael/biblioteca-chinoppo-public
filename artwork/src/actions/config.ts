'use server'

import { cookies } from 'next/headers';
import { TMDB_API_KEY as DEFAULT_TMDB_API_KEY } from '../config/tmdb';

export async function getDynamicConfig() {
  const cookieStore = cookies();
  const configCookie = cookieStore.get('artwork_studio_config')?.value;
  
  let config = {
    tmdbApiKey: DEFAULT_TMDB_API_KEY,
    fanartApiKey: process.env.FANART_API_KEY || ''   // personal key from fanart.tv: disc art
  };

  if (configCookie) {
    try {
      const parsed = JSON.parse(decodeURIComponent(configCookie));
      if (parsed.TMDB_API_KEY) config.tmdbApiKey = parsed.TMDB_API_KEY;
      if (parsed.FANART_API_KEY) config.fanartApiKey = parsed.FANART_API_KEY;
    } catch (e) {}
  }
  return config;
}

export async function getConfigStatus() {
  const config = await getDynamicConfig();
  
  const isTmdbConfigured = Boolean(config.tmdbApiKey && !/^(pon_aqui|tu_|YOUR_)/i.test(config.tmdbApiKey));

  return {
    isTmdbConfigured,
    isFullyConfigured: isTmdbConfigured   // posters, backdrops and logos all come from TMDb
  };
}

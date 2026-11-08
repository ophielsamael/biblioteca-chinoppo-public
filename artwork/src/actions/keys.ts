'use server'

import { writeKeys } from '../config/keys';
import { BIBLIOTECA_URL } from './biblioteca';

export type KeyState = 'saved' | 'unchanged' | 'invalid' | 'unreachable';
export type SaveKeysResult = { tmdb: KeyState; fanart: KeyState; biblioteca: boolean };

async function status(url: string): Promise<number | null> {
  try {
    const r = await fetch(url, { cache: 'no-store', signal: AbortSignal.timeout(15000) });
    return r.status;
  } catch {
    return null;
  }
}

// Checks each key against its service before saving it, so a typo shows up right away. An empty
// field keeps what was saved. The TMDb key is also handed to the Biblioteca (it needs it too).
export async function saveKeys(input: { tmdb: string; fanart: string }): Promise<SaveKeysResult> {
  const tmdb = (input.tmdb || '').trim();
  const fanart = (input.fanart || '').trim();
  const out: SaveKeysResult = { tmdb: 'unchanged', fanart: 'unchanged', biblioteca: true };

  if (tmdb) {
    // the "API Key" (32 letters and numbers), not the long "Read Access Token"
    const code = /^[0-9a-fA-F]{32}$/.test(tmdb) ? await status(`https://api.themoviedb.org/3/configuration?api_key=${tmdb}`) : 401;
    out.tmdb = code === 200 ? 'saved' : code === null ? 'unreachable' : 'invalid';
  }
  if (fanart) {
    const code = await status(`https://webservice.fanart.tv/v3/movies/603?api_key=${encodeURIComponent(fanart)}`);
    out.fanart = code === 200 || code === 404 ? 'saved' : code === null ? 'unreachable' : 'invalid';   // 404: valid key, no art for that film
  }

  writeKeys({ tmdb: out.tmdb === 'saved' ? tmdb : undefined, fanart: out.fanart === 'saved' ? fanart : undefined });

  if (out.tmdb === 'saved') {
    try {
      const r = await fetch(`${BIBLIOTECA_URL}/api/keys`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tmdb }),
        signal: AbortSignal.timeout(15000),
      });
      out.biblioteca = r.ok;
    } catch {
      out.biblioteca = false;
    }
  }
  return out;
}

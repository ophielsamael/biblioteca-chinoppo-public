'use server'

import { BIBLIOTECA_URL } from './biblioteca';

// Badge styles (the format row under the title on the movie page) live in the Biblioteca.
export type BadgeStyle = { id: string; name: string; author: string; own: boolean; selected: boolean; saved: boolean };

export async function listBadgeStyles(): Promise<BadgeStyle[]> {
  try {
    const r = await fetch(`${BIBLIOTECA_URL}/api/badge-styles`, { cache: 'no-store', signal: AbortSignal.timeout(10000) });
    return r.ok ? await r.json() : [];
  } catch {
    return [];
  }
}

// Picks a style for every title; the Biblioteca first saves a full copy of it on the NAS.
export async function setBadgeStyle(id: string): Promise<boolean> {
  try {
    const r = await fetch(`${BIBLIOTECA_URL}/api/badge-style`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id }),
      signal: AbortSignal.timeout(120000),   // a whole template can take a while to download
    });
    return r.ok;
  } catch {
    return false;
  }
}

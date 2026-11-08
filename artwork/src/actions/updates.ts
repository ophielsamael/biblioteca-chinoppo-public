'use server'

import installed from '../../changelog.json';

// One entry per published version, newest first (artwork/changelog.json). `compose`: compose.yaml
// changed, so the app must be deleted and created again instead of just rebuilt. `usb`: the disc or
// the USB scripts changed, so the USB files must be downloaded again.
export type Release = {
  id: string;
  date: string;
  title: { es: string; en: string };
  changes: { es: string[]; en: string[] };
  compose: boolean;
  usb: boolean;
};
export type UpdateInfo = { installed: string; latest: string; newer: Release[] } | null;

const SOURCE = process.env.CHANGELOG_URL
  || 'https://raw.githubusercontent.com/ophielsamael/biblioteca-chinoppo-public/main/artwork/changelog.json';

export async function installedVersion(): Promise<string> {
  return (installed as Release[])[0]?.id || '';
}

// Compares this install with the changelog published on GitHub (asked at most every 15 minutes; force=true asks right now, bypassing the cache). The
// only thing sent is the request for that file. Returns null when up to date or when GitHub can't
// be reached (never an error on screen). UPDATE_CHECK=off turns it off.
export async function checkForUpdates(force = false): Promise<UpdateInfo> {
  if (process.env.UPDATE_CHECK === 'off') return null;
  const mine = await installedVersion();
  try {
    const r = await fetch(SOURCE, force ? { cache: 'no-store', signal: AbortSignal.timeout(8000) } : { next: { revalidate: 900 }, signal: AbortSignal.timeout(8000) });
    if (!r.ok) return null;
    const remote = (await r.json()) as Release[];
    if (!Array.isArray(remote) || !remote.length) return null;
    const newer = remote.filter((e) => e && typeof e.id === 'string' && e.id > mine);   // ids sort by date
    return newer.length ? { installed: mine, latest: newer[0].id, newer } : null;
  } catch {
    return null;
  }
}

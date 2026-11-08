import fs from 'fs';
import path from 'path';

// API keys typed in the Ajustes window, kept on the NAS (the artwork_data volume) so they work from
// any browser and survive updates. A key saved here wins over the compose.yaml environment.
const file = () => path.join(process.env.DATA_DIR || process.cwd(), 'keys.json');

export type SavedKeys = { tmdb?: string; fanart?: string };

export function readKeys(): SavedKeys {
  try {
    const d = JSON.parse(fs.readFileSync(file(), 'utf8'));
    return d && typeof d === 'object' ? d : {};
  } catch {
    return {};
  }
}

export function writeKeys(update: SavedKeys) {
  const next: SavedKeys = { ...readKeys() };
  if (update.tmdb) next.tmdb = update.tmdb;
  if (update.fanart) next.fanart = update.fanart;
  fs.mkdirSync(path.dirname(file()), { recursive: true });
  fs.writeFileSync(file(), JSON.stringify(next), 'utf8');
}

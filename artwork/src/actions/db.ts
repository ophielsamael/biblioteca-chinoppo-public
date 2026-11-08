import fs from 'fs';
import path from 'path';

// in /app/data (a volume) so the choices survive an update of the container
const dbPath = path.join(process.env.DATA_DIR || process.cwd(), 'applied_overlays.json');

// Overlays are remembered per Biblioteca item.
export function overlayKey(itemId: string | number): string {
  return `bib:${itemId}`;
}

export function getAppliedOverlays(): Record<string, string> {
  try {
    if (fs.existsSync(dbPath)) {
      const data = fs.readFileSync(dbPath, 'utf8');
      return JSON.parse(data);
    }
  } catch (error) {
    console.error('Error reading applied_overlays.json:', error);
  }
  return {};
}

export function saveAppliedOverlay(itemId: string, overlayType: string | null) {
  try {
    const overlays = getAppliedOverlays();
    if (overlayType && overlayType !== 'Sin Overlay') {
      overlays[itemId] = overlayType;
    } else {
      delete overlays[itemId];
    }
    fs.writeFileSync(dbPath, JSON.stringify(overlays, null, 2), 'utf8');
  } catch (error) {
    console.error('Error writing applied_overlays.json:', error);
  }
}

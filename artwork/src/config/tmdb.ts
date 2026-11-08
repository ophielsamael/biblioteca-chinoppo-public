// From the compose file (TMDB_API_KEY); its placeholder ("pon_aqui...") counts as missing
const ENV_TMDB = process.env.TMDB_API_KEY || '';
export const TMDB_API_KEY = /^(pon_aqui|tu_|YOUR_)/i.test(ENV_TMDB) ? '' : ENV_TMDB;
export const isTmdbConfigured = Boolean(TMDB_API_KEY);

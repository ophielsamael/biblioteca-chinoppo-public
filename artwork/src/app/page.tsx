"use client";

import React, { useState, useEffect, useRef } from "react";
import Image from "next/image";
import OverlaySelector, { overlayOptions } from "../components/OverlaySelector";
import { fetchLibraryItems, fetchLibraries } from "../actions/library";
import { fetchTmdbPosters, fetchTmdbBackdrops, fetchTmdbLogos, fetchTmdbSeasonPosters, type TmdbLogo } from "../actions/tmdb";
import { fetchFanartDiscs, type FanartDisc } from "../actions/fanart";
import { searchTmdb, getBibliotecaMatch, applyMatch, type TmdbHit, type BibliotecaMatch } from "../actions/metadata";
import { getConfigStatus } from "../actions/config";
import { translations, Language } from "../config/i18n";

// Types
interface Movie {
  id: string | number;
  title: string;
  year: number;
  genre: string;
  rating: number;
  currentPoster: string;
  posters: string[];
  selectedOverlay: string | null;
  backdrop: string;
  tmdbId?: string | null;
  path?: string | null;          // file path: finds the same title in the Biblioteca
  media?: 'movie' | 'tv';
  seasons?: number[];            // series only
  format?: Fmt | null;           // detected video/audio format, for the overlay/case proposal
}

interface Fmt {
  res?: string | null;           // "4K" | "1080p" | "720p" | "SD"
  hdr?: string[];                // "DV" | "HDR10+" | "HDR10" | "HLG"
  atmos?: boolean;
  dtsx?: boolean;
  "3d"?: boolean;
}

interface Library {
  id: string;
  name: string;
  collectionType?: string;
}

// Initial Mock Movies
const initialMovies: Movie[] = [
  {
    id: 1,
    title: "Neon Horizon",
    year: 2026,
    genre: "Ciencia Ficción / Thriller",
    rating: 8.9,
    currentPoster: "/posters/cyberpunk_neon_city.png",
    posters: [
      "/posters/cyberpunk_neon_city.png",
      "/posters/neon_city_alt_one.png",
      "/posters/neon_city_alt_two.png",
      "/posters/deep_space_astronaut.png"
    ],
    selectedOverlay: null,
    backdrop: "rgba(82, 181, 75, 0.15)"
  },
  {
    id: 2,
    title: "Odisea Estelar",
    year: 2025,
    genre: "Ciencia Ficción / Aventura",
    rating: 9.1,
    currentPoster: "/posters/deep_space_astronaut.png",
    posters: [
      "/posters/deep_space_astronaut.png",
      "/posters/retro_sunset_drive.png",
      "/posters/cyberpunk_neon_city.png"
    ],
    selectedOverlay: "UHDBD with DV and Atmos",
    backdrop: "rgba(142, 84, 233, 0.15)"
  },
  {
    id: 3,
    title: "El Bosque de los Secretos",
    year: 2024,
    genre: "Fantasía / Drama",
    rating: 8.5,
    currentPoster: "/posters/mystical_fantasy_forest.png",
    posters: [
      "/posters/mystical_fantasy_forest.png",
      "/posters/deep_space_astronaut.png"
    ],
    selectedOverlay: null,
    backdrop: "rgba(0, 198, 255, 0.15)"
  },
  {
    id: 4,
    title: "Atardecer Retro",
    year: 2023,
    genre: "Acción / Drama",
    rating: 7.8,
    currentPoster: "/posters/retro_sunset_drive.png",
    posters: [
      "/posters/retro_sunset_drive.png",
      "/posters/cyberpunk_neon_city.png"
    ],
    selectedOverlay: "UHDBD with HDR",
    backdrop: "rgba(255, 167, 81, 0.15)"
  }
];

export default function Home() {
  const [movies, setMovies] = useState<Movie[]>(initialMovies);
  const [libraries, setLibraries] = useState<Library[]>([]);
  const [activeLibraryId, setActiveLibraryId] = useState<string>("");
  const [selectedMovie, setSelectedMovie] = useState<Movie | null>(null);
  const [activeFilter, setActiveFilter] = useState<string>("Todos");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [configStatus, setConfigStatus] = useState<any>(null);
  const [showSettingsModal, setShowSettingsModal] = useState<boolean>(false);
  const [settingsForm, setSettingsForm] = useState({
    TMDB_API_KEY: '',
    FANART_API_KEY: '',
    LANGUAGE: 'es' as Language
  });

  // Fetch real libraries and config from Server on mount
  useEffect(() => {
    // 1. Check LocalStorage
    const stored = localStorage.getItem('artwork_studio_config');
    if (stored) {
      try {
        const parsed = JSON.parse(stored);
        setSettingsForm({
          ...parsed,
          LANGUAGE: parsed.LANGUAGE || 'es'
        });
      } catch (e) {}
    }

    getConfigStatus().then(status => {
      setConfigStatus(status);
      if (!status.isTmdbConfigured) setShowSettingsModal(true);   // keys normally come from compose.yaml
    });

    fetchLibraries().then(libs => {
      if (libs && libs.length > 0) {
        setLibraries(libs);
        const want = new URLSearchParams(window.location.search).get('lib');   // deep link: ?lib=&item=&tab=
        setActiveLibraryId((libs.find((l: Library) => l.id === want) || libs[0]).id);
      }
    });
  }, []);

  const saveSettings = () => {
    // Save to LocalStorage
    localStorage.setItem('artwork_studio_config', JSON.stringify(settingsForm));
    
    // Save to Cookie (accessible by Server Actions)
    document.cookie = "artwork_studio_config=" + encodeURIComponent(JSON.stringify(settingsForm)) + "; path=/; max-age=31536000";
    
    setShowSettingsModal(false);
    window.location.reload();
  };

  // Fetch movies when activeLibraryId changes
  useEffect(() => {
    if (activeLibraryId) {
      const activeLib = libraries.find(l => l.id === activeLibraryId);
      fetchLibraryItems(activeLibraryId).then(items => {
        setMovies(items || []);
        // deep link (?item=ID&tab=backdrop): open that title once, e.g. from a guide or a screenshot script
        const q = new URLSearchParams(window.location.search);
        const it = (items || []).find((m: Movie) => String(m.id) === q.get('item'));
        if (it && !deepLinked.current) {
          deepLinked.current = true;
          openModal(it);
          const tab = q.get('tab');
          if (tab && ['poster', 'backdrop', 'logo', 'disc', 'meta', 'seasons'].includes(tab)) setActiveTab(tab as any);
          if (tab === 'seasons' && it.seasons?.length) {
            setSeason(it.seasons[0]);
            fetchTmdbSeasonPosters(it.tmdbId || '', it.seasons[0]).then(setSeasonAlts);
          }
        }
      });
    }
  }, [activeLibraryId, libraries]);
  const deepLinked = useRef(false);

  // Modal Interactive States
  const [modalPoster, setModalPoster] = useState<string>("");
  const [modalOverlay, setModalOverlay] = useState<string | null>(null);
  const [modalCase, setModalCase] = useState<'' | 'bluray' | 'uhd' | 'none'>('');
  const [isApplying, setIsApplying] = useState<boolean>(false);
  const [isDownloading, setIsDownloading] = useState<boolean>(false);
  const [tmdbAlternatives, setTmdbAlternatives] = useState<string[]>([]);
  const [tmdbBackdrops, setTmdbBackdrops] = useState<string[]>([]);
  const [isLoadingTmdb, setIsLoadingTmdb] = useState<boolean>(false);
  const [pendingBackdrop, setPendingBackdrop] = useState<string | null>(null);
  const [pendingLogo, setPendingLogo] = useState<string | null>(null);
  const [pendingDisc, setPendingDisc] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'poster' | 'backdrop' | 'logo' | 'disc' | 'meta' | 'seasons'>('poster');
  const [season, setSeason] = useState<number | null>(null);
  const [seasonAlts, setSeasonAlts] = useState<string[] | null>(null);
  const [seasonVer, setSeasonVer] = useState(0);   // reloads the current season poster after a change
  const [metaQuery, setMetaQuery] = useState('');
  const [metaYear, setMetaYear] = useState('');
  const [metaHits, setMetaHits] = useState<TmdbHit[] | null>(null);
  const [metaBusy, setMetaBusy] = useState(false);
  const [metaMsg, setMetaMsg] = useState('');
  const [bibMatch, setBibMatch] = useState<BibliotecaMatch | null | undefined>(undefined);  // undefined = loading
  const [discs, setDiscs] = useState<{ hasKey: boolean; discs: FanartDisc[] }>({ hasKey: true, discs: [] });
  const [tmdbLogos, setTmdbLogos] = useState<TmdbLogo[]>([]);
  const [backdropFade, setBackdropFade] = useState(true);   // darker bottom for the player's icon bar

  const t = translations[settingsForm.LANGUAGE] || translations.es;

  // From the detected format, the banner and the case Artwork proposes (the user confirms or changes)
  const proposeFromFormat = (fmt?: Fmt | null): { overlay: string | null; caseType: 'uhd' | 'bluray' } => {
    if (!fmt || !fmt.res) return { overlay: null, caseType: 'bluray' };
    const is4k = fmt.res === '4K';
    const caseType: 'uhd' | 'bluray' = is4k ? 'uhd' : 'bluray';
    if (fmt['3d']) return { overlay: overlayOptions.includes('BD 3D') ? 'BD 3D' : null, caseType };
    const hdr = fmt.hdr || [];
    const hdrPart = hdr.includes('DV') ? 'DV' : hdr.includes('HDR10+') ? 'HDR10+'
      : (hdr.includes('HDR10') || hdr.includes('HLG')) ? 'HDR' : '';
    const audioPart = fmt.atmos ? 'Atmos' : fmt.dtsx ? 'DTS' : '';
    const prefix = is4k ? 'UHDBD' : 'BD';
    const tries = [
      hdrPart && audioPart ? `${prefix} with ${hdrPart} and ${audioPart}` : '',
      hdrPart ? `${prefix} with ${hdrPart}` : '',
      prefix,
    ];
    const overlay = tries.find(n => n && overlayOptions.includes(n)) || null;
    return { overlay, caseType };
  };

  // Modal Interactions
  const openModal = (movie: Movie) => {
    setSelectedMovie(movie);
    setModalPoster(movie.currentPoster);
    const proposal = proposeFromFormat(movie.format);
    // remembered overlay wins; otherwise the one the format suggests. Case always pre-set from format.
    setModalOverlay(movie.selectedOverlay || proposal.overlay);
    setModalCase(movie.selectedOverlay || !movie.format ? '' : proposal.caseType);
    setTmdbAlternatives([]);
    setTmdbBackdrops([]);
    setTmdbLogos([]);
    setDiscs({ hasKey: true, discs: [] });
    setPendingBackdrop(null);
    setPendingLogo(null);
    setPendingDisc(null);
    setActiveTab('poster');
    setMetaQuery(movie.title);
    setMetaYear(movie.year ? String(movie.year) : '');
    setMetaHits(null);
    setMetaMsg('');
    setBibMatch(undefined);
    getBibliotecaMatch(movie.path).then(setBibMatch);
    setSeason(null);
    setSeasonAlts(null);
    
    if (movie.tmdbId) {
      setIsLoadingTmdb(true);
      Promise.all([
        fetchTmdbPosters(movie.tmdbId, movie.media),
        fetchTmdbBackdrops(movie.tmdbId, movie.media),
        fetchTmdbLogos(movie.tmdbId, movie.media),
        // fanart.tv keys series by TVDB id, not TMDb: discs are for films only
        movie.media === 'tv' ? Promise.resolve({ hasKey: true, discs: [], posters: [] as string[] }) : fetchFanartDiscs(movie.tmdbId)
      ]).then(([posters, backdrops, logos, fanartDiscs]) => {
        setTmdbAlternatives([...posters, ...(fanartDiscs.posters || [])]);   // TMDb first, then fanart.tv
        setTmdbBackdrops(backdrops);
        setTmdbLogos(logos);
        setDiscs(fanartDiscs);
        setIsLoadingTmdb(false);
      }).catch(() => setIsLoadingTmdb(false));
    }
  };

  const runMetaSearch = async () => {
    if (!selectedMovie) return;
    setMetaBusy(true);
    setMetaHits(await searchTmdb(metaQuery, metaYear, selectedMovie.media || 'movie'));
    setMetaBusy(false);
  };

  const handleApplyMatch = async (hit: TmdbHit) => {
    if (!selectedMovie) return;
    setMetaBusy(true);
    const r = await applyMatch(selectedMovie.path, hit.id);
    setMetaBusy(false);
    const updated = { ...selectedMovie, tmdbId: r?.tmdb_id ? String(r.tmdb_id) : selectedMovie.tmdbId };
    setMovies(prev => prev.map(m => (m.id === updated.id ? updated : m)));
    openModal(updated);             // reload posters/logos/discs of the right title
    setActiveTab('meta');
    setMetaMsg(r ? t.matchApplied : t.matchFailed);
  };

  const openSeason = (n: number) => {
    if (!selectedMovie) return;
    setSeason(n);
    setSeasonAlts(null);
    fetchTmdbSeasonPosters(selectedMovie.tmdbId || '', n).then(setSeasonAlts);
  };

  const applySeasonPoster = async (posterUrl: string) => {
    if (!selectedMovie || season === null) return;
    setIsApplying(true);
    try {
      const r = await fetch('/api/set-season', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ posterUrl, tmdbId: selectedMovie.tmdbId, itemId: selectedMovie.id, season }),
      });
      if (r.ok) setSeasonVer(v => v + 1);
      else alert(t.seasonFailed);
    } catch (e) {
      console.error(e);
      alert(t.seasonFailed);
    } finally {
      setIsApplying(false);
    }
  };

  const closeModal = () => {
    setSelectedMovie(null);
    setTmdbAlternatives([]);
    setTmdbBackdrops([]);
    setTmdbLogos([]);
    setIsLoadingTmdb(false);
  };

  const handleApplyChanges = async () => {
    if (!selectedMovie) return;

    setIsApplying(true);
    try {
      // The poster is redone only when its tab was touched, or when nothing else was picked
      // (the plain "Aplicar" of the poster tab): picking just a backdrop must not apply the
      // banner and case that the format merely proposed.
      const p = proposeFromFormat(selectedMovie.format);
      const posterTouched = modalPoster !== selectedMovie.currentPoster
        || modalOverlay !== (selectedMovie.selectedOverlay || p.overlay)
        || modalCase !== (selectedMovie.selectedOverlay || !selectedMovie.format ? '' : p.caseType);
      if (!posterTouched && (pendingBackdrop || pendingLogo || pendingDisc)) {
        const failed = await applyPicked();
        if (failed.length) alert(t.applyFailed + ' ' + failed.join(', '));
        else closeModal();
        return;
      }
      const response = await fetch('/api/process-image', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          itemId: selectedMovie.id,
          tmdbPosterUrl: modalPoster,
          overlayType: modalOverlay,
          caseType: modalCase || null,
          title: selectedMovie.title,
          tmdbId: selectedMovie.tmdbId,
          media: selectedMovie.media
        })
      });
      
      const failed = response.ok ? await applyPicked() : [];
      if (response.ok) {
        if (failed.length) alert(t.applyFailed + ' ' + failed.join(', '));
        closeModal();
        if (activeLibraryId) {
          const activeLib = libraries.find(l => l.id === activeLibraryId);
          fetchLibraryItems(activeLibraryId).then(items => {
            setMovies(items || []);
          });
        }
      } else {
        alert("Error al fusionar la carátula en el servidor");
      }
    } catch (e) {
      console.error(e);
      alert("Fallo de conexión al aplicar cambios");
    } finally {
      setIsApplying(false);
    }
  };

  // Backdrop, logo and disc are only chosen in their tabs; "Aplicar Cambios" sends them with the poster.
  const pick = (cur: string | null, url: string) => (cur === url ? null : url);   // a second click unpicks
  const postJson = async (url: string, body: object): Promise<boolean> => {
    try {
      const r = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
      return r.ok;
    } catch (e) {
      console.error(e);
      return false;
    }
  };
  const applyPicked = async (): Promise<string[]> => {
    if (!selectedMovie) return [];
    const ids = { tmdbId: selectedMovie.tmdbId, itemId: selectedMovie.id, media: selectedMovie.media };
    const failed: string[] = [];
    if (pendingBackdrop && !(await postJson('/api/set-backdrop', { tmdbBackdropUrl: pendingBackdrop, ...ids }))) failed.push(t.backdropsTitle);
    if (pendingLogo && !(await postJson('/api/set-logo', { tmdbLogoUrl: pendingLogo, ...ids }))) failed.push(t.logosTitle);
    if (pendingDisc && !(await postJson('/api/set-disc', { discUrl: pendingDisc, ...ids }))) failed.push(t.discsTitle);
    return failed;
  };

  // Sync modal states when a movie is selected
  useEffect(() => {
    if (selectedMovie) {
      setModalPoster(selectedMovie.currentPoster);
      // keep the proposal from the format when there is no remembered overlay (openModal set it)
      setModalOverlay(selectedMovie.selectedOverlay || proposeFromFormat(selectedMovie.format).overlay);
    }
  }, [selectedMovie]);

  // Handle overlay source resolution
  const getOverlaySrc = (overlay: string | null) => {
    if (!overlay) return null;
    const cleanName = overlay
      .toLowerCase()
      .replace(/ with /g, "-")
      .replace(/ and /g, "-")
      .replace(/\s+/g, "-");
    return `/overlays/${cleanName}.png`;
  };

  // Handle color border glow based on overlay type
  const getGlowClass = (overlay: string | null) => {
    if (!overlay) return "border-emerald-500/30 hover:border-emerald-500/60 shadow-[0_0_10px_rgba(82,181,75,0.1)]";
    if (overlay.includes("DV")) return "border-purple-500/50 shadow-[0_0_20px_rgba(168,85,247,0.25)]";
    if (overlay.includes("HDR10+")) return "border-blue-500/50 shadow-[0_0_20px_rgba(59,130,246,0.25)]";
    if (overlay.includes("HDR")) return "border-amber-500/50 shadow-[0_0_20px_rgba(245,158,11,0.25)]";
    return "border-emerald-500/50 shadow-[0_0_20px_rgba(16,185,129,0.25)]";
  };

  // Handle canvas rendering and image download
  const handleDownload = () => {
    if (!selectedMovie) return;
    setIsDownloading(true);

    const canvas = document.createElement("canvas");
    canvas.width = 1000;
    canvas.height = 1500;
    const ctx = canvas.getContext("2d");

    if (!ctx) {
      setIsDownloading(false);
      return;
    }

    const posterImg = new window.Image();
    posterImg.crossOrigin = "anonymous";
    posterImg.src = modalPoster;

    posterImg.onload = () => {
      // Draw background poster
      ctx.drawImage(posterImg, 0, 0, 1000, 1500);

      const overlaySrc = getOverlaySrc(modalOverlay);
      if (overlaySrc) {
        const overlayImg = new window.Image();
        overlayImg.src = overlaySrc;
        overlayImg.onload = () => {
          ctx.drawImage(overlayImg, 0, 0, 1000, 1500);
          triggerDownloadLink();
        };
      } else {
        triggerDownloadLink();
      }
    };

    const triggerDownloadLink = () => {
      const dataUrl = canvas.toDataURL("image/png");
      const link = document.createElement("a");
      const overlaySuffix = modalOverlay ? modalOverlay.toLowerCase().replace(/[\+\s]/g, "_") : "original";
      link.download = `${selectedMovie.title.toLowerCase().replace(/\s+/g, "_")}_${overlaySuffix}.png`;
      link.href = dataUrl;
      link.click();
      setIsDownloading(false);
    };
  };

  // Filtering Logic
  const filteredMovies = movies.filter(movie => {
    const matchesSearch = movie.title.toLowerCase().includes(searchQuery.toLowerCase()) || 
                          movie.genre.toLowerCase().includes(searchQuery.toLowerCase());
    
    if (!matchesSearch) return false;

    if (activeFilter === "Todos" || activeFilter === "All" || activeFilter === t.filterAll) return true;
    if (activeFilter === "Con Overlay" || activeFilter === "With Overlay" || activeFilter === t.filterWithOverlay) return movie.selectedOverlay !== null;
    if (activeFilter === "Originales" || activeFilter === "Originals" || activeFilter === t.filterOriginals) return movie.selectedOverlay === null;
    
    return true;
  });

  if (!configStatus) {
    return (
      <div className="min-h-screen bg-[#0a0a0a] flex items-center justify-center">
        <div className="animate-pulse w-12 h-12 rounded-full bg-cyan-500/20 flex items-center justify-center">
          <div className="w-4 h-4 rounded-full bg-cyan-400"></div>
        </div>
      </div>
    );
  }

  const { isTmdbConfigured, isFullyConfigured } = configStatus;

  return (
    <main className="min-h-screen bg-[#0a0a0a] text-white font-sans selection:bg-cyan-500/30 flex flex-col">
      
      {/* HEADER */}
      <header className="w-full border-b border-white/5 bg-black/40 backdrop-blur-md sticky top-0 z-40 px-8 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-gradient-to-tr from-emerald-500 to-teal-600 flex items-center justify-center shadow-[0_0_15px_rgba(16,185,129,0.4)]">
            <span className="font-bold text-white tracking-widest text-lg">A</span>
          </div>
          <h1 className="text-xl font-bold tracking-widest bg-clip-text text-transparent bg-gradient-to-r from-white to-gray-400 uppercase">
            ARTWORK <span className="text-emerald-400">STUDIO</span>
          </h1>
        </div>
        <div className="flex gap-4">
          <button 
            onClick={() => setShowSettingsModal(true)}
            className="px-5 py-2 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-sm font-semibold transition-colors flex items-center gap-2"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"/></svg>
            {t.settings}
          </button>
        </div>
      </header>

      {/* MAIN CONTROL PANEL */}
      <section className="w-full max-w-[1400px] mx-auto px-6 py-10 flex-1 flex flex-col">
        <div className="relative w-full h-[300px] md:h-[400px] rounded-[2rem] overflow-hidden mb-12 border border-white/5 shadow-2xl group">
          <Image 
            src="/home_hero.png" 
            alt="Artwork Studio Home Theater" 
            fill 
            className="object-cover transition-transform duration-1000 group-hover:scale-105 opacity-60"
            priority
          />
          <div className="absolute inset-0 bg-gradient-to-r from-[#0a0a0a] via-[#0a0a0a]/60 to-transparent"></div>
          <div className="absolute inset-0 bg-gradient-to-t from-[#0a0a0a] via-transparent to-transparent"></div>
          
          <div className="absolute inset-0 flex flex-col justify-center px-8 md:px-16">
            <span className="text-emerald-400 font-black tracking-[0.3em] uppercase text-xs mb-4">{t.advancedEditor}</span>
            <h2 className="text-5xl md:text-7xl font-black mb-4 text-white tracking-tighter leading-none">
                ARTWORK <span className="text-transparent bg-clip-text bg-gradient-to-r from-emerald-400 to-teal-600">STUDIO</span>
            </h2>
            <p className="text-gray-300 text-sm md:text-lg max-w-xl font-medium leading-relaxed opacity-90">
                {t.heroDescription}
            </p>
          </div>
        </div>

        {/* ARTWORK STUDIO MODULE */}
        <div className="w-full flex-1 flex flex-col">
          <div className="flex items-center gap-4 mb-6">
             <h2 className="text-2xl font-bold tracking-wider uppercase text-white/90">{t.smartSystem} <span className="text-[#52b54b]">Artwork Studio</span></h2>
             <div className="flex-1 h-px bg-gradient-to-r from-white/10 to-transparent"></div>
          </div>

          {!isFullyConfigured ? (
            <div className="w-full rounded-2xl bg-orange-950/20 border border-orange-500/30 p-8 flex flex-col items-center justify-center text-center gap-4 my-10">
               <svg className="w-16 h-16 text-orange-500 drop-shadow-[0_0_10px_rgba(249,115,22,0.5)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                 <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
               </svg>
               
               <h3 className="text-xl font-bold text-orange-400">{t.moduleInactive}</h3>
               <p className="text-gray-400 max-w-xl leading-relaxed">{t.moduleInactiveDesc}</p>

               <button onClick={() => setShowSettingsModal(true)} className="mt-6 px-8 py-3 rounded-xl bg-orange-500/20 hover:bg-orange-500/30 border border-orange-500/50 text-orange-300 font-bold tracking-wider transition-all shadow-[0_0_15px_rgba(249,115,22,0.15)] hover:shadow-[0_0_25px_rgba(249,115,22,0.3)]">
                 {t.configCredentials}
               </button>
            </div>
          ) : (
            <div className="w-full bg-[#0B0F19] border border-white/5 rounded-2xl overflow-hidden flex flex-col shadow-2xl relative flex-1 min-h-[800px]">

      {/* Module Toolbar (Old Navbar) */}
      <div className="w-full glass border-b border-white/5 px-6 py-4 flex items-center justify-between bg-[#07090e]">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-[#52b54b] to-[#00a4dc] flex items-center justify-center shadow-lg shadow-emerald-500/20">
              <svg className="w-4 h-4 text-white" viewBox="0 0 24 24" fill="currentColor">
                <path d="M8 5v14l11-7z" />
              </svg>
            </div>
            <span className="font-black text-lg tracking-tight text-white">CHINOPPO <span className="text-[#52b54b]">ARTWORK</span></span>
          </div>
        </div>

        {/* Search Bar */}
        <div className="flex-1 max-w-md mx-6 hidden md:block">
          <div className="relative">
            <span className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-400">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
            </span>
            <input
              type="text"
              placeholder={t.searchPlaceholder}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-white/5 border border-white/10 rounded-xl py-2 pl-9 pr-4 text-sm text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-[#52b54b]/50 focus:border-transparent transition-all"
            />
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-4">
          <div className="w-9 h-9 rounded-full bg-gradient-to-tr from-emerald-600 to-emerald-400 flex items-center justify-center font-bold text-white shadow-md border border-white/10">
            A
          </div>
        </div>
      </div>

      {/* Main Layout Container */}
      <div className="flex-1 flex overflow-hidden">
        
        {/* Left Sidebar */}
        <aside className="w-64 bg-[#11131c]/40 border-r border-white/5 p-6 flex flex-col gap-8 hidden lg:flex">
          <div className="flex flex-col gap-2">
            <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">{t.myContent}</span>
            {libraries.map((lib) => (
              <button
                key={lib.id}
                onClick={() => setActiveLibraryId(lib.id)}
                className={`flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-all duration-200 ${
                  activeLibraryId === lib.id
                    ? "bg-[#52b54b]/10 text-[#52b54b] shadow-[inset_0_0_8px_rgba(82,181,75,0.05)] border-l-4 border-[#52b54b]"
                    : "text-gray-400 hover:text-white hover:bg-white/5"
                }`}
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
                </svg>
                {lib.name}
              </button>
            ))}
          </div>

          <div className="flex flex-col gap-2">
            <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">{t.tools}</span>
            {[
              { name: t.bannersAndOverlays, icon: "M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z", action: () => { setActiveFilter(t.filterAll); setSearchQuery(""); } },
              { name: t.settings, icon: "M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z", action: () => setShowSettingsModal(true) },
            ].map((tool) => (
              <button
                key={tool.name}
                onClick={tool.action}
                className="flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium text-gray-400 hover:text-white hover:bg-white/5 transition-all duration-200"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d={tool.icon} />
                </svg>
                {tool.name}
              </button>
            ))}
          </div>
        </aside>

        {/* Content Area */}
        <main className="flex-1 p-6 md:p-8 overflow-y-auto">
          
          {/* Header & Filter System */}
          <div className="flex flex-col gap-6 md:flex-row md:items-center md:justify-between mb-8">
            <div>
              <h1 className="text-3xl font-extrabold text-white tracking-tight">{t.libraryMovies}</h1>
              <p className="text-gray-400 text-sm mt-1">{t.libraryMoviesDesc}</p>
              {/* The library sidebar is hidden below lg: same choice as a select */}
              <select
                value={activeLibraryId}
                onChange={(e) => setActiveLibraryId(e.target.value)}
                className="lg:hidden mt-3 bg-[#1a1d29] text-white border border-white/10 rounded-lg px-3 py-2 text-sm"
              >
                {libraries.map((lib) => <option key={lib.id} value={lib.id}>{lib.name}</option>)}
              </select>
            </div>
            
            {/* Filter Buttons */}
            <div className="flex flex-wrap gap-2">
              {[t.filterAll, t.filterWithOverlay, t.filterOriginals].map((filter) => (
                <button
                  key={filter}
                  onClick={() => setActiveFilter(filter)}
                  className={`px-4 py-1.5 rounded-xl text-xs font-semibold border transition-all duration-200 ${
                    activeFilter === filter
                      ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30 shadow-[0_0_10px_rgba(82,181,75,0.15)]"
                      : "bg-white/5 text-gray-400 border-white/5 hover:bg-white/10 hover:text-white"
                  }`}
                >
                  {filter}
                </button>
              ))}
            </div>
          </div>

          {/* Grid list of Movies */}
          {filteredMovies.length === 0 ? (
            <div className="h-96 w-full flex flex-col items-center justify-center rounded-2xl border border-dashed border-white/10 p-8 text-center bg-white/2">
              <svg className="w-12 h-12 text-gray-600 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M7 4v16M17 4v16M3 8h4m10 0h4M3 12h18M3 16h4m10 0h4M4 20h16a1 1 0 001-1V5a1 1 0 00-1-1H4a1 1 0 00-1 1v14a1 1 0 001 1z" />
              </svg>
              <h3 className="text-lg font-bold text-white">{t.noMoviesFound}</h3>
              <p className="text-gray-500 text-sm max-w-xs mt-1">{t.noMoviesFoundDesc}</p>
            </div>
          ) : (
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 xl:grid-cols-4 gap-6">
              {filteredMovies.map((movie) => (
                <div
                  key={movie.id}
                  onClick={() => openModal(movie)}
                  className="group cursor-pointer flex flex-col gap-3 rounded-2xl bg-[#11131c]/50 border border-white/5 p-3 hover:bg-[#11131c]/80 transition-all duration-300 hover:shadow-2xl"
                >
                  {/* Poster wrapper with standard aspect ratio 2:3 */}
                  <div className={`relative aspect-[2/3] w-full rounded-xl overflow-hidden border-2 transition-all duration-300 ${getGlowClass(movie.selectedOverlay)}`}>
                    
                    {/* Main Poster Image */}
                    <div className="w-full h-full relative group-hover:scale-[1.03] transition-transform duration-500">
                      <Image
                        src={movie.currentPoster}
                        alt={movie.title}
                        fill
                        className="object-cover"
                        sizes="(max-width: 640px) 50vw, (max-width: 1024px) 33vw, 25vw"
                        priority
                        unoptimized
                      />
                    </div>

                    {/* Overlay dynamic Banner */}
                    {movie.selectedOverlay && (
                      <div className="absolute top-0 left-0 w-full h-full z-10 pointer-events-none">
                        <img
                          src={getOverlaySrc(movie.selectedOverlay) || ""}
                          alt={movie.selectedOverlay}
                          className="w-full h-auto object-contain object-top"
                        />
                      </div>
                    )}

                    {/* Hover actions overlay */}
                    <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 flex items-center justify-center transition-opacity duration-300 z-20">
                      <div className="p-3.5 rounded-full bg-emerald-500 text-white shadow-lg transform scale-90 group-hover:scale-100 transition-all duration-300 shadow-emerald-500/30">
                        <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                        </svg>
                      </div>
                    </div>

                    {/* Overlay type badge at the bottom */}
                    {movie.selectedOverlay && (
                      <div className="absolute bottom-2 right-2 px-2 py-0.5 rounded text-[9px] font-black tracking-wide uppercase bg-black/80 border border-white/10 z-20 truncate max-w-[80%]">
                        {movie.selectedOverlay}
                      </div>
                    )}
                  </div>

                  {/* Metadata */}
                  <div className="flex flex-col px-1">
                    <div className="flex items-center justify-between">
                      <h3 className="font-bold text-white text-sm group-hover:text-emerald-400 transition-colors truncate pr-2">{movie.title}</h3>
                      <span className="text-[10px] bg-emerald-500/10 text-emerald-400 px-1.5 py-0.5 rounded font-bold border border-emerald-500/20">{movie.rating}</span>
                    </div>
                    <div className="flex items-center gap-1.5 text-xs text-gray-500 mt-0.5">
                      <span>{movie.year}</span>
                      <span>•</span>
                      <span className="truncate">{movie.genre.split(" / ")[0]}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </main>
      </div>

      {/* Interactive Modal Component */}
      {selectedMovie && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 animate-fade-in bg-black/75 backdrop-blur-md">
          
          <div className="w-full max-w-5xl glass-premium rounded-3xl overflow-hidden animate-scale-up border border-white/10 flex flex-col max-h-[90vh]">
            
            {/* Modal Header */}
            <div className="px-6 py-4 border-b border-white/5 flex items-center justify-between bg-black/20">
              <div className="flex items-center gap-6">
                <div className="flex items-center gap-2">
                  <span className="text-[#52b54b] font-bold text-sm tracking-widest uppercase">{t.artworkStudio}</span>
                  <span className="text-gray-600 hidden sm:inline">•</span>
                  <span className="text-white font-bold text-base truncate max-w-[200px] hidden sm:inline">{selectedMovie.title}</span>
                </div>
                <div className="flex bg-black/40 rounded-lg p-1 border border-white/5">
                  <button 
                    onClick={() => setActiveTab('poster')}
                    className={`px-4 py-1.5 rounded-md text-xs font-bold transition-all ${activeTab === 'poster' ? 'bg-white/10 text-white shadow-sm' : 'text-gray-500 hover:text-gray-300'}`}
                  >
                    {t.mainPoster}
                  </button>
                  <button 
                    onClick={() => setActiveTab('backdrop')}
                    className={`px-4 py-1.5 rounded-md text-xs font-bold transition-all ${activeTab === 'backdrop' ? 'bg-white/10 text-white shadow-sm' : 'text-gray-500 hover:text-gray-300'}`}
                  >
                    {t.backdrops}
                  </button>
                  <button 
                    onClick={() => setActiveTab('logo')}
                    className={`px-4 py-1.5 rounded-md text-xs font-bold transition-all ${activeTab === 'logo' ? 'bg-white/10 text-white shadow-sm' : 'text-gray-500 hover:text-gray-300'}`}
                  >
                    {t.logos}
                  </button>
                  <button 
                    onClick={() => setActiveTab('disc')}
                    className={`px-4 py-1.5 rounded-md text-xs font-bold transition-all ${activeTab === 'disc' ? 'bg-white/10 text-white shadow-sm' : 'text-gray-500 hover:text-gray-300'}`}
                  >
                    {t.discs}
                  </button>
                  {selectedMovie.media === 'tv' && (
                    <button
                      onClick={() => { setActiveTab('seasons'); if (season === null && selectedMovie.seasons?.length) openSeason(selectedMovie.seasons[0]); }}
                      className={`px-4 py-1.5 rounded-md text-xs font-bold transition-all ${activeTab === 'seasons' ? 'bg-white/10 text-white shadow-sm' : 'text-gray-500 hover:text-gray-300'}`}
                    >
                      {t.seasons}
                    </button>
                  )}
                  <button
                    onClick={() => setActiveTab('meta')}
                    className={`px-4 py-1.5 rounded-md text-xs font-bold transition-all ${activeTab === 'meta' ? 'bg-white/10 text-white shadow-sm' : 'text-gray-500 hover:text-gray-300'}`}
                  >
                    {t.metadata}
                  </button>
                </div>
              </div>
              <button
                onClick={closeModal}
                className="p-1.5 rounded-lg bg-white/5 text-gray-400 hover:text-white hover:bg-white/10 transition-colors"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {/* Modal Content - Scrollable */}
            <div className="flex-1 overflow-y-auto p-6 md:p-8">
              {activeTab === 'poster' ? (
                <div className="grid grid-cols-1 md:grid-cols-12 gap-8">
                  {/* Left Side: Live Preview (5 columns) */}
                  <div className="md:col-span-5 flex flex-col gap-4">
                    <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">{t.artworkPreview}</span>
                    
                    {/* Dynamic Poster Container */}
                    <div className={`relative aspect-[2/3] w-full rounded-2xl overflow-hidden border-4 bg-black/40 transition-all duration-300 ${getGlowClass(modalOverlay)}`}>
                      
                      {/* Live Preview Image */}
                      <div className="w-full h-full relative">
                        <Image
                          src={modalPoster}
                          alt="Preview"
                          fill
                          className="object-cover"
                          sizes="(max-width: 768px) 100vw, 30vw"
                          priority
                          unoptimized
                        />
                      </div>

                      {/* Overlay preview on top */}
                      {modalOverlay && (
                        <div className="absolute top-0 left-0 w-full h-full z-10 pointer-events-none animate-fade-in">
                          <img
                            src={getOverlaySrc(modalOverlay) || ""}
                            alt="Overlay Preview"
                            className="w-full h-auto object-contain object-top"
                          />
                        </div>
                      )}
                      
                      {/* Overlay info label */}
                      <div className="absolute bottom-4 left-4 right-4 bg-black/80 backdrop-blur-md border border-white/10 rounded-xl px-3 py-1.5 flex items-center gap-2 truncate">
                        <div className={`flex-shrink-0 w-2.5 h-2.5 rounded-full ${
                          modalOverlay?.includes("HDR") ? "bg-amber-500 shadow-[0_0_8px_#f59e0b]" :
                          modalOverlay?.includes("DV") ? "bg-purple-500 shadow-[0_0_8px_#a855f7]" :
                          modalOverlay?.includes("HDR10+") ? "bg-blue-500 shadow-[0_0_8px_#3b82f6]" : "bg-emerald-500 shadow-[0_0_8px_#10b981]"
                        }`} />
                        <span className="text-xs font-bold text-white tracking-wide truncate">
                          {modalOverlay || t.originalNoOverlay}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Right Side: Options & Carousel (7 columns) */}
                  <div className="md:col-span-7 flex flex-col gap-6">
                    
                    {/* Title & Info */}
                    <div>
                      <h2 className="text-2xl font-extrabold text-white tracking-tight">{selectedMovie.title}</h2>
                      <div className="flex items-center gap-2 text-sm text-gray-400 mt-1">
                        <span>{selectedMovie.year}</span>
                        <span>•</span>
                        <span>{selectedMovie.genre}</span>
                        <span>•</span>
                        <span className="text-emerald-400 font-bold">{t.rating}: {selectedMovie.rating}</span>
                      </div>
                    </div>

                    <hr className="border-white/5" />

                    {/* A cover from the PC: for videos TMDb doesn't have, or a custom one */}
                    <label className="flex items-center justify-center gap-2 py-2.5 rounded-lg bg-white/5 hover:bg-white/10 text-sm font-semibold text-gray-300 hover:text-white border border-dashed border-white/20 cursor-pointer transition-colors">
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2M12 4v12m0-12l-4 4m4-4l4 4" /></svg>
                      {t.uploadPoster}
                      <input type="file" accept="image/png,image/jpeg,image/webp" className="hidden"
                             onChange={(e) => {
                               const file = e.target.files?.[0];
                               if (!file) return;
                               if (file.size > 20 * 1024 * 1024) { alert(t.uploadTooBig); return; }
                               const reader = new FileReader();
                               reader.onload = () => setModalPoster(String(reader.result));   // preview now, sent on Apply
                               reader.readAsDataURL(file);
                               e.target.value = '';
                             }} />
                    </label>

                    {/* TMDb Alternatives Scrollable Grid */}
                    <div className="w-full flex flex-col gap-3">
                      <span className="text-xs font-semibold text-gray-400 tracking-wider uppercase">
                        {t.tmdbAlternatives}
                      </span>
                      
                      {isLoadingTmdb ? (
                        <div className="text-center text-sm text-gray-500 py-10 animate-pulse">{t.loadingTmdbPosters}</div>
                      ) : tmdbAlternatives.length > 0 ? (
                        <div className="w-full max-h-[320px] overflow-y-auto overflow-x-hidden pr-2 border border-gray-800/50 rounded-lg p-2 bg-gray-900/30">
                          <div className="grid grid-cols-3 gap-3 w-full auto-rows-max">
                            {tmdbAlternatives.map((posterPath, index) => {
                              const fromFanart = posterPath.startsWith('https://');   // fanart.tv posters come as full URLs
                              const originalUrl = fromFanart ? posterPath : `https://image.tmdb.org/t/p/original${posterPath}`;
                              const isSelected = modalPoster === originalUrl;

                              return (
                                <div 
                                  key={index} 
                                  onClick={() => setModalPoster(originalUrl)}
                                  className={`relative w-full aspect-[2/3] rounded-md overflow-hidden border border-gray-700/60 hover:border-green-500 cursor-pointer transition-all bg-gray-950 block ${isSelected ? 'border-green-500 shadow-[0_0_15px_rgba(82,181,75,0.4)]' : ''}`}
                                >
                                  <img 
                                    src={fromFanart ? posterPath.replace('/fanart/', '/preview/') : `https://image.tmdb.org/t/p/w185${posterPath}`} 
                                    alt={fromFanart ? "fanart.tv poster" : "TMDb alternative"}
                                    className="absolute inset-0 w-full h-full object-cover block m-0 p-0"
                                  />
                                  {fromFanart && (
                                    <span className="absolute bottom-1 right-1 text-[9px] font-bold uppercase bg-black/70 text-gray-200 rounded px-1 py-0.5">fanart</span>
                                  )}
                                  {isSelected && (
                                    <div className="absolute inset-0 bg-green-500/20 flex items-center justify-center pointer-events-none">
                                      <svg className="w-8 h-8 text-white drop-shadow-md" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
                                      </svg>
                                    </div>
                                  )}
                                </div>
                              );
                            })}
                          </div>
                        </div>
                      ) : (
                        <div className="text-center text-sm text-gray-500 py-10">{t.noTmdbAlternatives}</div>
                      )}
                    </div>

                    <hr className="border-white/5" />

                    {/* Overlay Selection Banners Dropdown */}
                    <OverlaySelector 
                      value={modalOverlay} 
                      onChange={setModalOverlay} 
                      t={t}
                    />

                    {/* Blu-ray / 4K case, chosen per title (not every film is 4K) */}
                    <div className="flex flex-col gap-3 w-full">
                      <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">{t.caseLabel}</span>
                      <div className="grid grid-cols-2 gap-2">
                        {([['', t.caseKeep], ['bluray', t.caseHd], ['uhd', t.case4k], ['none', t.caseNone]] as const).map(([value, label]) => (
                          <button
                            key={value}
                            onClick={() => setModalCase(value)}
                            className={`py-2.5 rounded-xl text-sm font-bold border transition-all ${modalCase === value ? 'bg-emerald-500 border-emerald-400 text-white' : 'bg-[#11131c] border-white/10 text-gray-300 hover:bg-[#1a1c24]'}`}
                          >
                            {label}
                          </button>
                        ))}
                      </div>
                      <p className="text-xs text-gray-500 px-1">{t.caseDesc}</p>
                    </div>

                  </div>
                </div>
              ) : activeTab === 'backdrop' ? (
                <div className="flex flex-col gap-6 animate-fade-in">
                  <div>
                    <h2 className="text-2xl font-extrabold text-white tracking-tight">{selectedMovie.title} - {t.backdropsTitle}</h2>
                    <p className="text-gray-400 text-sm mt-1">{t.backdropsDesc}</p>
                    <label className="mt-3 inline-flex items-center gap-2 text-sm text-gray-300 cursor-pointer">
                      <input type="checkbox" checked={backdropFade} onChange={(e) => setBackdropFade(e.target.checked)} />
                      {t.backdropFade}
                    </label>
                  </div>
                  
                  {isLoadingTmdb ? (
                    <div className="text-center text-sm text-gray-500 py-20 animate-pulse">{t.loadingTmdbBackdrops}</div>
                  ) : tmdbBackdrops.length > 0 ? (
                    <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-6">
                      {tmdbBackdrops.map((backdropPath, index) => {
                        const originalUrl = `https://image.tmdb.org/t/p/original${backdropPath}`;
                        const previewUrl = `https://image.tmdb.org/t/p/w780${backdropPath}`;
                        return (
                          <div key={index} className="flex flex-col gap-3 group">
                            <div className={`relative aspect-video w-full rounded-xl overflow-hidden border transition-all bg-gray-950 shadow-lg ${pendingBackdrop === originalUrl ? 'border-emerald-400 ring-2 ring-emerald-400' : 'border-gray-700/60 group-hover:border-emerald-500'}`}>
                              <img
                                src={previewUrl}
                                alt="Backdrop"
                                className="absolute inset-0 w-full h-full object-cover block m-0 p-0 group-hover:scale-105 transition-transform duration-500"
                                loading="lazy"
                              />
                            </div>
                            <button
                              onClick={() => setPendingBackdrop(pick(pendingBackdrop, originalUrl))}
                              disabled={isApplying}
                              className={`w-full py-2.5 rounded-lg text-sm font-semibold transition-colors border shadow-md flex items-center justify-center gap-2 ${pendingBackdrop === originalUrl ? 'bg-emerald-500 text-white border-emerald-400' : 'bg-white/5 hover:bg-emerald-500 text-gray-300 hover:text-white border-white/10 hover:border-emerald-400'}`}
                            >
                              {pendingBackdrop === originalUrl ? `✓ ${t.chosen}` : t.applyBackdrop}
                            </button>
                            <div className="flex gap-2">
                              {(['png', 'jpg'] as const).map((format) => (
                                <a
                                  key={format}
                                  href={`/api/backdrop-download?path=${encodeURIComponent(backdropPath)}&format=${format}&fade=${backdropFade ? 1 : 0}&name=${encodeURIComponent(selectedMovie.title)}`}
                                  className="flex-1 py-2 rounded-lg bg-white/5 hover:bg-white/10 text-xs font-semibold text-gray-300 hover:text-white transition-colors border border-white/10 text-center"
                                >
                                  {format.toUpperCase()} 1080p
                                </a>
                              ))}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <div className="text-center text-sm text-gray-500 py-20 border border-dashed border-gray-800 rounded-2xl">
                      {t.noTmdbBackdrops}
                    </div>
                  )}
                </div>
              ) : activeTab === 'logo' ? (
                <div className="flex flex-col gap-6 animate-fade-in">
                  <div>
                    <h2 className="text-2xl font-extrabold text-white tracking-tight">{selectedMovie.title} - {t.logosTitle}</h2>
                    <p className="text-gray-400 text-sm mt-1">{t.logosDesc}</p>
                  </div>
                  {isLoadingTmdb ? (
                    <div className="text-center text-sm text-gray-500 py-20 animate-pulse">{t.loadingTmdbLogos}</div>
                  ) : tmdbLogos.length > 0 ? (
                    <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-6">
                      {tmdbLogos.map((logo, index) => (
                        <div key={index} className="flex flex-col gap-3 group">
                          {/* logos are transparent: show them on a dark backdrop-like box */}
                          <div className={`relative aspect-video w-full rounded-xl overflow-hidden border transition-all bg-gradient-to-br from-gray-800 to-gray-950 shadow-lg flex items-center justify-center p-6 ${pendingLogo === `https://image.tmdb.org/t/p/original${logo.path}` ? 'border-emerald-400 ring-2 ring-emerald-400' : 'border-gray-700/60 group-hover:border-emerald-500'}`}>
                            <img
                              src={`https://image.tmdb.org/t/p/w500${logo.path}`}
                              alt="Logo"
                              className="max-w-full max-h-full object-contain"
                              loading="lazy"
                            />
                            <span className="absolute top-2 right-2 text-[10px] font-bold uppercase bg-black/70 text-gray-300 rounded px-1.5 py-0.5">
                              {logo.lang || '—'}
                            </span>
                          </div>
                          <button
                            onClick={() => setPendingLogo(pick(pendingLogo, `https://image.tmdb.org/t/p/original${logo.path}`))}
                            disabled={isApplying}
                            className={`w-full py-2.5 rounded-lg text-sm font-semibold transition-colors border shadow-md ${pendingLogo === `https://image.tmdb.org/t/p/original${logo.path}` ? 'bg-emerald-500 text-white border-emerald-400' : 'bg-white/5 hover:bg-emerald-500 text-gray-300 hover:text-white border-white/10 hover:border-emerald-400'}`}
                          >
                            {pendingLogo === `https://image.tmdb.org/t/p/original${logo.path}` ? `✓ ${t.chosen}` : t.applyLogo}
                          </button>
                          <a
                            href={`/api/logo-download?path=${encodeURIComponent(logo.path)}&name=${encodeURIComponent(selectedMovie.title)}`}
                            className="py-2 rounded-lg bg-white/5 hover:bg-white/10 text-xs font-semibold text-gray-300 hover:text-white transition-colors border border-white/10 text-center"
                          >
                            {t.downloadLogo}
                          </a>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-center text-sm text-gray-500 py-20 border border-dashed border-gray-800 rounded-2xl">
                      {t.noTmdbLogos}
                    </div>
                  )}
                </div>
              ) : activeTab === 'seasons' ? (
                <div className="flex flex-col gap-6 animate-fade-in">
                  <div>
                    <h2 className="text-2xl font-extrabold text-white tracking-tight">{selectedMovie.title} - {t.seasonsTitle}</h2>
                    <p className="text-gray-400 text-sm mt-1">{t.seasonsDesc}</p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {(selectedMovie.seasons || []).map((n) => (
                      <button key={n} onClick={() => openSeason(n)}
                              className={`px-4 py-2 rounded-lg text-sm font-bold border transition-colors ${season === n ? 'bg-[#52b54b] border-[#52b54b] text-white' : 'bg-white/5 border-white/10 text-gray-300 hover:text-white'}`}>
                        {t.season} {n}
                      </button>
                    ))}
                  </div>
                  {season !== null && (
                    <div className="grid grid-cols-1 md:grid-cols-12 gap-8">
                      <div className="md:col-span-4 flex flex-col gap-3">
                        <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">{t.currentSeasonPoster}</span>
                        <div className="aspect-[2/3] w-full rounded-2xl overflow-hidden border-4 border-white/10 bg-black/40">
                          <img src={`/api/image-proxy?itemId=${selectedMovie.id}&season=${season}&v=${seasonVer}`} alt="" className="w-full h-full object-cover" />
                        </div>
                        <label className="flex items-center justify-center gap-2 py-2.5 rounded-lg bg-white/5 hover:bg-white/10 text-sm font-semibold text-gray-300 hover:text-white border border-dashed border-white/20 cursor-pointer transition-colors">
                          {t.uploadPoster}
                          <input type="file" accept="image/png,image/jpeg,image/webp" className="hidden" disabled={isApplying}
                                 onChange={(e) => {
                                   const file = e.target.files?.[0];
                                   if (!file) return;
                                   if (file.size > 20 * 1024 * 1024) { alert(t.uploadTooBig); return; }
                                   const reader = new FileReader();
                                   reader.onload = () => applySeasonPoster(String(reader.result));
                                   reader.readAsDataURL(file);
                                   e.target.value = '';
                                 }} />
                        </label>
                      </div>
                      <div className="md:col-span-8 flex flex-col gap-3">
                        <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">{t.tmdbAlternatives}</span>
                        {seasonAlts === null ? (
                          <div className="text-center text-sm text-gray-500 py-10 animate-pulse">{t.loadingTmdbPosters}</div>
                        ) : seasonAlts.length === 0 ? (
                          <div className="text-center text-sm text-gray-500 py-10">{t.noTmdbAlternatives}</div>
                        ) : (
                          <div className="grid grid-cols-3 sm:grid-cols-4 gap-3 max-h-[520px] overflow-y-auto pr-2">
                            {seasonAlts.map((p) => (
                              <div key={p} className="flex flex-col gap-2">
                                <img src={`https://image.tmdb.org/t/p/w185${p}`} alt="" loading="lazy"
                                     className="w-full aspect-[2/3] object-cover rounded-md border border-gray-700/60" />
                                <button onClick={() => applySeasonPoster(`https://image.tmdb.org/t/p/original${p}`)} disabled={isApplying}
                                        className="py-1.5 rounded-md bg-white/5 hover:bg-emerald-500 text-xs font-semibold text-gray-300 hover:text-white border border-white/10 disabled:opacity-50">
                                  {t.useThis}
                                </button>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              ) : activeTab === 'meta' ? (
                <div className="flex flex-col gap-6 animate-fade-in">
                  <div>
                    <h2 className="text-2xl font-extrabold text-white tracking-tight">{selectedMovie.title} - {t.metadataTitle}</h2>
                    <p className="text-gray-400 text-sm mt-1">{t.metadataDesc}</p>
                  </div>
                  <div className="flex flex-wrap gap-3 text-sm">
                    <span className="bg-black/40 border border-white/10 rounded-lg px-3 py-2 text-gray-300">
                      {t.bibliotecaMatch}:{' '}
                      {bibMatch === undefined ? '…' : bibMatch === null ? <i className="text-gray-500">{t.notInBiblioteca}</i> : (
                        <b className="text-white">TMDb {bibMatch.tmdb_id || '—'}{bibMatch.locked ? ` · ${t.matchLocked}` : ''}</b>
                      )}
                    </span>
                  </div>
                  <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); runMetaSearch(); }}>
                    <input value={metaQuery} onChange={(e) => setMetaQuery(e.target.value)}
                           className="flex-1 bg-[#1a1d29] text-white border border-white/10 rounded-lg px-3 py-2 text-sm" />
                    <input value={metaYear} onChange={(e) => setMetaYear(e.target.value)} placeholder={t.yearPh}
                           className="w-24 bg-[#1a1d29] text-white border border-white/10 rounded-lg px-3 py-2 text-sm" />
                    <button type="submit" disabled={metaBusy}
                            className="px-5 py-2 rounded-lg bg-[#52b54b] hover:bg-[#46a03f] text-white text-sm font-bold disabled:opacity-50">
                      {t.search}
                    </button>
                  </form>
                  {metaMsg && <div className="text-sm text-emerald-300">{metaMsg}</div>}
                  {metaHits && metaHits.length === 0 && (
                    <div className="text-center text-sm text-gray-500 py-12 border border-dashed border-gray-800 rounded-2xl">{t.noResults}</div>
                  )}
                  {metaHits && metaHits.length > 0 && (
                    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-5">
                      {metaHits.map((hit) => (
                        <div key={hit.id} className={`flex flex-col gap-2 rounded-xl p-2 border ${String(hit.id) === String(selectedMovie.tmdbId) ? 'border-[#52b54b]' : 'border-transparent'}`}>
                          <div className="aspect-[2/3] w-full rounded-lg overflow-hidden bg-gray-900">
                            {hit.poster && <img src={`https://image.tmdb.org/t/p/w342${hit.poster}`} alt={hit.title} className="w-full h-full object-cover" loading="lazy" />}
                          </div>
                          <div className="text-sm font-bold text-white leading-tight">{hit.title} {hit.year && <span className="text-gray-400 font-normal">({hit.year})</span>}</div>
                          {hit.originalTitle && hit.originalTitle !== hit.title && <div className="text-xs text-gray-500 -mt-1">{hit.originalTitle}</div>}
                          <div className="text-xs text-gray-500">TMDb {hit.id} · {hit.votes} {t.votes}</div>
                          <button onClick={() => handleApplyMatch(hit)} disabled={metaBusy}
                                  className="w-full py-2 rounded-lg bg-white/5 hover:bg-emerald-500 text-sm font-semibold text-gray-300 hover:text-white transition-colors border border-white/10 disabled:opacity-50">
                            {t.useThis}
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ) : (
                <div className="flex flex-col gap-6 animate-fade-in">
                  <div>
                    <h2 className="text-2xl font-extrabold text-white tracking-tight">{selectedMovie.title} - {t.discsTitle}</h2>
                    <p className="text-gray-400 text-sm mt-1">{t.discsDesc}</p>
                  </div>
                  {isLoadingTmdb ? (
                    <div className="text-center text-sm text-gray-500 py-20 animate-pulse">{t.loadingDiscs}</div>
                  ) : !discs.hasKey ? (
                    <div className="text-center text-sm text-gray-500 py-20 border border-dashed border-gray-800 rounded-2xl">{t.noFanartKey}</div>
                  ) : discs.discs.length > 0 ? (
                    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-6">
                      {discs.discs.map((disc, index) => (
                        <div key={index} className="flex flex-col gap-3 group">
                          <div className={`relative aspect-square w-full rounded-full overflow-hidden bg-gray-950 shadow-lg border transition-all ${pendingDisc === disc.url ? 'border-emerald-400 ring-4 ring-emerald-400' : 'border-gray-700/60 group-hover:border-emerald-500'}`}>
                            <img src={disc.url.replace('/fanart/', '/preview/')} alt="Disco" className="w-full h-full object-contain" loading="lazy" />
                          </div>
                          <div className="flex justify-center gap-2 text-[10px] font-bold uppercase text-gray-400">
                            <span className="bg-black/60 rounded px-1.5 py-0.5">{disc.type || 'disc'}</span>
                            <span className="bg-black/60 rounded px-1.5 py-0.5">{disc.lang || '—'}</span>
                          </div>
                          <button
                            onClick={() => setPendingDisc(pick(pendingDisc, disc.url))}
                            disabled={isApplying}
                            className={`w-full py-2.5 rounded-lg text-sm font-semibold transition-colors border shadow-md ${pendingDisc === disc.url ? 'bg-emerald-500 text-white border-emerald-400' : 'bg-white/5 hover:bg-emerald-500 text-gray-300 hover:text-white border-white/10 hover:border-emerald-400'}`}
                          >
                            {pendingDisc === disc.url ? `✓ ${t.chosen}` : t.applyDisc}
                          </button>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-center text-sm text-gray-500 py-20 border border-dashed border-gray-800 rounded-2xl">{t.noDiscs}</div>
                  )}
                </div>
              )}
              

          </div>
            {/* Modal Footer Actions */}
            {/* on every tab: one button applies the poster tab and whatever was picked in the others */}
            {(
              <div className="px-6 py-5 border-t border-white/5 bg-black/40 flex flex-col sm:flex-row items-center justify-between gap-4">

                {/* Left Action: Live Export (poster tab only) */}
                {activeTab !== 'poster' ? (
                  <span className="text-xs text-gray-400">
                    {[pendingBackdrop && t.backdropsTitle, pendingLogo && t.logosTitle, pendingDisc && t.discsTitle].filter(Boolean).join(' · ') || t.nothingPicked}
                  </span>
                ) : <button
                  onClick={handleDownload}
                  disabled={isDownloading}
                  className="w-full sm:w-auto px-6 py-3 rounded-2xl font-bold bg-white/5 border border-white/10 hover:bg-white/10 text-white flex items-center justify-center gap-2 hover:scale-[1.02] active:scale-95 transition-all duration-200 disabled:opacity-50"
                >
                  {isDownloading ? (
                    <>
                      <svg className="animate-spin h-5 w-5 text-white" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                      </svg>
                      <span>{t.processing}</span>
                    </>
                  ) : (
                    <>
                      <svg className="w-5 h-5 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4-4m0 0l-4-4m4 4V4" />
                      </svg>
                      <span>{t.downloadArtwork}</span>
                    </>
                  )}
                </button>}

                {/* Right Actions: Apply or Cancel */}
                <div className="flex items-center gap-4">
                  <button 
                    onClick={closeModal}
                    disabled={isApplying}
                    className="px-6 py-2 rounded-lg text-sm font-semibold text-gray-300 hover:text-white transition-colors disabled:opacity-50"
                  >
                    {t.cancel}
                  </button>
                  <button 
                    onClick={handleApplyChanges}
                    disabled={isApplying}
                    className={`px-6 py-2 rounded-lg text-sm font-semibold text-white transition-all shadow-lg ${isApplying ? 'bg-gray-600 cursor-not-allowed' : 'bg-gradient-to-r from-[#52b54b] to-[#42953c] hover:shadow-[0_0_20px_rgba(82,181,75,0.4)]'}`}
                  >
                    {isApplying ? t.applying : t.applyChanges}
                  </button>
                </div>
              </div>
            )}
        </div>
      </div>
    )}

      {/* Footer inside the module */}
            <footer className="mt-auto border-t border-white/5 py-6 px-8 flex items-center justify-between text-xs text-gray-500 bg-[#090a0f]/60">
              <span>Artwork Studio · Biblioteca Chinoppo</span>
              <div className="flex gap-4">
                <a href="#" className="hover:underline">TMDb API</a>
              </div>
            </footer>
          </div>
          )}
        </div>
      </section>

      {/* GLOBAL SETTINGS MODAL */}
      {showSettingsModal && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-fade-in">
          <div className="w-full max-w-lg bg-[#0f111a] border border-white/10 rounded-3xl shadow-2xl overflow-hidden">
            <div className="px-6 py-4 border-b border-white/5 bg-black/40 flex justify-between items-center">
              <h3 className="text-emerald-400 font-bold tracking-wider uppercase text-sm">{t.connectionConfig}</h3>
              <button onClick={() => setShowSettingsModal(false)} className="text-gray-500 hover:text-white">
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12"/></svg>
              </button>
            </div>
            
            <div className="p-6 flex flex-col gap-5">
              <div>
                <label className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1 block">{t.language}</label>
                <select
                  value={settingsForm.LANGUAGE}
                  onChange={(e) => setSettingsForm({...settingsForm, LANGUAGE: e.target.value as Language})}
                  className="w-full bg-black/40 border border-white/10 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:border-emerald-500/50 appearance-none"
                >
                  <option value="es">Español</option>
                  <option value="en">English</option>
                </select>
              </div>
              <div>
                <label className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1 block">{t.tmdbApiKeyLabel}</label>
                <input 
                  type="password" 
                  value={settingsForm.TMDB_API_KEY}
                  onChange={(e) => setSettingsForm({...settingsForm, TMDB_API_KEY: e.target.value})}
                  placeholder={t.tmdbApiKeyPlaceholder}
                  className="w-full bg-black/40 border border-white/10 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:border-emerald-500/50"
                />
              </div>
              <div>
                <label className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1 block">{t.fanartApiKeyLabel}</label>
                <input 
                  type="password" 
                  value={settingsForm.FANART_API_KEY || ''}
                  onChange={(e) => setSettingsForm({...settingsForm, FANART_API_KEY: e.target.value})}
                  placeholder={t.fanartApiKeyPlaceholder}
                  className="w-full bg-black/40 border border-white/10 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:border-emerald-500/50"
                />
              </div>
            </div>

            <div className="px-6 py-5 border-t border-white/5 bg-black/20 flex justify-end gap-3">
              <button 
                onClick={() => setShowSettingsModal(false)}
                className="px-5 py-2.5 rounded-xl text-sm font-semibold text-gray-400 hover:text-white"
              >
                {t.cancel}
              </button>
              <button 
                onClick={saveSettings}
                className="px-6 py-2.5 rounded-xl text-sm font-bold bg-emerald-500 text-white hover:bg-emerald-400 shadow-[0_0_15px_rgba(16,185,129,0.3)] transition-all"
              >
                {t.saveAndReload}
              </button>
            </div>
          </div>
        </div>
      )}

    </main>
  );
}

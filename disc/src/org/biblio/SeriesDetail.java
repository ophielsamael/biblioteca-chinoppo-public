package org.biblio;

import java.awt.Color;
import java.awt.Font;
import java.awt.Graphics;
import java.awt.Image;
import java.io.IOException;
import java.util.Hashtable;
import java.util.Vector;

/** Series page, as in Plex: data on top, a row of season posters below; OK on a season shows its
 *  episodes in that row (4 cards), UP goes back to the seasons. */
public class SeriesDetail implements Screen {
    static final int CARDS = 4, CW = 240, CH = 135, CX = 60, CY = 470, CGAP = 26, TX = 270, TW = 950;
    static final int SEASONS = 7, SW = 140, SH = 210, SGAP = 22, SY = 400;   // season posters row
    static final Color MUTED = new Color(90, 90, 100);

    private final BibliotecaXlet host;
    private final Wall wall;
    private final String id;
    private Hashtable m = new Hashtable();
    private String[] seasons = new String[0], counts = new String[0];
    private int seasonIdx, firstSeason;
    private final Image[] seasonPosters = new Image[SEASONS];
    private int seasonGeneration;
    private String[][] eps = new String[0][];   // number, title, air_date, ep_file_id, resume, overview
    private int epIdx, first;
    private final Image[] stills = new Image[CARDS];
    private Image backdrop, poster, logo, seasonTop, seasonBadges;   // open season's poster and format badges
    static final int TOP_W = 180, TOP_H = 270, BADGE_H = 28;
    private boolean logoDone;   // title text only once we know there is no logo (no flicker)
    private boolean onEpisodes, closed;   // false: the seasons row has the focus
    private int generation;
    private String status = "Cargando...";

    public SeriesDetail(BibliotecaXlet host, Wall wall, String id) {
        this.host = host;
        this.wall = wall;
        this.id = id;
        Wall.background(new Runnable() {
            public void run() { load(); }
        });
    }

    private void load() {
        try {
            m = Proto.map(Net.text("/d/item?id=" + id));
            String s = str("seasons");
            seasons = s.length() == 0 ? new String[0] : Proto.splitOn(s, ',');
            String c = str("season_counts");
            counts = c.length() == 0 ? new String[0] : Proto.splitOn(c, ',');
            seasonIdx = seasons.length - 1 >= 0 ? 0 : -1;
            status = seasons.length == 0 ? "No hay episodios en el NAS" : null;
            logo = Img.load("/d/img/logo?id=" + id + "&w=420&h=80", host.component());   // null: 404, no logo
            logoDone = true;
            host.repaint();
            if (seasons.length > 0) loadSeasonPosters();
            poster = Img.load("/d/img/case?id=" + id + "&w=200&h=290", host.component());   // poster in a Blu-ray case
            host.repaint();
            if (!closed) backdrop = Img.load("/d/img/backdrop?id=" + id, host.component());
            if (closed) free();
            host.repaint();
        } catch (IOException e) {
            status = Net.message(e);
            host.repaint();
        }
    }

    private synchronized void loadSeasonPosters() {
        int gen = ++seasonGeneration;
        for (int i = 0; i < SEASONS; i++) { Img.free(seasonPosters[i]); seasonPosters[i] = null; }
        host.repaint();
        for (int i = 0; i < SEASONS && gen == seasonGeneration && !closed; i++) {
            int k = firstSeason + i;
            if (k >= seasons.length) break;
            Image img = Img.load("/d/img/season?id=" + id + "&season=" + seasons[k] + "&w=" + SW + "&h=" + SH,
                                 host.component());
            if (gen == seasonGeneration && !closed) seasonPosters[i] = img; else Img.free(img);
            host.repaint();
        }
    }

    private void loadSeason() throws IOException {
        String[] ls = Proto.lines(Net.text("/d/episodes?id=" + id + "&season=" + seasons[seasonIdx]));
        String[][] rows = new String[ls.length][];
        epIdx = -1;
        for (int i = 0; i < ls.length; i++) {
            rows[i] = Proto.fields(ls[i]);
            if (epIdx < 0 && !"0".equals(rows[i][3])) epIdx = i;
        }
        eps = rows;
        if (epIdx < 0) epIdx = 0;
        first = Math.max(0, Math.min(epIdx, eps.length - CARDS));
        loadStills();
    }

    private synchronized void loadStills() {
        int gen = ++generation;
        for (int i = 0; i < CARDS; i++) { Img.free(stills[i]); stills[i] = null; }
        host.repaint();
        for (int i = 0; i < CARDS && gen == generation && !closed; i++) {
            int e = first + i;
            if (e >= eps.length) break;
            Image img = Img.load("/d/img/still?id=" + id + "&season=" + seasons[seasonIdx] + "&episode="
                    + eps[e][0] + "&w=" + CW + "&h=" + CH, host.component());
            if (gen == generation && !closed) stills[i] = img; else Img.free(img);
            host.repaint();
        }
    }

    private void free() {
        Img.free(backdrop);
        Img.free(poster);
        Img.free(logo);
        Img.free(seasonTop);
        Img.free(seasonBadges);
        backdrop = poster = logo = seasonTop = seasonBadges = null;
        for (int i = 0; i < CARDS; i++) { Img.free(stills[i]); stills[i] = null; }
        for (int i = 0; i < SEASONS; i++) { Img.free(seasonPosters[i]); seasonPosters[i] = null; }
    }

    public void key(int code) {
        if (code == 461 || code == 403) {
            closed = true;
            ++generation;
            ++seasonGeneration;
            free();
            host.show(wall);
            wall.reopen();
            return;
        }
        if (onEpisodes && code == 38) {   // back to the seasons row
            onEpisodes = false;
            Img.free(seasonTop);
            Img.free(seasonBadges);
            seasonTop = seasonBadges = null;
            ++generation;
            for (int i = 0; i < CARDS; i++) { Img.free(stills[i]); stills[i] = null; }
        } else if (!onEpisodes && (code == 37 || code == 39) && seasons.length > 0) {
            int next = seasonIdx + (code == 37 ? -1 : 1);
            if (next >= 0 && next < seasons.length) {
                seasonIdx = next;
                int f = Math.max(0, Math.min(firstSeason, seasonIdx));
                if (seasonIdx >= f + SEASONS) f = seasonIdx - SEASONS + 1;
                if (f != firstSeason) {
                    firstSeason = f;
                    Wall.background(new Runnable() {
                        public void run() { loadSeasonPosters(); }
                    });
                }
            }
        } else if (!onEpisodes && (code == 10 || code == 40) && seasons.length > 0) {   // open the season
            onEpisodes = true;
            eps = new String[0][];
            final String season = seasons[seasonIdx];
            Wall.background(new Runnable() {
                public void run() {
                    Image top = Img.load("/d/img/season?id=" + id + "&season=" + season + "&w=" + TOP_W + "&h=" + TOP_H,
                                         host.component());
                    Image bdg = Img.load("/d/img/badges?id=" + id + "&season=" + season + "&h=" + BADGE_H + "&w=680",
                                         host.component());   // null: 404, no format
                    if (onEpisodes && !closed) { Img.free(seasonTop); seasonTop = top; Img.free(seasonBadges); seasonBadges = bdg; }
                    else { Img.free(top); Img.free(bdg); }
                    host.repaint();
                    try { loadSeason(); } catch (IOException e) { status = Net.message(e); }
                    host.repaint();
                }
            });
        } else if (onEpisodes && code == 37 && epIdx > 0) {
            epIdx--;
            if (epIdx < first) { first = epIdx; reloadStills(); }
        } else if (onEpisodes && code == 39 && epIdx < eps.length - 1) {
            epIdx++;
            if (epIdx >= first + CARDS) { first = epIdx - CARDS + 1; reloadStills(); }
        } else if (onEpisodes && code == 10 && epIdx < eps.length && !"0".equals(eps[epIdx][3])) {
            play(eps[epIdx][3], Detail.parseInt(eps[epIdx][4]) > 60);
        }
        host.repaint();
    }

    private void reloadStills() {
        Wall.background(new Runnable() {
            public void run() { loadStills(); }
        });
    }

    private void play(final String epId, final boolean resume) {
        status = resume ? "Reanudando..." : "Iniciando...";
        Wall.background(new Runnable() {
            public void run() {
                try {
                    String[] f = Proto.fields(Net.text("/d/play?ep=" + epId + "&resume=" + (resume ? "1" : "0")).trim());
                    if ("busy".equals(f[0])) status = "Ya hay una reproduccion en marcha";
                    else if ("error".equals(f[0])) status = "No se pudo reproducir: " + (f.length > 1 ? f[1] : "");
                    else {
                        host.repaint();
                        Thread.sleep(60000);
                        if (!closed) status = "No se pudo reproducir (ver " + Net.BASE + "/log)";
                    }
                } catch (IOException e) {
                    status = Net.message(e);
                } catch (InterruptedException ignored) {
                }
                host.repaint();
            }
        });
    }

    public void paint(Graphics g, int w, int h) {
        g.setColor(Wall.BG);
        g.fillRect(0, 0, w, h);
        if (backdrop != null) g.drawImage(backdrop, 0, 0, w, h, null);
        if (onEpisodes && seasonTop != null) g.drawImage(seasonTop, CX, 60, null);   // the open season
        else if (poster != null) g.drawImage(poster, CX - 10, 50, null);   // case PNG: 10 px of shadow around the old slot
        g.setColor(Color.white);
        if (m.isEmpty()) {
            if (status != null) { g.setFont(new Font(null, Font.PLAIN, 24)); g.drawString(status, TX, 200); }
            return;
        }
        g.setFont(new Font(null, Font.BOLD, 32));
        if (logo != null) g.drawImage(logo, TX, 106 - logo.getHeight(null), null);   // sits on the facts line
        else if (logoDone) g.drawString(Wall.cut(g, str("title"), TW), TX, 95);
        g.setFont(new Font(null, Font.PLAIN, 20));
        StringBuffer facts = new StringBuffer();
        if (str("rating").length() > 0 && !"0.0".equals(str("rating"))) facts.append("Nota " + str("rating"));
        if (str("year").length() > 0) facts.append(facts.length() > 0 ? "  -  " : "").append(str("year"));
        facts.append(facts.length() > 0 ? "  -  " : "").append(seasons.length + (seasons.length == 1 ? " temporada" : " temporadas"));
        g.drawString(facts.toString(), TX, 130);
        Vector lines = Detail.wrap(g.getFontMetrics(), str("overview"), TW);
        int y = 168;
        for (int i = 0; i < lines.size() && i < 3; i++, y += 26) g.drawString((String) lines.elementAt(i), TX, y);
        y += 12;
        if (str("director").length() > 0) { label(g, "CREADORES", str("director"), y); y += 28; }
        if (str("cast").length() > 0) label(g, "REPARTO", str("cast"), y);

        if (!onEpisodes) paintSeasons(g);
        else paintEpisodes(g, w);
        g.setColor(Wall.DIM);
        g.setFont(new Font(null, Font.PLAIN, 14));
        g.drawString(onEpisodes ? "OK: reproducir   ARRIBA: temporadas   POP-UP/ROJO: volver"
                                : "OK: ver episodios   POP-UP/ROJO: volver", CX, h - 14);
        if (status != null) {
            g.setColor(Color.white);
            g.setFont(new Font(null, Font.PLAIN, 22));
            g.drawString(status, CX + 300, 437);
        }
    }

    private void paintSeasons(Graphics g) {
        g.setFont(new Font(null, Font.BOLD, 22));
        g.setColor(Color.white);
        g.drawString("Temporadas", CX, SY - 14);
        for (int i = 0; i < SEASONS; i++) {
            int k = firstSeason + i;
            if (k >= seasons.length) break;
            int x = CX + i * (SW + SGAP);
            if (k == seasonIdx) { g.setColor(Color.white); g.fillRect(x - 4, SY - 4, SW + 8, SH + 8); }
            if (seasonPosters[i] != null) g.drawImage(seasonPosters[i], x, SY, SW, SH, null);
            else { g.setColor(new Color(29, 29, 36)); g.fillRect(x, SY, SW, SH); }
            g.setColor(Color.white);
            g.setFont(new Font(null, Font.BOLD, 16));
            g.drawString("Temporada " + seasons[k], x, SY + SH + 24);
            if (k < counts.length) {
                g.setColor(Wall.DIM);
                g.setFont(new Font(null, Font.PLAIN, 14));
                g.drawString(counts[k] + ("1".equals(counts[k]) ? " episodio" : " episodios"), x, SY + SH + 44);
            }
        }
        if (seasons.length > SEASONS) {
            g.setColor(Wall.DIM);
            g.setFont(new Font(null, Font.PLAIN, 14));
            g.drawString((seasonIdx + 1) + " / " + seasons.length, CX + SEASONS * (SW + SGAP) - 80, SY - 14);
        }
    }

    private void paintEpisodes(Graphics g, int w) {
        g.setFont(new Font(null, Font.BOLD, 22));
        g.setColor(Color.white);
        g.drawString("Temporada " + seasons[seasonIdx], CX, 437);
        if (seasonBadges != null)   // the season's format, right of the title
            g.drawImage(seasonBadges, CX + 230, 437 - BADGE_H + 4, null);
        for (int i = 0; i < CARDS; i++) {
            int e = first + i;
            if (e >= eps.length) break;
            int x = CX + i * (CW + CGAP);
            boolean has = !"0".equals(eps[e][3]);
            if (e == epIdx) { g.setColor(Color.white); g.fillRect(x - 4, CY - 4, CW + 8, CH + 8); }
            if (stills[i] != null && has) g.drawImage(stills[i], x, CY, CW, CH, null);
            else { g.setColor(new Color(29, 29, 36)); g.fillRect(x, CY, CW, CH); }
            g.setColor(has ? Color.white : MUTED);
            g.setFont(new Font(null, Font.BOLD, 16));
            g.drawString(Wall.cut(g, "S" + seasons[seasonIdx] + ":E" + eps[e][0] + " - " + eps[e][1], CW), x, CY + CH + 24);
            g.setFont(new Font(null, Font.PLAIN, 14));
            g.setColor(has ? Wall.DIM : MUTED);
            g.drawString(has ? eps[e][2] : "No esta en el NAS", x, CY + CH + 44);
        }
        if (eps.length > CARDS) {
            g.setColor(Wall.DIM);
            g.setFont(new Font(null, Font.PLAIN, 14));
            g.drawString((epIdx + 1) + " / " + eps.length, w - 120, CY - 12);
        }
    }

    private void label(Graphics g, String name, String value, int y) {
        g.setFont(new Font(null, Font.BOLD, 16));
        g.drawString(name, TX, y);
        g.setFont(new Font(null, Font.PLAIN, 18));
        g.drawString(Wall.cut(g, value, TW - 140), TX + 140, y);
    }

    private String str(String k) {
        Object v = m.get(k);
        return v == null ? "" : (String) v;
    }
}

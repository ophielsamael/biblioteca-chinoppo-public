package org.biblio;

import java.awt.Color;
import java.awt.Font;
import java.awt.Graphics;
import java.awt.Image;
import java.io.IOException;

/** Side menu of folders + 7x2 poster wall. Only the visible page of posters is kept in memory. */
public class Wall implements Screen {
    static final int COLS = 7, ROWS = 2, PAGE = COLS * ROWS;
    static final int PW = 150, PH = 225, GAP = 14, X0 = 120, Y0 = 82, ROW_H = PH + 44;
    static final Color BG = new Color(7, 7, 10), SIDE = new Color(16, 16, 22), DIM = new Color(150, 150, 160);

    private final BibliotecaXlet host;
    private String[][] folders = new String[0][];   // id, name, count
    private Image[] icons = new Image[0], iconsSel = new Image[0];
    private int folderIdx, menuIdx;
    private boolean inMenu;
    private String[][] items = new String[0][];     // id, title, year
    private int sel;
    private int pageLoaded = -1;
    private final Image[] posters = new Image[PAGE];
    private int generation;
    private String message = "Cargando...";

    public Wall(BibliotecaXlet host) {
        this.host = host;
        background(new Runnable() {
            public void run() { start(); }
        });
    }

    static void background(Runnable r) {
        new Thread(r).start();
    }

    private void start() {
        try {
            String[] ls = Proto.lines(Net.text("/d/folders"));
            folders = new String[ls.length][];
            icons = new Image[ls.length];
            iconsSel = new Image[ls.length];
            for (int i = 0; i < ls.length; i++) {
                folders[i] = Proto.fields(ls[i]);
                icons[i] = Img.load("/d/img/icon?folder=" + Net.q(folders[i][0]) + "&sel=0", host.component());
                iconsSel[i] = Img.load("/d/img/icon?folder=" + Net.q(folders[i][0]) + "&sel=1", host.component());
            }
            java.util.Hashtable st = Proto.map(Net.text("/d/state"));
            int f = 0;
            for (int i = 0; i < folders.length; i++) {
                if (folders[i][0].equals(st.get("folder"))) f = i;
            }
            openFolder(f, (String) st.get("item"));
        } catch (IOException e) {
            message = Net.message(e);
            host.repaint();
        }
    }

    /** Called from Detail when going back. */
    public void reopen() {
        pageLoaded = -1;
        background(new Runnable() {
            public void run() { loadPage(); }
        });
    }

    private void openFolder(int f, String itemId) throws IOException {
        folderIdx = menuIdx = f;
        String[] ls = Proto.lines(Net.text("/d/items?folder=" + Net.q(folders[f][0])));
        String[][] its = new String[Math.max(0, ls.length - 1)][];
        sel = 0;
        for (int i = 1; i < ls.length; i++) {
            its[i - 1] = Proto.fields(ls[i]);
            if (its[i - 1][0].equals(itemId)) sel = i - 1;
        }
        items = its;
        message = its.length == 0 ? "Esta carpeta no tiene peliculas" : null;
        pageLoaded = -1;
        loadPage();
    }

    private synchronized void loadPage() {
        int page = sel / PAGE;
        if (page == pageLoaded) return;
        int gen = ++generation;
        for (int i = 0; i < PAGE; i++) {
            Img.free(posters[i]);
            posters[i] = null;
        }
        pageLoaded = page;
        host.repaint();
        for (int i = 0; i < PAGE && gen == generation; i++) {
            int idx = page * PAGE + i;
            if (idx >= items.length) break;
            Image img = Img.load("/d/img/poster?id=" + items[idx][0] + "&w=" + PW + "&h=" + PH, host.component());
            if (gen == generation) posters[i] = img; else Img.free(img);
            host.repaint();
        }
    }

    public void key(int code) {
        if (inMenu) {
            if (code == 38 && menuIdx > 0) menuIdx--;
            else if (code == 40 && menuIdx < folders.length - 1) menuIdx++;
            else if (code == 39 && items.length > 0) inMenu = false;
            else if (code == 10) {
                final int f = menuIdx;
                inMenu = false;
                background(new Runnable() {
                    public void run() {
                        try { openFolder(f, null); } catch (IOException e) { message = Net.message(e); host.repaint(); }
                    }
                });
            }
        } else {
            int col = sel % COLS;
            if (code == 37) { if (col == 0) { inMenu = true; menuIdx = folderIdx; } else sel--; }
            else if (code == 39 && col < COLS - 1 && sel + 1 < items.length) sel++;
            else if (code == 38 && sel >= COLS) sel -= COLS;
            else if (code == 40 && sel + COLS < items.length) sel += COLS;
            else if (code == 40 && (sel / COLS + 1) * COLS < items.length) sel = items.length - 1;
            else if ((code == 461 || code == 403)) { inMenu = true; menuIdx = folderIdx; }
            else if (code == 10 && items.length > 0) { openDetail(); return; }
            if (sel / PAGE != pageLoaded) {
                background(new Runnable() {
                    public void run() { loadPage(); }
                });
            }
        }
        host.repaint();
    }

    private void openDetail() {
        final String fid = folders[folderIdx][0], iid = items[sel][0];
        ++generation;  // stop a page load in progress
        for (int i = 0; i < PAGE; i++) { Img.free(posters[i]); posters[i] = null; }
        pageLoaded = -1;
        background(new Runnable() {
            public void run() {
                try { Net.text("/d/select?folder=" + Net.q(fid) + "&item=" + iid); } catch (IOException ignored) {}
            }
        });
        boolean series = items[sel].length > 3 && "series".equals(items[sel][3]);
        host.show(series ? (Screen) new SeriesDetail(host, this, iid) : new Detail(host, this, iid));
    }

    public void paint(Graphics g, int w, int h) {
        g.setColor(BG);
        g.fillRect(0, 0, w, h);
        g.setColor(SIDE);
        g.fillRect(0, 0, 96, h);
        int top = h / 2 - folders.length * 64 / 2;
        for (int i = 0; i < folders.length; i++) {
            boolean hi = inMenu ? i == menuIdx : i == folderIdx;
            Image ic = hi ? iconsSel[i] : icons[i];
            if (ic != null) g.drawImage(ic, 24, top + i * 64, 48, 48, null);
        }
        if (folders.length > 0) {
            // icons only on the side; the folder under the menu cursor is named in the title
            String title = inMenu ? folders[menuIdx][1] : folders[folderIdx][1];
            g.setColor(Color.white);
            g.setFont(new Font(null, Font.BOLD, 30));
            g.drawString(title, X0, 52);
            if (!inMenu) {
                g.setFont(new Font(null, Font.PLAIN, 18));
                g.setColor(DIM);
                g.drawString(items.length + " titulos", X0 + 20 + g.getFontMetrics(new Font(null, Font.BOLD, 30)).stringWidth(title), 52);
            }
        }
        int page = sel / PAGE;
        g.setFont(new Font(null, Font.PLAIN, 15));
        for (int i = 0; i < PAGE; i++) {
            int idx = page * PAGE + i;
            if (idx >= items.length) break;
            int x = X0 + (i % COLS) * (PW + GAP), y = Y0 + (i / COLS) * ROW_H;
            if (idx == sel && !inMenu) {
                g.setColor(Color.white);
                g.fillRect(x - 4, y - 4, PW + 8, PH + 8);
            }
            if (posters[i] != null) g.drawImage(posters[i], x, y, PW, PH, null);
            else { g.setColor(SIDE); g.fillRect(x, y, PW, PH); }
            g.setColor(idx == sel ? Color.white : DIM);
            g.drawString(cut(g, items[idx][1], PW), x, y + PH + 22);
        }
        if (message != null) {
            g.setColor(Color.white);
            g.setFont(new Font(null, Font.PLAIN, 24));
            g.drawString(message, X0, h / 2);
        }
        g.setColor(DIM);
        g.setFont(new Font(null, Font.PLAIN, 14));
        // ponytail: memory readout kept for the first device runs; remove once posters are proven stable
        g.drawString("libre " + Runtime.getRuntime().freeMemory() / 1024 + " KB", w - 150, h - 20);
        g.drawString("OK: abrir   POP-UP/ROJO: carpetas", X0, h - 20);
    }

    static String cut(Graphics g, String s, int width) {
        if (g.getFontMetrics().stringWidth(s) <= width) return s;
        while (s.length() > 1 && g.getFontMetrics().stringWidth(s + "...") > width) s = s.substring(0, s.length() - 1);
        return s + "...";
    }
}

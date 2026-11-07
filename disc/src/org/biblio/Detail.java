package org.biblio;

import java.awt.Color;
import java.awt.Font;
import java.awt.FontMetrics;
import java.awt.Graphics;
import java.awt.Image;
import java.io.IOException;
import java.util.Hashtable;
import java.util.Vector;

/** Movie page: backdrop, poster, data, overview and Play / Resume buttons. */
public class Detail implements Screen {
    // disc that slides half out of the case when the page opens. It also turned at first,
    // but this player can't show it smoothly (steps of 15° and 7.5° both looked jerky,
    // 2026-11-04), so it stays still: one frame, the right half (D/2 x D) from the service
    static final int D = 240, FRAMES = 1, SLIDE = 8;
    static final int RX = 60, RY = 280, RW = 380, RH = 370;   // area redrawn while sliding

    private int tx = 330, tw = 860, caseX = 70;               // text column moves right when there is a disc
    private Image disc, buffer;
    private int step;                                         // slide-out step

    private final BibliotecaXlet host;
    private final Wall wall;
    private final String id;
    private Hashtable m = new Hashtable();
    private Image backdrop, poster, logo, badges;   // badges: the format row under the facts line
    private static final Font BUTTON_FONT = new Font(null, Font.BOLD, 20);
    private static final int BADGE_H = 30, BADGE_W = 790;   // 790: the text column's width when there is a disc
    private boolean logoDone;   // title text only once we know there is no logo (no flicker)
    private volatile boolean ready;   // until the whole page is loaded the wall stays on screen: it appears at once
    private String[] buttons = new String[0];
    private int btn;
    private String status = "Cargando...";
    private boolean closed;

    public Detail(BibliotecaXlet host, Wall wall, String id) {
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
            if ("1".equals(m.get("hascase"))) {   // a disc will slide out of the case: text column right away,
                tx = 460;                          // not when the disc image arrives (it moved under the eyes)
                tw = 790;
            }
            int resume = parseInt((String) m.get("resume"));
            buttons = resume > 60 ? new String[] {"Reanudar (" + hhmm(resume) + ")", "Reproducir"}
                                  : new String[] {"Reproducir"};
            status = null;
            // everything first (all cached on the homelab: a few tenths of a second), then one paint:
            // pieces popping in one by one showed (2026-11-05)
            backdrop = Img.load("/d/img/backdrop?id=" + id, host.component());
            logo = Img.load("/d/img/logo?id=" + id + "&w=500&h=140", host.component());   // null: 404, no logo
            logoDone = true;
            poster = Img.load("/d/img/case?id=" + id + "&w=240&h=350", host.component());   // poster in a Blu-ray case
            disc = Img.load("/d/img/disc?id=" + id + "&size=" + D + "&frames=" + FRAMES, host.component());   // null: no case
            if (disc != null) {   // the disc comes out on the right: text column moves over
                tx = 460;
                tw = 790;
            }
            badges = Img.load("/d/img/badges?id=" + id + "&h=" + BADGE_H + "&w=" + BADGE_W, host.component());   // null: 404
            ready = true;
            if (closed) free();
            host.repaint();
            if (disc != null && !closed) animate();
        } catch (IOException e) {
            status = Net.message(e);
            ready = true;
            host.repaint();
        }
    }

    private void free() {
        Img.free(backdrop);
        Img.free(poster);
        Img.free(logo);
        Img.free(badges);
        Img.free(disc);
        Img.free(buffer);
        backdrop = poster = logo = badges = disc = buffer = null;
    }

    public void key(int code) {
        if (code == 461 || code == 403 || (code == 37 && btn == 0)) {
            closed = true;
            free();
            host.show(wall);
            wall.reopen();
            return;
        }
        if (code == 37 && btn > 0) btn--;
        else if (code == 39 && btn < buttons.length - 1) btn++;
        else if (code == 10 && buttons.length > 0) play(buttons.length == 2 && btn == 0);
        host.repaint();
    }

    private void play(final boolean resume) {
        status = "Iniciando...";
        Wall.background(new Runnable() {
            public void run() {
                try {
                    String[] f = Proto.fields(Net.text("/d/play?id=" + id + "&resume=" + (resume ? "1" : "0")).trim());
                    if ("busy".equals(f[0])) status = "Ya hay una reproduccion en marcha";
                    else if ("error".equals(f[0])) status = "No se pudo reproducir: " + (f.length > 1 ? f[1] : "");
                    else {
                        // "ok": the service closes this disc; if we are still here after 60 s, it failed
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

    /** Disc and case composed off-screen, then copied once: no flicker between layers. */
    private void paintDisc(Graphics g, int w, int h) {
        Image d = disc, p = poster;
        if (d == null) return;
        if (buffer == null) buffer = host.component().createImage(RW, RH);
        if (buffer == null) return;
        Graphics b = buffer.getGraphics();
        b.translate(-RX, -RY);
        b.setColor(Wall.BG);
        b.fillRect(RX, RY, RW, RH);
        if (backdrop != null) b.drawImage(backdrop, 0, 0, w, h, null);
        int hidden = caseX + 120 - D / 2, out = caseX + 230 - D / 2;   // centred behind the case -> half out, right
        int x = hidden + (out - hidden) * step / SLIDE, y = 290 + 175 - D / 2;
        b.drawImage(d, x + D / 2, y, null);   // right half only: the left one stays behind the case
        if (p != null) b.drawImage(p, caseX, 290, null);
        b.dispose();
        g.drawImage(buffer, RX, RY, null);
    }

    /** Slide out: 8 steps of 50 ms, then the disc stays put (no thread left running). */
    private void animate() {
        Wall.background(new Runnable() {
            public void run() {
                try {
                    while (!closed && disc != null && step < SLIDE) {
                        step++;
                        host.repaint(RX, RY, RW, RH);
                        Thread.sleep(50);
                    }
                } catch (InterruptedException ignored) {
                }
            }
        });
    }

    public void paint(Graphics g, int w, int h) {
        // Draw nothing until the page is loaded: update() doesn't clear, so the wall's last frame stays
        // on screen instead of a black one (the wall freed its posters, it can't be painted again here)
        if (!ready) return;
        g.setColor(Wall.BG);
        g.fillRect(0, 0, w, h);
        if (backdrop != null) g.drawImage(backdrop, 0, 0, w, h, null);
        if (disc != null) paintDisc(g, w, h);
        else if (poster != null) g.drawImage(poster, caseX, 290, null);   // case PNG: 10 px of shadow around the old 220x330 slot
        g.setColor(Color.white);
        if (m.isEmpty()) {
            if (status != null) { g.setFont(new Font(null, Font.PLAIN, 24)); g.drawString(status, tx, 360); }
            return;
        }
        g.setFont(new Font(null, Font.BOLD, 32));
        if (logo != null) g.drawImage(logo, tx, 342 - logo.getHeight(null), null);   // sits on the facts line
        else if (logoDone) g.drawString(Wall.cut(g, str("title"), tw), tx, 330);
        g.setFont(new Font(null, Font.PLAIN, 20));
        StringBuffer facts = new StringBuffer();
        add(facts, str("rating").length() > 0 && !"0.0".equals(str("rating")) ? "Nota " + str("rating") : "");
        add(facts, str("certification").length() > 0 ? "+" + str("certification") : "");
        add(facts, str("year"));
        add(facts, parseInt(str("runtime")) > 0 ? str("runtime") + " min" : "");
        g.drawString(facts.toString(), tx, 366);
        int y = 408, maxLines = 5;
        if (badges != null || str("badges").length() > 0) {   // their own row, kept from the start
            if (badges != null) g.drawImage(badges, tx, 380, null);
            y += 40;
            maxLines = 4;
        }
        Vector lines = wrap(g.getFontMetrics(), str("overview"), tw);
        for (int i = 0; i < lines.size() && i < maxLines; i++, y += 26) g.drawString((String) lines.elementAt(i), tx, y);
        y += 16;
        y = label(g, "CATEGORIAS", str("genres"), y);
        y = label(g, "DIRECTOR", str("director"), y);
        label(g, "REPARTO", str("cast"), y);
        int bx = tx;
        g.setFont(BUTTON_FONT);
        for (int i = 0; i < buttons.length; i++) {
            int bw = g.getFontMetrics().stringWidth(buttons[i]) + 44;
            g.setColor(i == btn ? Color.white : new Color(40, 40, 50));
            g.fillRect(bx, 640, bw, 44);
            g.setColor(i == btn ? Color.black : Color.white);
            g.drawString(buttons[i], bx + 22, 669);
            bx += bw + 16;
        }
        g.setColor(Wall.DIM);
        g.setFont(new Font(null, Font.PLAIN, 14));
        g.drawString("POP-UP/ROJO: volver", w - 200, h - 14);
        if (status != null) {
            g.setColor(Color.white);
            g.setFont(new Font(null, Font.PLAIN, 22));
            g.drawString(status, bx + 10, 669);
        }
    }

    private int label(Graphics g, String name, String value, int y) {
        if (value.length() == 0) return y;
        g.setFont(new Font(null, Font.BOLD, 16));
        g.drawString(name, tx, y);
        g.setFont(new Font(null, Font.PLAIN, 18));
        g.drawString(Wall.cut(g, value, tw - 140), tx + 140, y);
        return y + 28;
    }

    private String str(String k) {
        Object v = m.get(k);
        return v == null ? "" : (String) v;
    }

    private static void add(StringBuffer b, String s) {
        if (s.length() == 0) return;
        if (b.length() > 0) b.append("  -  ");
        b.append(s);
    }

    static int parseInt(String s) {
        try { return Integer.parseInt(s.trim()); } catch (Exception e) { return 0; }
    }

    static String hhmm(int secs) {
        int hh = secs / 3600, mm = secs % 3600 / 60;
        return (hh < 10 ? "0" : "") + hh + ":" + (mm < 10 ? "0" : "") + mm;
    }

    static Vector wrap(FontMetrics fm, String text, int width) {
        Vector out = new Vector();
        String[] words = Proto.splitOn(text, ' ');
        StringBuffer cur = new StringBuffer();
        for (int i = 0; i < words.length; i++) {
            String next = cur.length() == 0 ? words[i] : cur + " " + words[i];
            if (fm.stringWidth(next) > width && cur.length() > 0) {
                out.addElement(cur.toString());
                cur = new StringBuffer(words[i]);
            } else {
                cur = new StringBuffer(next);
            }
        }
        if (cur.length() > 0) out.addElement(cur.toString());
        return out;
    }
}

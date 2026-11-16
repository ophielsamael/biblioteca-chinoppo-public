package org.biblio;

import java.awt.Color;
import java.awt.Font;
import java.awt.FontMetrics;
import java.awt.Graphics;

/**
 * The "Cargando biblioteca" picture shown from the disc's first paint until the first posters are
 * there: the same look as the loading video the stick plays (five drawn poster cards lighting up in
 * a wave, the text with its dots). Only primitives, no images: the Java heap here is ~1 MB.
 * Measured 2026-11-16: the screen stayed black ~4 s after the disc opened; this fills what Java can.
 */
final class LoadingArt {
    static final int PW = 150, PH = 225, GAP = 36, N = 5;
    static final String TEXT = "Cargando biblioteca";
    // sky top / bottom, moon, hills (r,g,b): five invented posters, as in tools/loaders/make_loaders.py
    static final int[][] TOP = {{44, 54, 82}, {74, 56, 92}, {120, 48, 34}, {70, 80, 48}, {30, 78, 74}};
    static final int[][] BOT = {{96, 108, 140}, {150, 122, 150}, {190, 110, 80}, {140, 150, 96}, {80, 150, 140}};
    static final int[] MOON_X = {60, 22, 70, 98, 50}, MOON_Y = {40, 30, 70, 72, 60}, MOON_R = {26, 20, 17, 17, 24};

    private LoadingArt() {}

    /** Left edge, top and size of the animated block (for partial repaints). */
    static int x0(int w) { return (w - (N * PW + (N - 1) * GAP)) / 2; }

    static void paint(Graphics g, int w, int h, long ms) {
        g.setColor(Wall.BG);
        g.fillRect(0, 0, w, h);
        int x0 = x0(w);
        for (int i = 0; i < N; i++) {
            // a wave: each card rises and lights up in turn (2 s a cycle)
            double k = 0.5 + 0.5 * Math.sin(2 * Math.PI * (ms / 2000.0 - i / 5.0));
            int bright = (int) (38 + 62 * k);
            card(g, x0 + i * (PW + GAP), 330 - (int) (22 * k), i, bright);
        }
        g.setFont(new Font(null, Font.BOLD, 44));
        FontMetrics fm = g.getFontMetrics();
        int dots = (int) (ms / 500 % 4);
        String dotted = TEXT;
        for (int d = 0; d < dots; d++) dotted += ".";
        g.setColor(new Color(225, 225, 230));
        g.drawString(dotted, (w - fm.stringWidth(TEXT + "...")) / 2, 700);
    }

    private static Color mix(int[] c, int bright) {
        return new Color(c[0] * bright / 100, c[1] * bright / 100, c[2] * bright / 100);
    }

    private static void card(Graphics g, int x, int y, int i, int bright) {
        int[] top = TOP[i], bot = BOT[i];
        for (int row = 0; row < PH; row += 3) {
            int[] c = new int[3];
            for (int j = 0; j < 3; j++) c[j] = top[j] + (bot[j] - top[j]) * row / PH;
            g.setColor(mix(c, bright));
            g.fillRect(x, y + row, PW, 3);
        }
        g.setColor(mix(new int[] {250, 240, 210}, bright));
        g.fillOval(x + MOON_X[i] - MOON_R[i], y + MOON_Y[i] - MOON_R[i], 2 * MOON_R[i], 2 * MOON_R[i]);
        int[] ground = {top[0] / 3, top[1] / 3, top[2] / 3};
        g.setColor(mix(ground, bright));
        int[] xs = {x, x, x + 38, x + 75, x + 112, x + PW, x + PW};
        int[] ys = {y + PH, y + 158 + i * 5, y + 140, y + 160 - i * 4, y + 138, y + 150, y + PH};
        g.fillPolygon(xs, ys, xs.length);
        g.setColor(mix(new int[] {235, 235, 240}, bright));
        g.fillRect(x + 14, y + PH - 34, PW - 28, 8);
        g.setColor(mix(new int[] {170, 170, 180}, bright));
        g.fillRect(x + 34, y + PH - 20, PW - 68, 4);
    }
}

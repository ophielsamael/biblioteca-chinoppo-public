package org.biblio;

import java.awt.BorderLayout;
import java.awt.Container;
import java.awt.Graphics;
import java.awt.event.KeyEvent;
import java.awt.event.KeyListener;
import javax.tv.xlet.Xlet;
import javax.tv.xlet.XletContext;
import org.havi.ui.HScene;
import org.havi.ui.HSceneFactory;

/** Lifecycle, focus and key routing; the active Screen draws everything. */
public class BibliotecaXlet implements Xlet, KeyListener {
    private HScene scene;
    private Canvas canvas;
    private Screen screen;

    class Canvas extends Container {
        public void paint(Graphics g) {
            Screen s = screen;
            if (s != null) s.paint(g, getWidth(), getHeight());
        }

        public void update(Graphics g) {
            paint(g);
        }
    }

    public void initXlet(XletContext context) {
        scene = HSceneFactory.getInstance().getDefaultHScene();
        canvas = new Canvas();
        canvas.setSize(scene.getWidth(), scene.getHeight());
        scene.add(canvas, BorderLayout.CENTER);
        scene.addKeyListener(this);
        scene.validate();
    }

    public void startXlet() {
        canvas.setVisible(true);
        scene.setVisible(true);
        scene.requestFocus();
        show(firstScreen());
    }

    protected Screen firstScreen() {
        return new Wall(this);
    }

    /** Component for MediaTracker when decoding images. */
    public java.awt.Component component() {
        return canvas;
    }

    public void pauseXlet() {
        canvas.setVisible(false);
    }

    public void destroyXlet(boolean unconditional) {
        scene.removeKeyListener(this);
        scene.remove(canvas);
        HSceneFactory.getInstance().dispose(scene);
        scene = null;
    }

    public void show(Screen s) {
        screen = s;
        repaint();
    }

    public void repaint() {
        if (canvas != null) canvas.repaint();
    }

    /** Only part of the screen (animations): the Screen still paints, clipped to it. */
    public void repaint(int x, int y, int w, int h) {
        if (canvas != null) canvas.repaint(x, y, w, h);
    }

    public void keyPressed(KeyEvent e) {
        Screen s = screen;
        if (s != null) s.key(e.getKeyCode());
    }

    public void keyReleased(KeyEvent e) {}

    public void keyTyped(KeyEvent e) {}
}

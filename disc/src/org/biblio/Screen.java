package org.biblio;

import java.awt.Graphics;

public interface Screen {
    void paint(Graphics g, int w, int h);

    void key(int code);
}

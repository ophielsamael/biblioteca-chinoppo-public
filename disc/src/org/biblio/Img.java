package org.biblio;

import java.awt.Component;
import java.awt.Image;
import java.awt.MediaTracker;
import java.awt.Toolkit;

/** JPEG from the service, decoded synchronously. Null on any failure (incl. out of memory). */
final class Img {
    private Img() {}

    static Image load(String path, Component c) {
        try {
            Image img = Toolkit.getDefaultToolkit().createImage(Net.bytes(path));
            MediaTracker mt = new MediaTracker(c);
            mt.addImage(img, 0);
            mt.waitForAll();
            if (mt.isErrorAny()) {
                img.flush();
                return null;
            }
            return img;
        } catch (Throwable t) { // OutOfMemoryError included: the Chinoppo has ~1 MB free
            return null;
        }
    }

    static void free(Image img) {
        if (img != null) img.flush();
    }
}

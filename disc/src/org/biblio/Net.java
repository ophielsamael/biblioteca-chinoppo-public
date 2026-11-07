package org.biblio;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.net.URL;

/** HTTP GET to the homelab service. Needs "Acceso red BD-Live" = Activado on the Chinoppo. */
public final class Net {
    /** EDIT THIS: the address of the server running the Biblioteca service (port 8095). */
    public static final String BASE = "http://192.168.1.201:8095";

    private Net() {}

    public static byte[] bytes(String path) throws IOException {
        InputStream in = null;
        try {
            in = new URL(BASE + path).openStream();
            ByteArrayOutputStream out = new ByteArrayOutputStream();
            byte[] buf = new byte[8192];
            int n;
            while ((n = in.read(buf)) > 0) out.write(buf, 0, n);
            return out.toByteArray();
        } catch (SecurityException e) {
            throw new IOException("BDLIVE");
        } finally {
            if (in != null) try { in.close(); } catch (IOException ignored) {}
        }
    }

    public static String text(String path) throws IOException {
        return new String(bytes(path), "UTF-8");
    }

    /** Encode a query value (Java 1.3 URLEncoder has no charset parameter). */
    public static String q(String s) {
        StringBuffer b = new StringBuffer();
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            if ((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') || c == '-' || c == '_') {
                b.append(c);
            } else {
                b.append('%').append(Integer.toHexString(0x100 | c).substring(1).toUpperCase());
            }
        }
        return b.toString();
    }

    public static String message(IOException e) {
        if ("BDLIVE".equals(e.getMessage())) {
            return "Activa BD-Live: Setup > Red > Acceso red BD-Live = Activado";
        }
        return "Sin conexion con el servidor (" + BASE + ")";
    }
}

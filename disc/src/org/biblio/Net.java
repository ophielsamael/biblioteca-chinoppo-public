package org.biblio;

import java.io.ByteArrayOutputStream;
import java.io.FileInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.net.URL;

/** HTTP GET to the homelab service. Needs "Acceso red BD-Live" = Activado on the Chinoppo. */
public final class Net {
    /** The service address, from BIBLIO.TXT on this disc ("BIBLIO_URL=http://ip:8095"). The service
     *  writes it into the ISO when you download the USB files from its web page, so the same disc
     *  works for everyone. The file is padded past 2 KB so UDF keeps it out of the file entry. */
    public static final String BASE = load();
    static String where = "?";

    private Net() {}

    private static String load() {
        String root = System.getProperty("bluray.vfs.root");
        String[] paths = { root + "/BIBLIO.TXT", root + "/BDMV/JAR/BIBLIO.TXT", "BIBLIO.TXT" };
        for (int i = 0; i < paths.length; i++) {
            FileInputStream in = null;
            try {
                in = new FileInputStream(paths[i]);
                byte[] buf = new byte[256];
                int n = in.read(buf);
                String s = n > 0 ? new String(buf, 0, n, "US-ASCII") : "";
                int k = s.indexOf("BIBLIO_URL=");
                if (k >= 0) {
                    String url = s.substring(k + 11).trim();
                    int nl = url.indexOf('\n');
                    if (nl >= 0) url = url.substring(0, nl).trim();
                    if (url.startsWith("http://") && url.indexOf("0.0.0.0") < 0) {
                        where = paths[i];
                        return url;
                    }
                    where = "sin configurar";
                    return "";
                }
            } catch (Throwable ignored) {
                // next candidate
            } finally {
                if (in != null) try { in.close(); } catch (IOException ignored) {}
            }
        }
        where = "no encontrado (" + root + ")";
        return "";
    }

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
        if (BASE.length() == 0) {
            return "Disco sin servidor (" + where + "): descargalo desde la pagina :8095";
        }
        return "Sin conexion con el servidor (" + BASE + ")";
    }
}

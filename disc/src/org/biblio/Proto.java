package org.biblio;

import java.util.Hashtable;
import java.util.Vector;

/** Text protocol from biblio/proto.py: lines split by \n, fields by \t (Java 1.3: no split()). */
public final class Proto {
    private Proto() {}

    static String[] splitOn(String s, char sep) {
        Vector parts = new Vector();
        int start = 0;
        for (int i = s.indexOf(sep); i >= 0; i = s.indexOf(sep, start)) {
            parts.addElement(s.substring(start, i));
            start = i + 1;
        }
        parts.addElement(s.substring(start));
        String[] out = new String[parts.size()];
        parts.copyInto(out);
        return out;
    }

    public static String[] lines(String body) {
        String[] all = splitOn(body, '\n');
        int n = all.length;
        while (n > 0 && all[n - 1].length() == 0) n--;
        String[] out = new String[n];
        System.arraycopy(all, 0, out, 0, n);
        return out;
    }

    public static String[] fields(String line) {
        return splitOn(line, '\t');
    }

    public static Hashtable map(String body) {
        Hashtable m = new Hashtable();
        String[] ls = lines(body);
        for (int i = 0; i < ls.length; i++) {
            int t = ls[i].indexOf('\t');
            if (t > 0) m.put(ls[i].substring(0, t), ls[i].substring(t + 1));
        }
        return m;
    }
}

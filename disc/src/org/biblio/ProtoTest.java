package org.biblio;

// Host-side check (JDK 8, -source 1.3): java -ea -cp out org.biblio.ProtoTest
public class ProtoTest {
    static void check(boolean ok, String what) {
        if (!ok) throw new RuntimeException("FAIL: " + what);
    }

    public static void main(String[] args) {
        String[] f = Proto.fields("1\t\tÑandú");
        check(f.length == 3 && f[0].equals("1") && f[1].equals("") && f[2].equals("Ñandú"), "fields keeps empty");
        String[] l = Proto.lines("2\na\tb\n");
        check(l.length == 2 && l[0].equals("2") && l[1].equals("a\tb"), "lines drops trailing empty");
        check(Proto.lines("").length == 0, "empty body");
        java.util.Hashtable m = Proto.map("title\tCoda\nyear\t2021\ndirector\t");
        check("2021".equals(m.get("year")) && "".equals(m.get("director")), "map");
        System.out.println("OK");
    }
}

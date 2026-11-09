package com.example.photoviewer;

import java.util.Locale;

final class Formats {
    private Formats() {
    }

    static String bytes(long n) {
        if (n < 1024) {
            return n + "B";
        }
        if (n < 1024 * 1024) {
            return String.format(Locale.US, "%.1fKB", n / 1024.0);
        }
        return String.format(Locale.US, "%.2fMB", n / (1024.0 * 1024.0));
    }
}

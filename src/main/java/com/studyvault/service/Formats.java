package com.studyvault.service;

/** Small display helpers shared by the view models. */
public final class Formats {

    private Formats() {
    }

    public static String humanSize(long bytes) {
        if (bytes <= 0) {
            return "0 KB";
        }
        if (bytes < 1024 * 1024) {
            return Math.max(1, Math.round(bytes / 1024.0)) + " KB";
        }
        double megabytes = bytes / (1024.0 * 1024.0);
        return megabytes < 10
                ? String.format("%.1f MB", megabytes)
                : Math.round(megabytes) + " MB";
    }
}

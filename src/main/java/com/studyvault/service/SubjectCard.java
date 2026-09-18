package com.studyvault.service;

import java.time.LocalDate;

/**
 * What the home page renders for one subject. A plain class with getters
 * (rather than a record) so Thymeleaf property access works on every version.
 */
public class SubjectCard {

    private final Long id;
    private final String name;
    private final LocalDate examDate;
    private final long fileCount;
    private final long totalBytes;
    private final Long daysUntilExam;

    public SubjectCard(Long id, String name, LocalDate examDate,
                       long fileCount, long totalBytes, Long daysUntilExam) {
        this.id = id;
        this.name = name;
        this.examDate = examDate;
        this.fileCount = fileCount;
        this.totalBytes = totalBytes;
        this.daysUntilExam = daysUntilExam;
    }

    public Long getId() {
        return id;
    }

    public String getName() {
        return name;
    }

    public LocalDate getExamDate() {
        return examDate;
    }

    public long getFileCount() {
        return fileCount;
    }

    public long getTotalBytes() {
        return totalBytes;
    }

    public String getSizeLabel() {
        return Formats.humanSize(totalBytes);
    }

    public String getFileCountLabel() {
        return fileCount == 1 ? "1 file" : fileCount + " files";
    }

    /** Null when no exam date is set, negative once the exam has passed. */
    public Long getDaysUntilExam() {
        return daysUntilExam;
    }

    public boolean isExamUpcoming() {
        return daysUntilExam != null && daysUntilExam >= 0;
    }

    /** Drives the colour of the countdown chip. */
    public String getUrgency() {
        return urgency(daysUntilExam);
    }

    public String getCountdownLabel() {
        return countdownLabel(daysUntilExam);
    }

    public static String urgency(Long days) {
        if (days == null || days < 0) {
            return "none";
        }
        if (days <= 3) {
            return "critical";
        }
        return days <= 10 ? "soon" : "planned";
    }

    public static String countdownLabel(Long days) {
        if (days == null) {
            return null;
        }
        if (days < 0) {
            return "Exam done";
        }
        if (days == 0) {
            return "Exam today";
        }
        return days == 1 ? "1 day left" : days + " days left";
    }
}

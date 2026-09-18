package com.studyvault.service;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;

/**
 * One search hit. The snippet is split into three plain strings so the template
 * can highlight the match with th:text, which escapes everything. Nothing is
 * ever rendered as raw HTML.
 */
public class SearchResult {

    private static final DateTimeFormatter STAMP = DateTimeFormatter.ofPattern("d MMM yyyy");

    private final String publicId;
    private final String fileName;
    private final String extension;
    private final Long subjectId;
    private final String subjectName;
    private final LocalDateTime uploadedAt;
    private final String snippetBefore;
    private final String snippetMatch;
    private final String snippetAfter;

    public SearchResult(String publicId, String fileName, String extension,
                        Long subjectId, String subjectName, LocalDateTime uploadedAt,
                        String snippetBefore, String snippetMatch, String snippetAfter) {
        this.publicId = publicId;
        this.fileName = fileName;
        this.extension = extension;
        this.subjectId = subjectId;
        this.subjectName = subjectName;
        this.uploadedAt = uploadedAt;
        this.snippetBefore = snippetBefore;
        this.snippetMatch = snippetMatch;
        this.snippetAfter = snippetAfter;
    }

    public String getPublicId() {
        return publicId;
    }

    public String getFileName() {
        return fileName;
    }

    public String getExtension() {
        return extension;
    }

    public Long getSubjectId() {
        return subjectId;
    }

    public String getSubjectName() {
        return subjectName;
    }

    public LocalDateTime getUploadedAt() {
        return uploadedAt;
    }

    public String getUploadedAtLabel() {
        return uploadedAt.format(STAMP);
    }

    public String getSnippetBefore() {
        return snippetBefore;
    }

    public String getSnippetMatch() {
        return snippetMatch;
    }

    public String getSnippetAfter() {
        return snippetAfter;
    }

    /** False when only the filename matched, so the template can say so. */
    public boolean isMatchedInsideDocument() {
        return snippetMatch != null && !snippetMatch.isEmpty();
    }
}

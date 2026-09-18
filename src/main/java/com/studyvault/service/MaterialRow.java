package com.studyvault.service;

import com.studyvault.repository.MaterialView;

import java.time.format.DateTimeFormatter;

/**
 * One row of the file list, with everything already formatted. Built from the
 * projection, so the file bytes are still never loaded to draw this screen.
 */
public class MaterialRow {

    private static final DateTimeFormatter STAMP = DateTimeFormatter.ofPattern("d MMM yyyy, HH:mm");

    private final String publicId;
    private final String fileName;
    private final String extension;
    private final String sizeLabel;
    private final String uploadedBy;
    private final String uploadedAtLabel;
    private final long downloadCount;

    public MaterialRow(MaterialView view) {
        this.publicId = view.getPublicId();
        this.fileName = view.getOriginalFileName();
        this.extension = view.getExtension();
        this.sizeLabel = Formats.humanSize(view.getSizeBytes());
        this.uploadedBy = view.getUploadedBy();
        this.uploadedAtLabel = view.getUploadedAt().format(STAMP);
        this.downloadCount = view.getDownloadCount();
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

    public String getSizeLabel() {
        return sizeLabel;
    }

    public String getUploadedBy() {
        return uploadedBy;
    }

    public String getUploadedAtLabel() {
        return uploadedAtLabel;
    }

    public long getDownloadCount() {
        return downloadCount;
    }

    public boolean isPreviewable() {
        return "pdf".equals(extension);
    }
}

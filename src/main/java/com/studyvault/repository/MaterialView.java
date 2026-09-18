package com.studyvault.repository;

import java.time.LocalDateTime;

/**
 * Closed projection of a material. Because it lists no getter for {@code data}
 * or {@code contentText}, Spring Data generates a SELECT that leaves both
 * columns out entirely.
 */
public interface MaterialView {

    String getPublicId();

    String getOriginalFileName();

    String getContentType();

    String getExtension();

    long getSizeBytes();

    String getUploadedBy();

    LocalDateTime getUploadedAt();

    long getDownloadCount();
}

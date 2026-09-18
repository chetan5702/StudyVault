package com.studyvault.repository;

import java.time.LocalDateTime;

/** One search match, including the extracted text used to build a snippet. */
public interface SearchHit {

    String getPublicId();

    String getFileName();

    String getExtension();

    Long getSubjectId();

    String getSubjectName();

    LocalDateTime getUploadedAt();

    String getContentText();
}

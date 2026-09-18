package com.studyvault.repository;

import java.time.LocalDate;

/**
 * Read-only view of a subject plus its file statistics. Spring Data builds this
 * from the aliases in the query, so the home page never touches file bytes.
 */
public interface SubjectSummary {

    Long getId();

    String getName();

    LocalDate getExamDate();

    long getFileCount();

    long getTotalBytes();
}

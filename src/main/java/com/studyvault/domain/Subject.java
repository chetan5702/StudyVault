package com.studyvault.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

import java.time.LocalDate;
import java.time.LocalDateTime;

/**
 * A subject, e.g. "Design and Analysis of Algorithms".
 *
 * There is deliberately NO {@code @OneToMany List<Material>} here. In the old
 * version, calling {@code subject.getFiles().size()} from a Thymeleaf template
 * loaded every row of ppt_files for that subject, and because the file bytes
 * lived in the same row, rendering the home page pulled every uploaded file
 * into memory. Counts now come from a projection query instead.
 */
@Entity
@Table(name = "subjects")
public class Subject {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, unique = true, length = 120)
    private String name;

    /** Optional. Drives the countdown and the ordering on the home page. */
    @Column(name = "exam_date")
    private LocalDate examDate;

    // This is intentionally nullable at the database level. Existing StudyVault
    // databases predate this column; Hibernate can then add it without rejecting
    // already-stored subjects. New subjects still receive a timestamp below.
    @Column(name = "created_at")
    private LocalDateTime createdAt = LocalDateTime.now();

    protected Subject() {
        // required by JPA
    }

    public Subject(String name) {
        this.name = name;
    }

    public Long getId() {
        return id;
    }

    public String getName() {
        return name;
    }

    public void setName(String name) {
        this.name = name;
    }

    public LocalDate getExamDate() {
        return examDate;
    }

    public void setExamDate(LocalDate examDate) {
        this.examDate = examDate;
    }

    public LocalDateTime getCreatedAt() {
        return createdAt;
    }

    public void setCreatedAt(LocalDateTime createdAt) {
        this.createdAt = createdAt;
    }
}

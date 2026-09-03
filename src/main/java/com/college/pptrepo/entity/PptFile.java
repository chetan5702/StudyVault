package com.college.pptrepo.entity;

import jakarta.persistence.*;
import java.time.LocalDateTime;

/**
 * Represents one uploaded file (PPT or PDF).
 *
 * The actual file bytes are stored INSIDE the database (as a BLOB),
 * not on the server's disk. This matters because free hosting tiers
 * (like Render's free web service) wipe the local disk on every
 * restart - but the database survives. Storing the bytes here is
 * like keeping the book inside the library building itself, instead
 * of in a shed out back that sometimes gets cleared out.
 */
@Entity
@Table(name = "ppt_files")
public class PptFile {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false)
    private String originalFileName;

    @Column(nullable = false)
    private String contentType; // e.g. "application/pdf", needed so downloads open correctly

    @Lob
    @Column(nullable = false)
    private byte[] data; // the actual file content, stored in the database

    @Column(nullable = false)
    private LocalDateTime uploadedAt;

    @ManyToOne
    @JoinColumn(name = "subject_id", nullable = false)
    private Subject subject;

    public PptFile() {
    }

    public PptFile(String originalFileName, String contentType, byte[] data, Subject subject) {
        this.originalFileName = originalFileName;
        this.contentType = contentType;
        this.data = data;
        this.subject = subject;
        this.uploadedAt = LocalDateTime.now();
    }

    public Long getId() {
        return id;
    }

    public void setId(Long id) {
        this.id = id;
    }

    public String getOriginalFileName() {
        return originalFileName;
    }

    public void setOriginalFileName(String originalFileName) {
        this.originalFileName = originalFileName;
    }

    public String getContentType() {
        return contentType;
    }

    public void setContentType(String contentType) {
        this.contentType = contentType;
    }

    public byte[] getData() {
        return data;
    }

    public void setData(byte[] data) {
        this.data = data;
    }

    public LocalDateTime getUploadedAt() {
        return uploadedAt;
    }

    public void setUploadedAt(LocalDateTime uploadedAt) {
        this.uploadedAt = uploadedAt;
    }

    public Subject getSubject() {
        return subject;
    }

    public void setSubject(Subject subject) {
        this.subject = subject;
    }
}

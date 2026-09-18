package com.studyvault.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Index;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.time.LocalDateTime;
import java.util.UUID;

/**
 * One uploaded study file (PDF, PPT, PPTX, DOC or DOCX).
 *
 * Two mapping details matter a lot here:
 *
 * 1. The bytes are NOT annotated {@code @Lob}. Under Hibernate 6, {@code @Lob byte[]}
 *    maps to PostgreSQL's {@code oid} large-object type, which needs an explicit
 *    transaction and fails at download time with "Large Objects may not be used in
 *    auto-commit mode". VARBINARY with an explicit length gives {@code bytea} on
 *    PostgreSQL and {@code longblob} on MySQL, which is what we actually want.
 *
 * 2. Every list screen reads through a projection interface, so the {@code data}
 *    and {@code contentText} columns are only ever selected on the download path.
 */
@Entity
@Table(name = "materials", indexes = {
        @Index(name = "idx_material_subject", columnList = "subject_id"),
        @Index(name = "idx_material_public_id", columnList = "public_id", unique = true),
        @Index(name = "idx_material_sha256", columnList = "sha256")
})
public class Material {

    /** 25 MiB. Kept in sync with spring.servlet.multipart.max-file-size. */
    public static final int MAX_FILE_BYTES = 25 * 1024 * 1024;

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    /**
     * Public, unguessable handle used in every URL. The numeric primary key is
     * never exposed, so /materials/1/download style enumeration is not possible.
     */
    @Column(name = "public_id", nullable = false, unique = true, updatable = false, length = 36)
    private String publicId = UUID.randomUUID().toString();

    @Column(name = "original_file_name", nullable = false, length = 255)
    private String originalFileName;

    /** Derived from the validated extension, never trusted from the browser. */
    @Column(name = "content_type", nullable = false, length = 120)
    private String contentType;

    @Column(name = "extension", nullable = false, length = 8)
    private String extension;

    @Column(name = "size_bytes", nullable = false)
    private long sizeBytes;

    /** Lets us spot a file that has already been uploaded to this subject. */
    @Column(name = "sha256", nullable = false, length = 64)
    private String sha256;

    @JdbcTypeCode(SqlTypes.VARBINARY)
    @Column(name = "data", nullable = false, length = MAX_FILE_BYTES)
    private byte[] data;

    /** Plain text pulled out of the file at upload time, so search can look inside it. */
    @JdbcTypeCode(SqlTypes.LONGVARCHAR)
    @Column(name = "content_text")
    private String contentText;

    @Column(name = "uploaded_by", nullable = false, length = 80)
    private String uploadedBy;

    @Column(name = "uploaded_at", nullable = false)
    private LocalDateTime uploadedAt = LocalDateTime.now();

    @Column(name = "download_count", nullable = false)
    private long downloadCount;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "subject_id", nullable = false)
    private Subject subject;

    protected Material() {
        // required by JPA
    }

    public Material(String originalFileName, String contentType, String extension,
                    byte[] data, String sha256, String contentText,
                    String uploadedBy, Subject subject) {
        this.originalFileName = originalFileName;
        this.contentType = contentType;
        this.extension = extension;
        this.data = data;
        this.sizeBytes = data.length;
        this.sha256 = sha256;
        this.contentText = contentText;
        this.uploadedBy = uploadedBy;
        this.subject = subject;
    }

    public Long getId() {
        return id;
    }

    public String getPublicId() {
        return publicId;
    }

    public String getOriginalFileName() {
        return originalFileName;
    }

    public String getContentType() {
        return contentType;
    }

    public String getExtension() {
        return extension;
    }

    public long getSizeBytes() {
        return sizeBytes;
    }

    public String getSha256() {
        return sha256;
    }

    public byte[] getData() {
        return data;
    }

    public String getContentText() {
        return contentText;
    }

    public String getUploadedBy() {
        return uploadedBy;
    }

    public LocalDateTime getUploadedAt() {
        return uploadedAt;
    }

    public void setUploadedAt(LocalDateTime uploadedAt) {
        this.uploadedAt = uploadedAt;
    }

    public long getDownloadCount() {
        return downloadCount;
    }

    public Subject getSubject() {
        return subject;
    }

    /** True for formats a browser can render in a tab without downloading. */
    public boolean isPreviewable() {
        return "pdf".equals(extension);
    }
}

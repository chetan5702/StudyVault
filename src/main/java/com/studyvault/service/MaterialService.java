package com.studyvault.service;

import com.studyvault.config.StudyVaultProperties;
import com.studyvault.domain.Material;
import com.studyvault.domain.Subject;
import com.studyvault.repository.MaterialRepository;
import com.studyvault.repository.MaterialView;
import com.studyvault.repository.SearchHit;
import org.springframework.data.domain.PageRequest;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.server.ResponseStatusException;

import java.io.IOException;
import java.io.OutputStream;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Optional;
import java.util.Set;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;

@Service
public class MaterialService {

    private final MaterialRepository materialRepository;
    private final SubjectService subjectService;
    private final FileValidator fileValidator;
    private final TextExtractor textExtractor;
    private final StudyVaultProperties properties;

    public MaterialService(MaterialRepository materialRepository,
                           SubjectService subjectService,
                           FileValidator fileValidator,
                           TextExtractor textExtractor,
                           StudyVaultProperties properties) {
        this.materialRepository = materialRepository;
        this.subjectService = subjectService;
        this.fileValidator = fileValidator;
        this.textExtractor = textExtractor;
        this.properties = properties;
    }

    @Transactional(readOnly = true)
    public List<MaterialRow> list(Long subjectId) {
        List<MaterialRow> rows = new ArrayList<>();
        for (MaterialView view : materialRepository.findBySubjectIdOrderByUploadedAtDesc(subjectId)) {
            rows.add(new MaterialRow(view));
        }
        return rows;
    }

    /**
     * Validates, de-duplicates by content hash, extracts the text for search,
     * and stores the file.
     */
    @Transactional
    public UploadOutcome store(Long subjectId, MultipartFile file, String username) {
        Subject subject = subjectService.get(subjectId);
        ValidatedUpload upload = fileValidator.validate(file);
        String hash = sha256(upload.data());

        Optional<MaterialView> existing =
                materialRepository.findFirstBySubjectIdAndSha256(subjectId, hash);
        if (existing.isPresent()) {
            return UploadOutcome.duplicateOf(existing.get().getOriginalFileName());
        }

        String text = textExtractor.extract(upload.data(), upload.fileName());
        materialRepository.save(new Material(
                upload.fileName(), upload.contentType(), upload.extension(),
                upload.data(), hash, text, username, subject));
        return UploadOutcome.stored(upload.fileName());
    }

    @Transactional(readOnly = true)
    public Material load(String publicId) {
        return materialRepository.findByPublicId(publicId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "File not found"));
    }

    @Transactional
    public void recordDownload(String publicId) {
        materialRepository.incrementDownloadCount(publicId);
    }

    @Transactional
    public String delete(String publicId) {
        String name = materialRepository.findViewByPublicId(publicId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "File not found"))
                .getOriginalFileName();
        materialRepository.deleteByPublicId(publicId);
        return "Deleted " + name + ".";
    }

    @Transactional(readOnly = true)
    public List<SearchResult> search(String rawQuery) {
        String query = rawQuery == null ? "" : rawQuery.trim();
        if (query.length() < 2) {
            return List.of();
        }
        List<SearchResult> results = new ArrayList<>();
        List<SearchHit> hits = materialRepository.search(
                query, PageRequest.of(0, properties.getSearchResultLimit()));
        for (SearchHit hit : hits) {
            results.add(toResult(hit, query));
        }
        return results;
    }

    /**
     * Streams a subject's files into a zip. Each file is loaded, written and
     * released one at a time, so the whole subject is never in memory at once.
     */
    @Transactional(readOnly = true)
    public void writeZip(Long subjectId, OutputStream outputStream) throws IOException {
        try (ZipOutputStream zip = new ZipOutputStream(outputStream)) {
            Set<String> usedNames = new HashSet<>();
            for (MaterialView view : materialRepository.findBySubjectIdOrderByUploadedAtDesc(subjectId)) {
                Optional<Material> material = materialRepository.findByPublicId(view.getPublicId());
                if (material.isEmpty()) {
                    continue;
                }
                zip.putNextEntry(new ZipEntry(uniqueEntryName(usedNames, material.get().getOriginalFileName())));
                zip.write(material.get().getData());
                zip.closeEntry();
            }
        }
    }

    public String archiveFileName(String subjectName) {
        String slug = subjectName.toLowerCase(Locale.ROOT)
                .replaceAll("[^a-z0-9]+", "-")
                .replaceAll("(^-|-$)", "");
        return (slug.isEmpty() ? "study-material" : slug) + ".zip";
    }

    private SearchResult toResult(SearchHit hit, String query) {
        String text = hit.getContentText();
        int radius = properties.getSnippetRadius();
        String before = "";
        String match = "";
        String after = "";

        if (text != null) {
            int index = text.toLowerCase(Locale.ROOT).indexOf(query.toLowerCase(Locale.ROOT));
            if (index >= 0) {
                int start = Math.max(0, index - radius);
                int end = Math.min(text.length(), index + query.length() + radius);
                before = (start > 0 ? "… " : "") + text.substring(start, index);
                match = text.substring(index, index + query.length());
                after = text.substring(index + query.length(), end) + (end < text.length() ? " …" : "");
            }
        }
        return new SearchResult(hit.getPublicId(), hit.getFileName(), hit.getExtension(),
                hit.getSubjectId(), hit.getSubjectName(), hit.getUploadedAt(), before, match, after);
    }

    private String uniqueEntryName(Set<String> used, String fileName) {
        String candidate = fileName;
        int counter = 2;
        while (!used.add(candidate)) {
            int dot = fileName.lastIndexOf('.');
            candidate = dot < 0
                    ? fileName + " (" + counter + ")"
                    : fileName.substring(0, dot) + " (" + counter + ")" + fileName.substring(dot);
            counter++;
        }
        return candidate;
    }

    private String sha256(byte[] data) {
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256").digest(data);
            StringBuilder hex = new StringBuilder(digest.length * 2);
            for (byte b : digest) {
                hex.append(Character.forDigit((b >> 4) & 0xF, 16));
                hex.append(Character.forDigit(b & 0xF, 16));
            }
            return hex.toString();
        } catch (NoSuchAlgorithmException e) {
            // SHA-256 is required of every JVM, so this cannot happen in practice.
            throw new IllegalStateException("SHA-256 is unavailable", e);
        }
    }
}

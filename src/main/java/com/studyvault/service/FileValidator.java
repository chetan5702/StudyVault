package com.studyvault.service;

import com.studyvault.domain.Material;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.nio.file.Paths;
import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * The accept=".pdf,.pptx" attribute on the upload form is a hint to the file
 * picker and nothing more: anyone can POST whatever they like straight to the
 * endpoint. Every upload is therefore checked here for extension, real size,
 * and leading magic bytes, and its content type is derived from the extension
 * rather than believed from the browser.
 */
@Component
public class FileValidator {

    private static final Map<String, String> ALLOWED_TYPES = new LinkedHashMap<>();

    static {
        ALLOWED_TYPES.put("pdf", "application/pdf");
        ALLOWED_TYPES.put("ppt", "application/vnd.ms-powerpoint");
        ALLOWED_TYPES.put("pptx", "application/vnd.openxmlformats-officedocument.presentationml.presentation");
        ALLOWED_TYPES.put("doc", "application/msword");
        ALLOWED_TYPES.put("docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document");
    }

    private static final byte[] PDF_MAGIC = {0x25, 0x50, 0x44, 0x46};                 // %PDF
    private static final byte[] ZIP_MAGIC = {0x50, 0x4B, 0x03, 0x04};                 // pptx, docx
    private static final byte[] OLE2_MAGIC = {(byte) 0xD0, (byte) 0xCF, 0x11, (byte) 0xE0,
                                              (byte) 0xA1, (byte) 0xB1, 0x1A, (byte) 0xE1}; // ppt, doc

    private static final int MAX_NAME_LENGTH = 200;

    public ValidatedUpload validate(MultipartFile file) {
        if (file == null || file.isEmpty()) {
            throw new UploadRejectedException("Choose a file before uploading.");
        }
        if (file.getSize() > Material.MAX_FILE_BYTES) {
            throw new UploadRejectedException("That file is larger than the 25 MB limit.");
        }

        String fileName = safeFileName(file.getOriginalFilename());
        String extension = extensionOf(fileName);
        String contentType = ALLOWED_TYPES.get(extension);
        if (contentType == null) {
            throw new UploadRejectedException(
                    "Only PDF, PPT, PPTX, DOC and DOCX files can be uploaded. Got: " + fileName);
        }

        byte[] data;
        try {
            data = file.getBytes();
        } catch (IOException e) {
            throw new UploadRejectedException("That file could not be read. Try uploading it again.");
        }

        if (data.length == 0) {
            throw new UploadRejectedException("That file is empty.");
        }
        if (!magicBytesMatch(extension, data)) {
            throw new UploadRejectedException(
                    "The contents of " + fileName + " do not match a ." + extension + " file.");
        }

        return new ValidatedUpload(fileName, extension, contentType, data);
    }

    /**
     * Strips any directory component a client may have sent, so a name like
     * "../../etc/passwd" cannot survive into a header or a zip entry.
     */
    public String safeFileName(String rawName) {
        String cleaned = StringUtils.cleanPath(rawName == null ? "" : rawName);
        String baseName = Paths.get(cleaned).getFileName() == null
                ? ""
                : Paths.get(cleaned).getFileName().toString();
        baseName = baseName.replace('\r', ' ').replace('\n', ' ').replace('"', '\'').trim();
        if (baseName.isEmpty()) {
            throw new UploadRejectedException("That file has no usable name.");
        }
        return baseName.length() > MAX_NAME_LENGTH ? baseName.substring(0, MAX_NAME_LENGTH) : baseName;
    }

    private String extensionOf(String fileName) {
        int dot = fileName.lastIndexOf('.');
        return dot < 0 ? "" : fileName.substring(dot + 1).toLowerCase();
    }

    private boolean magicBytesMatch(String extension, byte[] data) {
        return switch (extension) {
            case "pdf" -> startsWith(data, PDF_MAGIC);
            case "pptx", "docx" -> startsWith(data, ZIP_MAGIC);
            case "ppt", "doc" -> startsWith(data, OLE2_MAGIC);
            default -> false;
        };
    }

    private boolean startsWith(byte[] data, byte[] prefix) {
        return data.length >= prefix.length
                && Arrays.equals(Arrays.copyOfRange(data, 0, prefix.length), prefix);
    }
}

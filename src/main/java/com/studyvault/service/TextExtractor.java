package com.studyvault.service;

import org.apache.tika.Tika;
import org.apache.tika.metadata.Metadata;
import org.apache.tika.metadata.TikaCoreProperties;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.io.ByteArrayInputStream;
import java.io.InputStream;

/**
 * Pulls the readable text out of an uploaded document once, at upload time, so
 * that searching later is a database query rather than a re-parse of every file.
 *
 * Extraction is best-effort: a scanned PDF with no text layer, or a corrupt
 * file, simply yields no text and the material stays searchable by filename.
 */
@Service
public class TextExtractor {

    private static final Logger log = LoggerFactory.getLogger(TextExtractor.class);

    /** Roughly 200 pages of slides. Plenty for search, bounded for storage. */
    private static final int MAX_CHARS = 200_000;

    private final Tika tika;

    public TextExtractor() {
        this.tika = new Tika();
        this.tika.setMaxStringLength(MAX_CHARS);
    }

    public String extract(byte[] data, String fileName) {
        try (InputStream in = new ByteArrayInputStream(data)) {
            Metadata metadata = new Metadata();
            metadata.set(TikaCoreProperties.RESOURCE_NAME_KEY, fileName);
            return normalise(tika.parseToString(in, metadata));
        } catch (Exception e) {
            log.warn("No text could be extracted from {}: {}", fileName, e.toString());
            return null;
        }
    }

    private String normalise(String text) {
        if (text == null) {
            return null;
        }
        String collapsed = text.replaceAll("\\s+", " ").trim();
        return collapsed.isEmpty() ? null : collapsed;
    }
}

package com.studyvault.service;

import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockMultipartFile;

import java.nio.charset.StandardCharsets;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class FileValidatorTest {

    private final FileValidator validator = new FileValidator();

    private static byte[] pdfBytes() {
        return "%PDF-1.7 pretend document".getBytes(StandardCharsets.UTF_8);
    }

    @Test
    void acceptsAPdfAndDerivesItsContentTypeFromTheExtension() {
        MockMultipartFile file = new MockMultipartFile(
                "file", "unit-3.pdf", "text/html", pdfBytes());

        ValidatedUpload upload = validator.validate(file);

        assertThat(upload.fileName()).isEqualTo("unit-3.pdf");
        assertThat(upload.extension()).isEqualTo("pdf");
        // The browser claimed text/html. We ignore that and use our own mapping.
        assertThat(upload.contentType()).isEqualTo("application/pdf");
    }

    @Test
    void rejectsAnExecutableRenamedAsAPdf() {
        MockMultipartFile file = new MockMultipartFile(
                "file", "notes.pdf", "application/pdf", "MZ\u0090 not a pdf".getBytes(StandardCharsets.UTF_8));

        assertThatThrownBy(() -> validator.validate(file))
                .isInstanceOf(UploadRejectedException.class)
                .hasMessageContaining("do not match");
    }

    @Test
    void rejectsAnExtensionThatIsNotOnTheAllowList() {
        MockMultipartFile file = new MockMultipartFile(
                "file", "cheatsheet.exe", "application/octet-stream", pdfBytes());

        assertThatThrownBy(() -> validator.validate(file))
                .isInstanceOf(UploadRejectedException.class)
                .hasMessageContaining("Only PDF");
    }

    @Test
    void stripsDirectoryTraversalFromTheFileName() {
        assertThat(validator.safeFileName("../../../etc/passwd.pdf")).isEqualTo("passwd.pdf");
        assertThat(validator.safeFileName("C:\\Users\\me\\unit 1.pptx")).isEqualTo("unit 1.pptx");
    }

    @Test
    void rejectsAnEmptyUpload() {
        MockMultipartFile file = new MockMultipartFile("file", "empty.pdf", "application/pdf", new byte[0]);

        assertThatThrownBy(() -> validator.validate(file))
                .isInstanceOf(UploadRejectedException.class);
    }
}

package com.studyvault.web;

import com.studyvault.domain.Material;
import com.studyvault.domain.Subject;
import com.studyvault.service.MaterialService;
import com.studyvault.service.SubjectService;
import com.studyvault.service.UploadOutcome;
import com.studyvault.service.UploadRejectedException;
import org.springframework.http.ContentDisposition;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.core.userdetails.UserDetails;
import org.springframework.stereotype.Controller;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.servlet.mvc.method.annotation.StreamingResponseBody;
import org.springframework.web.servlet.mvc.support.RedirectAttributes;

import java.nio.charset.StandardCharsets;

@Controller
public class MaterialController {

    private final MaterialService materialService;
    private final SubjectService subjectService;

    public MaterialController(MaterialService materialService, SubjectService subjectService) {
        this.materialService = materialService;
        this.subjectService = subjectService;
    }

    @PostMapping("/subjects/{id}/materials")
    public String upload(@PathVariable Long id,
                         @RequestParam("file") MultipartFile file,
                         @AuthenticationPrincipal UserDetails user,
                         RedirectAttributes redirect) {
        try {
            UploadOutcome outcome = materialService.store(id, file, user.getUsername());
            redirect.addFlashAttribute(outcome.duplicate() ? "error" : "notice", outcome.message());
        } catch (UploadRejectedException e) {
            redirect.addFlashAttribute("error", e.getMessage());
        }
        return "redirect:/subjects/" + id;
    }

    /** Download with the filename encoded properly, including non-ASCII names. */
    @GetMapping("/materials/{publicId}/download")
    public ResponseEntity<byte[]> download(@PathVariable String publicId) {
        Material material = materialService.load(publicId);
        materialService.recordDownload(publicId);
        return ResponseEntity.ok()
                .contentType(MediaType.parseMediaType(material.getContentType()))
                .header(HttpHeaders.CONTENT_DISPOSITION, disposition("attachment", material))
                .header(HttpHeaders.X_CONTENT_TYPE_OPTIONS, "nosniff")
                .body(material.getData());
    }

    /** Same bytes, shown in the browser instead of saved. Used by the PDF preview. */
    @GetMapping("/materials/{publicId}/view")
    public ResponseEntity<byte[]> view(@PathVariable String publicId) {
        Material material = materialService.load(publicId);
        return ResponseEntity.ok()
                .contentType(MediaType.parseMediaType(material.getContentType()))
                .header(HttpHeaders.CONTENT_DISPOSITION, disposition("inline", material))
                .header(HttpHeaders.X_CONTENT_TYPE_OPTIONS, "nosniff")
                .body(material.getData());
    }

    /** Everything for one subject, zipped on the fly for the night before the exam. */
    @GetMapping("/subjects/{id}/archive")
    public ResponseEntity<StreamingResponseBody> archive(@PathVariable Long id) {
        Subject subject = subjectService.get(id);
        String archiveName = materialService.archiveFileName(subject.getName());
        StreamingResponseBody body = outputStream -> materialService.writeZip(id, outputStream);
        return ResponseEntity.ok()
                .contentType(MediaType.parseMediaType("application/zip"))
                .header(HttpHeaders.CONTENT_DISPOSITION, ContentDisposition.attachment()
                        .filename(archiveName, StandardCharsets.UTF_8).build().toString())
                .body(body);
    }

    @PostMapping("/materials/{publicId}/delete")
    public String delete(@PathVariable String publicId,
                         @RequestParam Long subjectId,
                         RedirectAttributes redirect) {
        redirect.addFlashAttribute("notice", materialService.delete(publicId));
        return "redirect:/subjects/" + subjectId;
    }

    private String disposition(String type, Material material) {
        return ContentDisposition.builder(type)
                .filename(material.getOriginalFileName(), StandardCharsets.UTF_8)
                .build()
                .toString();
    }
}

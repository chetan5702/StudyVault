package com.college.pptrepo.controller;

import com.college.pptrepo.entity.PptFile;
import com.college.pptrepo.entity.Subject;
import com.college.pptrepo.repository.PptFileRepository;
import com.college.pptrepo.repository.SubjectRepository;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.util.List;

@Controller
public class PptController {

    private final SubjectRepository subjectRepository;
    private final PptFileRepository pptFileRepository;

    public PptController(SubjectRepository subjectRepository, PptFileRepository pptFileRepository) {
        this.subjectRepository = subjectRepository;
        this.pptFileRepository = pptFileRepository;
    }

    // Home page: list of all subjects
    @GetMapping("/")
    public String home(Model model) {
        List<Subject> subjects = subjectRepository.findAll();
        model.addAttribute("subjects", subjects);
        return "home";
    }

    // Add a new subject (simple form on the home page)
    @PostMapping("/subjects/add")
    public String addSubject(@RequestParam String name) {
        String trimmed = name.trim();
        if (!trimmed.isEmpty() && subjectRepository.findByName(trimmed).isEmpty()) {
            subjectRepository.save(new Subject(trimmed));
        }
        return "redirect:/";
    }

    // Subject detail page: shows all files for that subject + upload form
    @GetMapping("/subjects/{id}")
    public String subjectDetail(@PathVariable Long id, Model model) {
        Subject subject = subjectRepository.findById(id)
                .orElseThrow(() -> new RuntimeException("Subject not found"));
        List<PptFile> files = pptFileRepository.findBySubjectOrderByUploadedAtDesc(subject);
        model.addAttribute("subject", subject);
        model.addAttribute("files", files);
        return "subject-detail";
    }

    // Handle file upload for a subject - reads the bytes straight into the database
    @PostMapping("/subjects/{id}/upload")
    public String uploadFile(@PathVariable Long id, @RequestParam("file") MultipartFile file) throws IOException {
        Subject subject = subjectRepository.findById(id)
                .orElseThrow(() -> new RuntimeException("Subject not found"));

        if (!file.isEmpty()) {
            String contentType = file.getContentType() != null ? file.getContentType() : "application/octet-stream";
            PptFile pptFile = new PptFile(file.getOriginalFilename(), contentType, file.getBytes(), subject);
            pptFileRepository.save(pptFile);
        }

        return "redirect:/subjects/" + id;
    }

    // Handle file download - streams the bytes back out of the database
    @GetMapping("/files/{fileId}/download")
    @ResponseBody
    public ResponseEntity<byte[]> downloadFile(@PathVariable Long fileId) {
        PptFile pptFile = pptFileRepository.findById(fileId)
                .orElseThrow(() -> new RuntimeException("File not found"));

        return ResponseEntity.ok()
                .contentType(MediaType.parseMediaType(pptFile.getContentType()))
                .header(HttpHeaders.CONTENT_DISPOSITION,
                        "attachment; filename=\"" + pptFile.getOriginalFileName() + "\"")
                .body(pptFile.getData());
    }
}

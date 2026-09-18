package com.studyvault.web;

import com.studyvault.domain.Subject;
import com.studyvault.service.MaterialService;
import com.studyvault.service.SubjectCard;
import com.studyvault.service.SubjectService;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.servlet.mvc.support.RedirectAttributes;

import java.time.LocalDate;
import java.time.temporal.ChronoUnit;

@Controller
public class SubjectController {

    private final SubjectService subjectService;
    private final MaterialService materialService;

    public SubjectController(SubjectService subjectService, MaterialService materialService) {
        this.subjectService = subjectService;
        this.materialService = materialService;
    }

    @GetMapping("/")
    public String home(Model model) {
        model.addAttribute("cards", subjectService.cards());
        return "home";
    }

    @PostMapping("/subjects")
    public String addSubject(@RequestParam String name, RedirectAttributes redirect) {
        String problem = subjectService.create(name);
        if (problem != null) {
            redirect.addFlashAttribute("error", problem);
        } else {
            redirect.addFlashAttribute("notice", "Added " + name.trim() + ".");
        }
        return "redirect:/";
    }

    @GetMapping("/subjects/{id}")
    public String subjectDetail(@PathVariable Long id, Model model) {
        Subject subject = subjectService.get(id);
        Long days = subject.getExamDate() == null
                ? null
                : ChronoUnit.DAYS.between(LocalDate.now(), subject.getExamDate());
        model.addAttribute("subject", subject);
        model.addAttribute("materials", materialService.list(id));
        model.addAttribute("countdown", SubjectCard.countdownLabel(days));
        model.addAttribute("urgency", SubjectCard.urgency(days));
        return "subject";
    }

    @PostMapping("/subjects/{id}/exam-date")
    public String setExamDate(@PathVariable Long id,
                              @RequestParam(required = false)
                              @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate examDate,
                              RedirectAttributes redirect) {
        subjectService.setExamDate(id, examDate);
        redirect.addFlashAttribute("notice",
                examDate == null ? "Exam date cleared." : "Exam date set to " + examDate + ".");
        return "redirect:/subjects/" + id;
    }

    @PostMapping("/subjects/{id}/delete")
    public String deleteSubject(@PathVariable Long id, RedirectAttributes redirect) {
        redirect.addFlashAttribute("notice", subjectService.delete(id));
        return "redirect:/";
    }
}

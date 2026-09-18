package com.studyvault.service;

import com.studyvault.domain.Subject;
import com.studyvault.repository.MaterialRepository;
import com.studyvault.repository.SubjectRepository;
import com.studyvault.repository.SubjectSummary;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

import java.time.LocalDate;
import java.time.temporal.ChronoUnit;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;

@Service
public class SubjectService {

    private static final int MAX_NAME_LENGTH = 120;

    private final SubjectRepository subjectRepository;
    private final MaterialRepository materialRepository;

    public SubjectService(SubjectRepository subjectRepository, MaterialRepository materialRepository) {
        this.subjectRepository = subjectRepository;
        this.materialRepository = materialRepository;
    }

    /**
     * Home page data: one query, no file bytes, ordered by what is most urgent.
     * Subjects with an exam coming up lead, soonest first; then subjects with no
     * date, alphabetically; then subjects whose exam has passed.
     */
    @Transactional(readOnly = true)
    public List<SubjectCard> cards() {
        LocalDate today = LocalDate.now();
        List<SubjectCard> cards = new ArrayList<>();
        for (SubjectSummary summary : subjectRepository.findAllSummaries()) {
            Long days = summary.getExamDate() == null
                    ? null
                    : ChronoUnit.DAYS.between(today, summary.getExamDate());
            cards.add(new SubjectCard(summary.getId(), summary.getName(), summary.getExamDate(),
                    summary.getFileCount(), summary.getTotalBytes(), days));
        }
        cards.sort(Comparator.<SubjectCard>comparingInt(SubjectService::orderingGroup)
                .thenComparingLong(SubjectService::daysKey)
                .thenComparing(SubjectCard::getName, String.CASE_INSENSITIVE_ORDER));
        return cards;
    }

    /** 0 = exam coming up, 1 = no date set, 2 = exam already gone. */
    private static int orderingGroup(SubjectCard card) {
        if (card.isExamUpcoming()) {
            return 0;
        }
        return card.getExamDate() == null ? 1 : 2;
    }

    private static long daysKey(SubjectCard card) {
        return card.isExamUpcoming() ? card.getDaysUntilExam() : 0L;
    }

    @Transactional(readOnly = true)
    public Subject get(Long id) {
        return subjectRepository.findById(id)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Subject not found"));
    }

    /**
     * @return a message for the user, or null when the subject was created cleanly.
     */
    @Transactional
    public String create(String rawName) {
        String name = rawName == null ? "" : rawName.trim().replaceAll("\\s+", " ");
        if (name.isEmpty()) {
            return "Give the subject a name.";
        }
        if (name.length() > MAX_NAME_LENGTH) {
            return "Subject names are limited to " + MAX_NAME_LENGTH + " characters.";
        }
        if (subjectRepository.findByNameIgnoreCase(name).isPresent()) {
            return "\"" + name + "\" already exists.";
        }
        subjectRepository.save(new Subject(name));
        return null;
    }

    @Transactional
    public void setExamDate(Long id, LocalDate examDate) {
        Subject subject = get(id);
        subject.setExamDate(examDate);
        subjectRepository.save(subject);
    }

    /**
     * Deletes the materials with a bulk statement rather than cascading through
     * a loaded collection, so no file bytes are read into memory to delete them.
     */
    @Transactional
    public String delete(Long id) {
        Subject subject = get(id);
        materialRepository.deleteBySubjectId(id);
        subjectRepository.delete(subject);
        return "Deleted " + subject.getName() + " and everything in it.";
    }
}

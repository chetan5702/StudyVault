package com.studyvault.repository;

import com.studyvault.domain.Material;
import com.studyvault.domain.Subject;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.orm.jpa.DataJpaTest;

import java.nio.charset.StandardCharsets;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * The counts on the home page come from one aggregate query. This test pins
 * that behaviour so nobody reintroduces the per-subject collection that used to
 * drag every file's bytes into memory.
 */
@DataJpaTest
class SubjectRepositoryTest {

    @Autowired
    private SubjectRepository subjectRepository;

    @Autowired
    private MaterialRepository materialRepository;

    @Test
    void summarisesFileCountAndTotalSizePerSubject() {
        Subject daa = subjectRepository.save(new Subject("DAA"));
        Subject os = subjectRepository.save(new Subject("Operating Systems"));

        materialRepository.save(material("unit-1.pdf", 1000, daa));
        materialRepository.save(material("unit-2.pdf", 2000, daa));

        List<SubjectSummary> summaries = subjectRepository.findAllSummaries();

        assertThat(summaries).hasSize(2);
        SubjectSummary daaSummary = summaries.stream()
                .filter(s -> s.getId().equals(daa.getId())).findFirst().orElseThrow();
        SubjectSummary osSummary = summaries.stream()
                .filter(s -> s.getId().equals(os.getId())).findFirst().orElseThrow();

        assertThat(daaSummary.getFileCount()).isEqualTo(2);
        assertThat(daaSummary.getTotalBytes()).isEqualTo(3000);
        // A subject with nothing in it still appears, with zeroes.
        assertThat(osSummary.getFileCount()).isZero();
        assertThat(osSummary.getTotalBytes()).isZero();
    }

    @Test
    void findsMaterialsByTextExtractedFromInsideTheDocument() {
        Subject daa = subjectRepository.save(new Subject("Algorithms"));
        Material lecture = material("week-4.pdf", 500, daa);
        materialRepository.save(lecture);

        List<SearchHit> hits = materialRepository.search("knapsack",
                org.springframework.data.domain.PageRequest.of(0, 10));

        assertThat(hits).hasSize(1);
        assertThat(hits.get(0).getFileName()).isEqualTo("week-4.pdf");
        assertThat(hits.get(0).getSubjectName()).isEqualTo("Algorithms");
    }

    private Material material(String name, int size, Subject subject) {
        byte[] data = new byte[size];
        System.arraycopy("%PDF".getBytes(StandardCharsets.UTF_8), 0, data, 0, 4);
        return new Material(name, "application/pdf", "pdf", data, "hash-" + name,
                "Greedy algorithms and the knapsack problem", "student", subject);
    }
}

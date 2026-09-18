package com.studyvault.repository;

import com.studyvault.domain.Subject;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;

import java.util.List;
import java.util.Optional;

public interface SubjectRepository extends JpaRepository<Subject, Long> {

    Optional<Subject> findByNameIgnoreCase(String name);

    /**
     * One query for the whole home page. The old code called
     * {@code subject.getFiles().size()} inside the template, which fired a
     * separate SELECT per subject and dragged every file's bytes along with it.
     */
    @Query("""
           select s.id           as id,
                  s.name         as name,
                  s.examDate     as examDate,
                  count(m.id)    as fileCount,
                  coalesce(sum(m.sizeBytes), 0) as totalBytes
           from Subject s
           left join Material m on m.subject = s
           group by s.id, s.name, s.examDate
           """)
    List<SubjectSummary> findAllSummaries();
}

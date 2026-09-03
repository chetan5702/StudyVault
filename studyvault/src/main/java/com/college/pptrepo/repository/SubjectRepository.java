package com.college.pptrepo.repository;

import com.college.pptrepo.entity.Subject;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;

/**
 * By extending JpaRepository, we get findAll(), save(), findById(),
 * deleteById() etc for free - no SQL to write for basic operations.
 */
public interface SubjectRepository extends JpaRepository<Subject, Long> {
    Optional<Subject> findByName(String name);
}

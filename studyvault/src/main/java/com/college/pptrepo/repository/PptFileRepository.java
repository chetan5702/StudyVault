package com.college.pptrepo.repository;

import com.college.pptrepo.entity.PptFile;
import com.college.pptrepo.entity.Subject;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface PptFileRepository extends JpaRepository<PptFile, Long> {
    List<PptFile> findBySubjectOrderByUploadedAtDesc(Subject subject);
}

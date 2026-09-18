package com.studyvault.repository;

import com.studyvault.domain.Material;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.List;
import java.util.Optional;

public interface MaterialRepository extends JpaRepository<Material, Long> {

    /** Listing: projection, so no bytes and no extracted text are selected. */
    List<MaterialView> findBySubjectIdOrderByUploadedAtDesc(Long subjectId);

    /** Download: the only place a full entity, and therefore the bytes, is loaded. */
    Optional<Material> findByPublicId(String publicId);

    Optional<MaterialView> findViewByPublicId(String publicId);

    Optional<MaterialView> findFirstBySubjectIdAndSha256(Long subjectId, String sha256);

    long countBySubjectId(Long subjectId);

    /**
     * Substring search over filenames and extracted document text. This is
     * portable across MySQL, PostgreSQL and H2 with no dialect-specific SQL.
     * See the README for the PostgreSQL tsvector upgrade once the vault grows.
     */
    @Query("""
           select m.publicId          as publicId,
                  m.originalFileName  as fileName,
                  m.extension         as extension,
                  s.id                as subjectId,
                  s.name              as subjectName,
                  m.uploadedAt        as uploadedAt,
                  m.contentText       as contentText
           from Material m
           join m.subject s
           where lower(m.originalFileName) like lower(concat('%', :q, '%'))
              or lower(m.contentText)      like lower(concat('%', :q, '%'))
           order by m.uploadedAt desc
           """)
    List<SearchHit> search(@Param("q") String q, Pageable pageable);

    @Modifying
    @Query("update Material m set m.downloadCount = m.downloadCount + 1 where m.publicId = :publicId")
    void incrementDownloadCount(@Param("publicId") String publicId);

    @Modifying
    @Query("delete from Material m where m.subject.id = :subjectId")
    void deleteBySubjectId(@Param("subjectId") Long subjectId);

    @Modifying
    @Query("delete from Material m where m.publicId = :publicId")
    int deleteByPublicId(@Param("publicId") String publicId);
}

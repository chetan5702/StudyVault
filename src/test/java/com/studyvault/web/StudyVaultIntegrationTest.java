package com.studyvault.web;

import com.studyvault.repository.MaterialRepository;
import com.studyvault.repository.SubjectRepository;
import com.studyvault.domain.Subject;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.security.test.context.support.WithMockUser;
import org.springframework.test.web.servlet.MockMvc;

import java.nio.charset.StandardCharsets;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.csrf;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.multipart;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.redirectedUrlPattern;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
class StudyVaultIntegrationTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private SubjectRepository subjectRepository;

    @Autowired
    private MaterialRepository materialRepository;

    @Test
    void anonymousVisitorsAreSentToTheLoginPage() throws Exception {
        mockMvc.perform(get("/"))
                .andExpect(status().is3xxRedirection())
                .andExpect(redirectedUrlPattern("**/login"));
    }

    @Test
    @WithMockUser(username = "student", roles = "USER")
    void aSignedInStudentCanUploadAndThenDownloadAFile() throws Exception {
        Subject subject = subjectRepository.save(new Subject("DBMS " + System.nanoTime()));
        byte[] pdf = "%PDF-1.4 normalisation and functional dependency".getBytes(StandardCharsets.UTF_8);
        MockMultipartFile upload = new MockMultipartFile("file", "unit-2.pdf", "application/pdf", pdf);

        mockMvc.perform(multipart("/subjects/{id}/materials", subject.getId()).file(upload).with(csrf()))
                .andExpect(status().is3xxRedirection());

        var stored = materialRepository.findBySubjectIdOrderByUploadedAtDesc(subject.getId());
        assertThat(stored).hasSize(1);
        assertThat(stored.get(0).getSizeBytes()).isEqualTo(pdf.length);

        mockMvc.perform(get("/materials/{pid}/download", stored.get(0).getPublicId()))
                .andExpect(status().isOk())
                .andExpect(header().string("Content-Disposition",
                        org.hamcrest.Matchers.containsString("attachment")));
    }

    @Test
    @WithMockUser(username = "student", roles = "USER")
    void theSameFileIsNotStoredTwiceInOneSubject() throws Exception {
        Subject subject = subjectRepository.save(new Subject("OS " + System.nanoTime()));
        byte[] pdf = "%PDF-1.4 paging and segmentation".getBytes(StandardCharsets.UTF_8);

        for (int i = 0; i < 2; i++) {
            mockMvc.perform(multipart("/subjects/{id}/materials", subject.getId())
                            .file(new MockMultipartFile("file", "same.pdf", "application/pdf", pdf))
                            .with(csrf()))
                    .andExpect(status().is3xxRedirection());
        }

        assertThat(materialRepository.countBySubjectId(subject.getId())).isEqualTo(1);
    }

    @Test
    @WithMockUser(username = "student", roles = "USER")
    void deletingIsRefusedForAccountsWithoutTheAdminRole() throws Exception {
        mockMvc.perform(org.springframework.test.web.servlet.request.MockMvcRequestBuilders
                        .post("/subjects/{id}/delete", 1L).with(csrf()))
                .andExpect(status().isForbidden());
    }
}

package com.studyvault;

import com.studyvault.config.StudyVaultProperties;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.EnableConfigurationProperties;

@SpringBootApplication
@EnableConfigurationProperties(StudyVaultProperties.class)
public class StudyVaultApplication {

    public static void main(String[] args) {
        SpringApplication.run(StudyVaultApplication.class, args);
    }
}

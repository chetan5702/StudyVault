package com.college.pptrepo;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/**
 * Entry point of the application.
 * Running this class starts an embedded web server (like how you'd
 * run a Java console app, except this one listens on a port instead
 * of a terminal).
 */
@SpringBootApplication
public class PptRepoApplication {
    public static void main(String[] args) {
        SpringApplication.run(PptRepoApplication.class, args);
    }
}

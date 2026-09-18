package com.studyvault.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * Everything that used to be hard-coded. Each value is backed by an environment
 * variable in application.properties, so no credential ever needs to be edited
 * into a file that gets committed.
 */
@ConfigurationProperties(prefix = "studyvault")
public class StudyVaultProperties {

    private final Account admin = new Account("admin", "admin123");
    private final Account student = new Account("student", "student123");

    /** How many search results to show on one page. */
    private int searchResultLimit = 25;

    /** Characters of context shown either side of a search match. */
    private int snippetRadius = 120;

    public Account getAdmin() {
        return admin;
    }

    public Account getStudent() {
        return student;
    }

    public int getSearchResultLimit() {
        return searchResultLimit;
    }

    public void setSearchResultLimit(int searchResultLimit) {
        this.searchResultLimit = searchResultLimit;
    }

    public int getSnippetRadius() {
        return snippetRadius;
    }

    public void setSnippetRadius(int snippetRadius) {
        this.snippetRadius = snippetRadius;
    }

    public static class Account {

        private String username;
        private String password;

        public Account(String username, String password) {
            this.username = username;
            this.password = password;
        }

        public String getUsername() {
            return username;
        }

        public void setUsername(String username) {
            this.username = username;
        }

        public String getPassword() {
            return password;
        }

        public void setPassword(String password) {
            this.password = password;
        }
    }
}

package com.studyvault.config;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpMethod;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.core.userdetails.User;
import org.springframework.security.core.userdetails.UserDetails;
import org.springframework.security.core.userdetails.UserDetailsService;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.provisioning.InMemoryUserDetailsManager;
import org.springframework.security.web.SecurityFilterChain;

/**
 * The old app had no authentication at all: anyone who found the URL could
 * upload to it and download from it. Two roles now exist.
 *
 *   USER  - browse, search, upload, download
 *   ADMIN - all of the above, plus delete
 *
 * CSRF protection comes on automatically with Spring Security, and Thymeleaf
 * adds the token to every form written with th:action.
 */
@Configuration
@EnableWebSecurity
public class SecurityConfig {

    private static final Logger log = LoggerFactory.getLogger(SecurityConfig.class);

    @Bean
    SecurityFilterChain securityFilterChain(HttpSecurity http) throws Exception {
        http
                .authorizeHttpRequests(auth -> auth
                        .requestMatchers("/css/**", "/favicon.ico", "/login", "/error").permitAll()
                        .requestMatchers(HttpMethod.POST, "/subjects/*/delete", "/materials/*/delete")
                        .hasRole("ADMIN")
                        .anyRequest().authenticated())
                .formLogin(form -> form
                        .loginPage("/login")
                        .defaultSuccessUrl("/", true)
                        .permitAll())
                .logout(logout -> logout
                        .logoutSuccessUrl("/login?logout"))
                // The inline PDF viewer embeds a same-origin URL in an <iframe>,
                // which the default DENY policy would block.
                .headers(headers -> headers.frameOptions(frame -> frame.sameOrigin()));
        return http.build();
    }

    @Bean
    PasswordEncoder passwordEncoder() {
        return new BCryptPasswordEncoder();
    }

    @Bean
    UserDetailsService userDetailsService(StudyVaultProperties properties, PasswordEncoder encoder) {
        warnAboutDefaultPassword(properties.getAdmin(), "admin123", "SV_ADMIN_PASSWORD");
        warnAboutDefaultPassword(properties.getStudent(), "student123", "SV_STUDENT_PASSWORD");

        UserDetails admin = User.withUsername(properties.getAdmin().getUsername())
                .password(encoder.encode(properties.getAdmin().getPassword()))
                .roles("ADMIN", "USER")
                .build();

        UserDetails student = User.withUsername(properties.getStudent().getUsername())
                .password(encoder.encode(properties.getStudent().getPassword()))
                .roles("USER")
                .build();

        return new InMemoryUserDetailsManager(admin, student);
    }

    private void warnAboutDefaultPassword(StudyVaultProperties.Account account,
                                          String shippedDefault, String envVar) {
        if (shippedDefault.equals(account.getPassword())) {
            log.warn("Account '{}' is using the password this project ships with. "
                    + "Set {} before putting StudyVault on the internet.",
                    account.getUsername(), envVar);
        }
    }
}

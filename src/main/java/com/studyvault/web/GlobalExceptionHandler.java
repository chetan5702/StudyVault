package com.studyvault.web;

import com.studyvault.service.UploadRejectedException;
import org.springframework.web.bind.annotation.ControllerAdvice;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.multipart.MaxUploadSizeExceededException;
import org.springframework.web.servlet.mvc.support.RedirectAttributes;

/**
 * Turns the two failures a user can actually cause into a message on the page
 * they were on, instead of Spring's default white error screen.
 */
@ControllerAdvice
public class GlobalExceptionHandler {

    @ExceptionHandler(MaxUploadSizeExceededException.class)
    public String handleTooLarge(RedirectAttributes redirect) {
        redirect.addFlashAttribute("error", "That file is larger than the 25 MB limit.");
        return "redirect:/";
    }

    @ExceptionHandler(UploadRejectedException.class)
    public String handleRejectedUpload(UploadRejectedException e, RedirectAttributes redirect) {
        redirect.addFlashAttribute("error", e.getMessage());
        return "redirect:/";
    }
}

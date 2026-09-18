package com.studyvault.service;

/** Result of storing one upload. */
public record UploadOutcome(boolean duplicate, String message) {

    public static UploadOutcome stored(String fileName) {
        return new UploadOutcome(false, "Uploaded " + fileName + ".");
    }

    public static UploadOutcome duplicateOf(String existingFileName) {
        return new UploadOutcome(true,
                "That exact file is already in this subject as \"" + existingFileName + "\".");
    }
}

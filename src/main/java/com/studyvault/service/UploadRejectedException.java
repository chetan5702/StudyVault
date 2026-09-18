package com.studyvault.service;

/** Thrown when an upload fails a server-side check. The message is shown to the user. */
public class UploadRejectedException extends RuntimeException {

    public UploadRejectedException(String message) {
        super(message);
    }
}

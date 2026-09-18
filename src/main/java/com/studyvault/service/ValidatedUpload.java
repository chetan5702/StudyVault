package com.studyvault.service;

/** An upload that has passed every server-side check. */
public record ValidatedUpload(String fileName, String extension, String contentType, byte[] data) {
}

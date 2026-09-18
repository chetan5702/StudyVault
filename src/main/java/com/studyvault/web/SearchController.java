package com.studyvault.web;

import com.studyvault.service.MaterialService;
import com.studyvault.service.SearchResult;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;

import java.util.List;

@Controller
public class SearchController {

    private final MaterialService materialService;

    public SearchController(MaterialService materialService) {
        this.materialService = materialService;
    }

    @GetMapping("/search")
    public String search(@RequestParam(name = "q", required = false) String query, Model model) {
        String trimmed = query == null ? "" : query.trim();
        List<SearchResult> results = materialService.search(trimmed);
        model.addAttribute("query", trimmed);
        model.addAttribute("results", results);
        model.addAttribute("heading", results.size() == 1
                ? "1 match for " + trimmed
                : results.size() + " matches for " + trimmed);
        return "search";
    }
}

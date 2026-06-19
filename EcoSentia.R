################################################################################
## Bibliometric Analysis: AI in Biomimetics 
## General indicators : merged WoS + Scopus (deduplicated)
## Co-citation        : WoS-only (standardized, parseable cited references)
## Visualization      : R only (bibliometrix + igraph + ggraph + ggplot2)
## Time window        : 2015-2025. 
################################################################################

## ============================ 00. SETUP ====================================
set.seed(42)

required <- c("bibliometrix", "igraph", "ggraph", "ggplot2",
              "dplyr", "stringr", "tidyr", "viridis", "scales", "ggrepel")
for (pkg in required) {
  if (!requireNamespace(pkg, quietly = TRUE)) install.packages(pkg)
}
suppressPackageStartupMessages({
  library(bibliometrix); library(igraph); library(ggraph); library(ggplot2)
  library(dplyr); library(stringr); library(tidyr); library(viridis); library(scales)
  library(ggrepel)
})

cat("bibliometrix version:", as.character(packageVersion("bibliometrix")), "\n")

## ---- Global plotting switch (FALSE avoids RStudio zero-viewport errors) ----
SHOW_PLOTS <- FALSE

## ---- Output directory (all artifacts go here) ----
OUTDIR <- path.expand("~/Downloads/Ecosentia/EcoSentia/Bibliometric/OUTPUT")

cat("Requested OUTDIR:\n", OUTDIR, "\n")

if (!dir.exists(OUTDIR)) {
  ok <- dir.create(OUTDIR, recursive = TRUE, showWarnings = TRUE)
  cat("dir.create result:", ok, "\n")
}

if (!dir.exists(OUTDIR)) {
  stop("Output directory was not created. Check path spelling and write permission: ", OUTDIR)
}

OUTDIR <- normalizePath(OUTDIR, winslash = "/", mustWork = TRUE)
cat("Normalized OUTDIR:\n", OUTDIR, "\n")

op <- function(name) file.path(OUTDIR, name)

save_fig <- function(plot, name, width = 10, height = 8) {
  ggsave(
    op(paste0(name, ".png")),
    plot,
    width = width,
    height = height,
    dpi = 600,
    bg = "white"
  )
  ggsave(
    op(paste0(name, ".pdf")),
    plot,
    width = width,
    height = height,
    bg = "white"
  )
  cat("Saved figure:", name, "\n")
}

theme_pub <- function(base_size = 13) {
  theme_minimal(base_size = base_size) +
    theme(
      plot.title       = element_text(face = "bold", size = base_size + 1),
      plot.subtitle    = element_text(color = "grey40"),
      panel.grid.minor = element_blank(),
      legend.position  = "right"
    )
}

## ============================ 01. IMPORT ===================================
wos_path    <- path.expand("~/Downloads/Ecosentia/EcoSentia/Bibliometric/WOS")     ## << EDIT
scopus_path <- path.expand("~/Downloads/Ecosentia/EcoSentia/Bibliometric/SCOPUS")  ## << EDIT

wos_files    <- list.files(wos_path,    pattern = "\\.(txt|bib)$",
                           full.names = TRUE, ignore.case = TRUE)
scopus_files <- list.files(scopus_path, pattern = "\\.(csv|bib)$",
                           full.names = TRUE, ignore.case = TRUE)

cat("WoS files found:", length(wos_files),
    "| Scopus files found:", length(scopus_files), "\n")

M_wos    <- convert2df(file = wos_files,    dbsource = "wos",    format = "plaintext")
M_scopus <- convert2df(file = scopus_files, dbsource = "scopus", format = "csv")

cat("WoS records:", nrow(M_wos), "| Scopus records:", nrow(M_scopus), "\n")

## ============================ 02. MERGE + FILTER + QC ======================
## Merged corpus used for GENERAL indicators only.
M <- mergeDbSources(M_wos, M_scopus, remove.duplicated = TRUE)
cat("Merged corpus (deduplicated):", nrow(M), "\n")

## Temporal filter: 2015-2025.
## 2026 is the current (incomplete) indexing year at retrieval (03 June 2026)
## and is excluded by design to avoid a truncated final-year artifact.
M$PY <- suppressWarnings(as.numeric(M$PY))
n_pre <- nrow(M)
n_2026 <- sum(!is.na(M$PY) & M$PY == 2026)
cat("Excluded 2026 (incomplete current year):", n_2026, "records\n")

M <- M[!is.na(M$PY) & M$PY >= 2015 & M$PY <= 2025, ]
cat("Removed out-of-range records:", n_pre - nrow(M),
    "| After temporal filter (2015-2025):", nrow(M), "\n")

## Extract country tags BEFORE main analysis (ordering fix).
M <- metaTagExtraction(M, Field = "AU_CO", sep = ";")

## Field completeness audit.
fields <- c("AU","TI","SO","PY","DI","DT","DE","ID","TC","CR","AB","C1")
completeness <- sapply(fields, function(f) {
  if (f %in% names(M)) {
    v <- as.character(M[[f]])
    round(mean(!is.na(v) & trimws(v) != "" & toupper(trimws(v)) != "NA") * 100, 1)
  } else NA
})
completeness_df <- data.frame(field = names(completeness),
                              completeness_pct = as.numeric(completeness))
print(completeness_df)
write.csv(completeness_df, op("field_completeness.csv"), row.names = FALSE)

## Residual duplicate DOIs.
norm_doi <- toupper(trimws(M$DI)); norm_doi[norm_doi %in% c("", "NA")] <- NA
cat("Residual duplicate DOIs:", sum(duplicated(norm_doi) & !is.na(norm_doi)), "\n")

n_docs    <- nrow(M)
n_sources <- length(unique(M$SO))
cat("FINAL merged corpus:", n_docs, "docs |", n_sources, "sources\n")

## ============================ 03. MAIN ANALYSIS ============================
res <- biblioAnalysis(M, sep = ";")
S   <- summary(res, k = 20, pause = FALSE)

## ============================ 04. ANNUAL GROWTH ============================
trend_df <- M %>%
  filter(!is.na(PY)) %>%
  count(PY, name = "Articles") %>%
  rename(Year = PY) %>%
  arrange(Year)

## CAGR over the FULL 2015-2025 window.
## 2025 is the last COMPLETE calendar year; 2026 was excluded upstream.
y0 <- trend_df$Articles[trend_df$Year == 2015]
yN <- trend_df$Articles[trend_df$Year == 2025]
ny <- 2025 - 2015
cagr <- round(((yN / y0)^(1 / ny) - 1) * 100, 2)
cat("CAGR (2015-2025):", cagr, "%\n")

peak_x <- min(trend_df$Year) + 1
peak_y <- max(trend_df$Articles) * 0.85

p_trend <- ggplot(trend_df, aes(x = Year, y = Articles)) +
  geom_area(fill = "#3498db", alpha = 0.12) +
  geom_line(color = "#2c3e50", linewidth = 1.1) +
  geom_point(color = "#e74c3c", size = 3) +
  geom_text(aes(label = Articles), vjust = -1.1, size = 3, color = "#2c3e50") +
  annotate("text", x = peak_x, y = peak_y,
           label = paste0("CAGR (2015-2025) = ", cagr, "%"),
           size = 5, fontface = "bold", color = "#e74c3c", hjust = 0) +
  scale_x_continuous(breaks = trend_df$Year) +
  scale_y_continuous(expand = expansion(mult = c(0.02, 0.12))) +
  labs(title = "Annual Scientific Production: AI in Biomimetics (2015-2025)",
       subtitle = paste0("Total documents: ", sum(trend_df$Articles),
                         " | CAGR (2015-2025): ", cagr, "%"),
       x = "Publication Year", y = "Number of Documents",
       caption = "Source: Web of Science + Scopus (merged, deduplicated). Retrieval: 03 June 2026; 2026 excluded.") +
  theme_pub() +
  theme(axis.text.x = element_text(angle = 45, hjust = 1))

save_fig(p_trend, "fig1_annual_production", width = 9, height = 5.5)
if (SHOW_PLOTS) print(p_trend)

## ============================ 05. AUTHORS / COUNTRIES / SOURCES ============
authors_prod <- as.data.frame(res$Authors)
write.csv(head(authors_prod, 30), op("top_authors.csv"), row.names = FALSE)

country_prod <- as.data.frame(res$Countries)
write.csv(country_prod, op("country_production.csv"), row.names = FALSE)

NetCountries <- tryCatch(
  biblioNetwork(M, analysis = "collaboration", network = "countries", sep = ";"),
  error = function(e) { cat("Country network error:", e$message, "\n"); NULL })
if (!is.null(NetCountries)) {
  gC <- graph_from_adjacency_matrix(NetCountries, mode = "undirected",
                                    weighted = TRUE, diag = FALSE)
  write.csv(igraph::as_data_frame(gC, what = "edges"),
            op("country_collaboration_edges.csv"), row.names = FALSE)
}

brad <- tryCatch(bradford(M), error = function(e) NULL)
if (!is.null(brad)) write.csv(brad$table, op("bradford_zones.csv"), row.names = FALSE)

top_sources <- as.data.frame(sort(table(M$SO), decreasing = TRUE)[1:30])
names(top_sources) <- c("Source", "Documents")
write.csv(top_sources, op("top_sources.csv"), row.names = FALSE)

top_cited_docs <- as.data.frame(res$MostCitedPapers)
write.csv(top_cited_docs, op("top_cited_documents.csv"), row.names = FALSE)

## ============================ 06. KEYWORD CLEANING =========================
clean_kw <- function(x) {
  x %>% str_to_lower() %>%
    str_replace_all("[-_]", " ") %>%
    str_replace_all("\\s+", " ") %>%
    str_trim()
}

keyword_dictionary <- c(
  "neural network"               = "neural networks",
  "neural networks"              = "neural networks",
  "artificial neural network"    = "neural networks",
  "artificial neural networks"   = "neural networks",
  "ann"                          = "neural networks",
  "convolutional neural network" = "convolutional neural networks",
  "convolutional neural networks"= "convolutional neural networks",
  "cnn"                          = "convolutional neural networks",
  "deep learning"                = "deep learning",
  "machine learning"             = "machine learning",
  "artificial intelligence"      = "artificial intelligence",
  "reinforcement learning"       = "reinforcement learning",
  "genetic algorithm"            = "genetic algorithm",
  "genetic algorithms"           = "genetic algorithm",
  "ga"                           = "genetic algorithm",
  "particle swarm optimization"  = "particle swarm optimization",
  "pso"                          = "particle swarm optimization",
  "swarm intelligence"           = "swarm intelligence",
  "ant colony optimization"      = "ant colony optimization",
  "evolutionary algorithm"       = "evolutionary algorithm",
  "evolutionary algorithms"      = "evolutionary algorithm",
  "bio inspired"                 = "bio-inspired",
  "bioinspired"                  = "bio-inspired",
  "biologically inspired"        = "bio-inspired",
  "bio inspired algorithms"      = "bio-inspired",
  "bio inspired algorithm"       = "bio-inspired",
  "biomimetic"                   = "biomimetics",
  "biomimetics"                  = "biomimetics",
  "biomimicry"                   = "biomimicry",
  "bionic"                       = "bionics",
  "bionics"                      = "bionics",
  "optimisation"                 = "optimization",
  "optimization"                 = "optimization",
  "neuromorphic"                 = "neuromorphic computing",
  "neuromorphic computing"       = "neuromorphic computing",
  "memristor"                    = "memristors",
  "memristors"                   = "memristors",
  "memristive device"            = "memristors",
  "memristive devices"           = "memristors",
  "spiking neural network"       = "spiking neural networks",
  "spiking neural networks"      = "spiking neural networks",
  "soft robot"                   = "soft robotics",
  "soft robots"                  = "soft robotics",
  "soft robotics"                = "soft robotics"
)

harmonize <- function(x) {
  xc <- clean_kw(x)
  ifelse(xc %in% names(keyword_dictionary), keyword_dictionary[xc], xc)
}

generic_terms <- c("model","models","system","systems","method","methods",
                   "approach","performance","simulation","classification",
                   "prediction","behavior","framework","application","applications",
                   "design","analysis","study")

KW_FIELD <- if ("DE" %in% names(M) &&
                mean(!is.na(M$DE) & M$DE != "") > 0.5) "DE" else "ID"
cat("Keyword field used:", KW_FIELD, "\n")

M$doc_id <- seq_len(nrow(M))
kw_long <- M %>%
  select(doc_id, all_of(KW_FIELD), PY) %>%
  rename(kw_raw = all_of(KW_FIELD)) %>%
  filter(!is.na(kw_raw), kw_raw != "") %>%
  separate_rows(kw_raw, sep = ";") %>%
  mutate(keyword = harmonize(kw_raw)) %>%
  filter(keyword != "", nchar(keyword) > 2, toupper(keyword) != "NA") %>%
  distinct(doc_id, keyword, PY)

keyword_freq <- kw_long %>% count(keyword, name = "freq") %>% arrange(desc(freq))
write.csv(keyword_freq, op("keyword_frequency_cleaned.csv"), row.names = FALSE)
cat("Top 15 keywords (cleaned):\n"); print(head(keyword_freq, 15))

## ============================ 07. GOVERNANCE-GAP AUDIT =====================
governance_terms <- c("governance","human in the loop","human oversight",
                      "responsible ai","explainable ai","interpretability",
                      "accountability","ethics","ethical","validation",
                      "evidence based","design methodology","oversight",
                      "transparency","trustworthy ai","human centered")

optimization_terms <- c("optimization","genetic algorithm","particle swarm optimization",
                        "swarm intelligence","ant colony optimization",
                        "evolutionary algorithm","machine learning","deep learning",
                        "neural networks","convolutional neural networks")

count_group <- function(terms) {
  kw_long %>% mutate(kc = clean_kw(keyword)) %>%
    filter(kc %in% terms) %>% nrow()
}

gov_count <- count_group(governance_terms)
opt_count <- count_group(optimization_terms)
total_kw  <- nrow(kw_long)

gap_df <- data.frame(
  category = c("Governance-related", "Optimization/Learning-related", "All keyword tokens"),
  occurrences = c(gov_count, opt_count, total_kw),
  share_pct = round(c(gov_count, opt_count, total_kw) / total_kw * 100, 2)
)
print(gap_df)
write.csv(gap_df, op("governance_gap_audit.csv"), row.names = FALSE)
cat("GOVERNANCE GAP: governance =", gov_count,
    "(", round(gov_count/total_kw*100, 2), "% ) vs optimization/learning =",
    opt_count, "(", round(opt_count/total_kw*100, 2), "% )\n")

## ============================ 08. KEYWORD NETWORK (ggraph) =================
build_pairs <- function(kw_long_df) {
  kw_long_df %>%
    select(doc_id, keyword) %>%
    distinct() %>%
    inner_join(., ., by = "doc_id") %>%
    filter(keyword.x < keyword.y) %>%
    count(keyword.x, keyword.y, name = "weight") %>%
    rename(from = keyword.x, to = keyword.y)
}

pairs_all <- build_pairs(kw_long)

make_kw_network <- function(min_occ, edge_min = 5, top_terms = 40,
                            label_top = 18, drop_generic = TRUE) {
  kf <- keyword_freq
  
  if (drop_generic) {
    kf <- kf %>% filter(!keyword %in% generic_terms)
  }
  
  keep_terms <- kf %>%
    filter(freq >= min_occ) %>%
    slice_max(freq, n = top_terms) %>%
    pull(keyword)
  
  edges <- pairs_all %>%
    filter(from %in% keep_terms, to %in% keep_terms, weight >= edge_min)
  
  if (nrow(edges) == 0) return(NULL)
  
  g <- graph_from_data_frame(edges, directed = FALSE)
  g <- delete_vertices(g, V(g)[degree(g) == 0])
  comp <- components(g)
  g <- induced_subgraph(g, which(comp$membership == which.max(comp$csize)))
  
  V(g)$freq <- kf$freq[match(V(g)$name, kf$keyword)]
  V(g)$freq[is.na(V(g)$freq)] <- 1
  
  cl <- cluster_louvain(g, weights = E(g)$weight)
  V(g)$cluster <- as.factor(membership(cl))
  
  lab_terms <- names(sort(
    setNames(V(g)$freq, V(g)$name),
    decreasing = TRUE
  ))[1:min(label_top, vcount(g))]
  
  V(g)$label <- ifelse(V(g)$name %in% lab_terms, V(g)$name, NA)
  
  g
}

plot_kw_network <- function(g, title) {
  set.seed(42)
  
  ggraph(g, layout = "fr", niter = 2500) +
    geom_edge_link(
      aes(width = weight),
      alpha = 0.08,
      colour = "grey70"
    ) +
    geom_node_point(
      aes(size = freq, colour = cluster),
      alpha = 0.88
    ) +
    geom_node_label(
      aes(label = label, filter = !is.na(label)),
      repel = TRUE,
      size = 3.0,
      label.size = 0.18,
      label.padding = unit(0.16, "lines"),
      label.r = unit(0.12, "lines"),
      fill = scales::alpha("white", 0.88),
      colour = "grey15",
      max.overlaps = Inf,
      force = 12,
      force_pull = 0.05,
      box.padding = 0.8,
      point.padding = 0.55,
      min.segment.length = 0,
      segment.color = "grey55",
      segment.size = 0.25,
      seed = 42,
      na.rm = TRUE
    ) +
    scale_edge_width(range = c(0.15, 1.4), guide = "none") +
    scale_size(range = c(2.4, 8.5), guide = "none") +
    scale_colour_viridis_d(option = "D", name = "Cluster") +
    theme_void(base_size = 12) +
    theme(
      plot.title = element_text(face = "bold", size = 14, hjust = 0.5),
      plot.subtitle = element_text(size = 10.5, color = "grey40", hjust = 0.5),
      legend.position = "right",
      plot.margin = margin(18, 18, 18, 18)
    ) +
    labs(
      title = title,
      subtitle = "Terms harmonized; generic terms removed; nodes sized by occurrence"
    )
}

## ---- Primary keyword network (min occurrence = 30) ----
g30 <- make_kw_network(min_occ = 30, edge_min = 5, top_terms = 70, label_top = 18)

if (!is.null(g30)) {
  p_kw30 <- plot_kw_network(
    g30,
    "Keyword Co-occurrence Network (min occurrence = 30)"
  )
  save_fig(p_kw30, "fig3_keyword_network_min30", width = 13, height = 10)
  if (SHOW_PLOTS) print(p_kw30)
}

## ---- Sensitivity networks (min occurrence = 20 and 50) ----
for (mo in c(20, 50)) {
  label_n <- ifelse(mo == 20, 15, 18)
  top_n   <- ifelse(mo == 20, 65, 70)
  
  g_mo <- make_kw_network(
    min_occ = mo,
    edge_min = 5,
    top_terms = top_n,
    label_top = label_n
  )
  
  if (!is.null(g_mo)) {
    p_mo <- plot_kw_network(
      g_mo,
      paste0("Keyword Co-occurrence Network (min occurrence = ", mo, ")")
    )
    save_fig(p_mo, paste0("figS_keyword_network_min", mo), width = 13, height = 10)
    if (SHOW_PLOTS) print(p_mo)
  }
}

## ---- Temporal overlay (built on g30) ----
kw_year <- kw_long %>%
  group_by(keyword) %>%
  summarise(
    freq = n(),
    avg_year = mean(as.numeric(PY), na.rm = TRUE),
    .groups = "drop"
  ) %>%
  filter(freq >= 30, !keyword %in% generic_terms)

if (!is.null(g30)) {
  V(g30)$avg_year <- kw_year$avg_year[match(V(g30)$name, kw_year$keyword)]
  
  set.seed(42)
  p_overlay <- ggraph(g30, layout = "fr", niter = 2500) +
    geom_edge_link(
      aes(width = weight),
      alpha = 0.06,
      colour = "grey75"
    ) +
    geom_node_point(
      aes(size = freq, colour = avg_year),
      alpha = 0.9
    ) +
    geom_node_label(
      aes(label = label, filter = !is.na(label)),
      repel = TRUE,
      size = 3.0,
      label.size = 0.18,
      label.padding = unit(0.16, "lines"),
      label.r = unit(0.12, "lines"),
      fill = scales::alpha("white", 0.88),
      colour = "grey15",
      max.overlaps = Inf,
      force = 12,
      force_pull = 0.05,
      box.padding = 0.8,
      point.padding = 0.55,
      min.segment.length = 0,
      segment.color = "grey55",
      segment.size = 0.25,
      seed = 42,
      na.rm = TRUE
    ) +
    scale_colour_viridis_c(option = "plasma", name = "Avg. year") +
    scale_size(range = c(2.4, 8.5), guide = "none") +
    scale_edge_width(range = c(0.15, 1.3), guide = "none") +
    theme_void(base_size = 12) +
    theme(
      plot.title = element_text(face = "bold", size = 14, hjust = 0.5),
      plot.subtitle = element_text(size = 10.5, color = "grey40", hjust = 0.5),
      legend.position = "right",
      plot.margin = margin(18, 18, 18, 18)
    ) +
    labs(
      title = "Temporal Overlay of Keyword Co-occurrence",
      subtitle = "Node color encodes mean publication year"
    )
  
  save_fig(p_overlay, "figS_keyword_temporal_overlay", width = 13, height = 10)
  if (SHOW_PLOTS) print(p_overlay)
}

## ---- Top keywords lollipop ----
p_topkw <- keyword_freq %>%
  filter(!keyword %in% generic_terms) %>%
  slice_max(freq, n = 30) %>%
  mutate(keyword = reorder(keyword, freq)) %>%
  ggplot(aes(x = freq, y = keyword)) +
  geom_segment(aes(x = 0, xend = freq, y = keyword, yend = keyword), color = "grey80") +
  geom_point(aes(size = freq), color = "#2C7FB8", alpha = 0.85) +
  scale_size(range = c(3, 9), guide = "none") +
  theme_pub() +
  labs(x = "Frequency", y = NULL, title = "Top 30 Harmonized Keywords")
save_fig(p_topkw, "fig_top_keywords", width = 8, height = 8)
if (SHOW_PLOTS) print(p_topkw)

## ============================ 09. THEMATIC MAP =============================
TM <- tryCatch(
  thematicMap(M, field = KW_FIELD, n = 250, minfreq = 5,
              stemming = FALSE, size = 0.3, repel = TRUE,
              n.labels = 2),
  error = function(e) { cat("Thematic map error:", e$message, "\n"); NULL })

if (!is.null(TM) && !is.null(TM$map)) {
  save_fig(TM$map, "fig2_thematic_map", width = 11, height = 9)
  if (SHOW_PLOTS) print(TM$map)
  if (!is.null(TM$words))
    write.csv(TM$words, op("thematic_clusters.csv"), row.names = FALSE)
} else {
  cat("Thematic map empty; adjust minfreq/n.\n")
}

## ============================ 10. CO-CITATION (WoS-only) ===================
cat("\n--- Co-citation analyses (WoS-only) ---\n")
M_cr <- M_wos
M_cr$PY <- suppressWarnings(as.numeric(M_cr$PY))
M_cr <- M_cr[!is.na(M_cr$PY) & M_cr$PY >= 2015 & M_cr$PY <= 2025, ]

cr_ok <- !is.na(M_cr$CR) & nchar(M_cr$CR) > 10
n_cr <- sum(cr_ok)
cat("WoS records with valid CR (2015-2025):", n_cr, "of", nrow(M_cr),
    "(", round(mean(cr_ok) * 100, 1), "% )\n")

cit <- tryCatch(citations(M_cr, field = "article", sep = ";"),
                error = function(e) { cat("citations() error:", e$message, "\n"); NULL })
if (!is.null(cit)) {
  cited_obj <- if (is.list(cit) && "Cited" %in% names(cit)) cit$Cited else cit
  cited_df <- tryCatch({
    if (inherits(cited_obj, "table")) {
      d <- as.data.frame(cited_obj, stringsAsFactors = FALSE)
      names(d) <- c("reference", "freq")[seq_len(ncol(d))]; d
    } else if (!is.null(names(cited_obj))) {
      data.frame(reference = names(cited_obj),
                 freq = as.numeric(cited_obj), stringsAsFactors = FALSE)
    } else NULL
  }, error = function(e) NULL)
  if (!is.null(cited_df) && nrow(cited_df) > 0) {
    cited_df <- cited_df[order(-cited_df$freq), ]
    write.csv(head(cited_df, 30), op("top_30_cited_references.csv"), row.names = FALSE)
    cat("Top cited references exported.\n")
  }
}

shorten_ref <- function(x) {
  x %>% str_replace_all("\\s+", " ") %>%
    str_replace("^([^,]+),\\s*([^,]+),.*?(\\d{4}).*$", "\\1 \\3") %>%
    str_trim()
}

if (n_cr > 0) {
  M_cr <- metaTagExtraction(M_cr, Field = "CR_SO", sep = ";")
  
  NetCoCitRef <- tryCatch(
    biblioNetwork(M_cr, analysis = "co-citation", network = "references", sep = ";"),
    error = function(e) { cat("Ref co-citation error:", e$message, "\n"); NULL })
  
  if (!is.null(NetCoCitRef)) {
    cat("Raw reference co-citation nodes:", dim(NetCoCitRef)[1], "\n")
    g <- graph_from_adjacency_matrix(NetCoCitRef, mode = "undirected",
                                     weighted = TRUE, diag = FALSE)
    deg  <- degree(g)
    keep <- names(sort(deg, decreasing = TRUE))[1:min(50, length(deg))]
    g_sub <- induced_subgraph(g, keep)
    g_sub <- delete_vertices(g_sub, V(g_sub)[degree(g_sub) == 0])
    
    ## Keep only the largest connected component (remove isolated satellites)
    comp <- components(g_sub)
    g_sub <- induced_subgraph(g_sub, which(comp$membership == which.max(comp$csize)))
    
    cl <- cluster_louvain(g_sub, weights = E(g_sub)$weight)
    V(g_sub)$cluster  <- as.factor(membership(cl))
    V(g_sub)$strength <- strength(g_sub, weights = E(g_sub)$weight)
    V(g_sub)$betweenness <- betweenness(g_sub, weights = 1 / (E(g_sub)$weight + 1e-6))
    
    ## --- Balanced labeling: top-N strongest nodes PER cluster ---
    per_cluster_labels <- 4   # number of labels per knowledge base
    
    node_meta <- data.frame(
      name     = V(g_sub)$name,
      cluster  = as.integer(as.character(V(g_sub)$cluster)),
      strength = V(g_sub)$strength,
      stringsAsFactors = FALSE
    )
    
    lab_nodes <- node_meta %>%
      group_by(cluster) %>%
      slice_max(strength, n = per_cluster_labels, with_ties = FALSE) %>%
      ungroup() %>%
      pull(name)
    
    V(g_sub)$label <- ifelse(
      V(g_sub)$name %in% lab_nodes,
      shorten_ref(V(g_sub)$name),
      NA
    )
    
    cat("Labeled nodes per cluster:\n")
    print(table(node_meta$cluster[node_meta$name %in% lab_nodes]))
    write.csv(igraph::as_data_frame(g_sub, what = "edges"),
              op("cocitation_references_edges_top50.csv"), row.names = FALSE)
    node_tbl <- data.frame(
      reference   = V(g_sub)$name,
      cluster     = V(g_sub)$cluster,
      strength    = round(V(g_sub)$strength, 2),
      betweenness = round(V(g_sub)$betweenness, 2)
    ) %>% arrange(desc(strength))
    write.csv(node_tbl, op("cocitation_references_nodes_top50.csv"), row.names = FALSE)
    
    set.seed(42)
    p_cocit <- ggraph(g_sub, layout = "fr", niter = 3000) +
      geom_edge_link(
        aes(width = weight),
        alpha = 0.07,
        colour = "grey75"
      ) +
      geom_node_point(
        aes(size = strength, colour = cluster),
        alpha = 0.9
      ) +
      geom_node_label(
        aes(label = label, filter = !is.na(label)),
        repel = TRUE,
        size = 3.0,
        label.size = 0.18,
        label.padding = unit(0.16, "lines"),
        label.r = unit(0.12, "lines"),
        fill = scales::alpha("white", 0.90),
        colour = "grey15",
        max.overlaps = Inf,
        force = 14,
        force_pull = 0.04,
        box.padding = 0.9,
        point.padding = 0.65,
        min.segment.length = 0,
        segment.color = "grey55",
        segment.size = 0.25,
        seed = 42,
        na.rm = TRUE
      ) +
      scale_edge_width(range = c(0.15, 1.4), guide = "none") +
      scale_size(range = c(2.4, 8.0), guide = "none") +
      scale_colour_viridis_d(option = "C", name = "Knowledge base") +
      theme_void(base_size = 12) +
      theme(
        plot.title = element_text(face = "bold", size = 14, hjust = 0.5),
        plot.subtitle = element_text(size = 10.5, color = "grey40", hjust = 0.5),
        legend.position = "right",
        plot.margin = margin(18, 18, 18, 18)
      ) +
      labs(
        title = "Reference Co-citation Network (WoS subset)",
        subtitle = "Top 50 co-cited references; representative labels per knowledge base"
      )
    
    save_fig(p_cocit, "fig4_reference_cocitation", width = 13, height = 10)
    if (SHOW_PLOTS) print(p_cocit)
    cat("Highest-betweenness brokers (top 5):\n")
    print(head(node_tbl[order(-node_tbl$betweenness), ], 5))
  }
} else {
  cat("No valid CR; co-citation skipped.\n")
}

## ============================ 11. MANUSCRIPT SUMMARY =======================
cat("\n################################################################\n")
cat("##         MANUSCRIPT-READY SUMMARY (copy for writing)        ##\n")
cat("################################################################\n\n")

cat("=== 1. SCOPE & CORPUS ===\n")
cat("Timespan: 2015-2025 (2026 excluded as incomplete) | Merged corpus:",
    n_docs, "docs |", n_sources, "sources | Authors:", length(res$Authors), "\n")
cat("Excluded 2026 records:", n_2026, "| WoS CR-valid subset:", n_cr, "\n\n")

cat("=== 2. GROWTH ===\n")
cat("2015:", trend_df$Articles[trend_df$Year == 2015],
    "| 2025:", trend_df$Articles[trend_df$Year == 2025],
    "| CAGR (2015-2025):", cagr, "%\n\n")

cat("=== 3. GOVERNANCE GAP ===\n"); print(gap_df); cat("\n")
cat("=== 4. TOP KEYWORDS (cleaned) ===\n"); print(head(keyword_freq, 15)); cat("\n")
cat("=== 5. TOP COUNTRIES ===\n"); print(head(country_prod, 5)); cat("\n")
cat("=== 6. TOP SOURCES ===\n"); print(head(top_sources, 5)); cat("\n")

cat("################################################################\n")
cat("## END OF SUMMARY                                            ##\n")
cat("################################################################\n")

## ============================ 12. SAVE WORKSPACE ===========================
save.image(op("bibliometric_analysis_workspace.RData"))
writeLines(capture.output(sessionInfo()), op("session_info.txt"))

cat("\n=============== PIPELINE COMPLETED SUCCESSFULLY ===============\n")
cat("Merged corpus:", n_docs, "| Sources:", n_sources, "| WoS CR subset:", n_cr, "\n")
cat("Excluded 2026:", n_2026, "| All outputs saved to:", OUTDIR, "\n")
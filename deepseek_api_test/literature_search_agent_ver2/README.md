# 📚 Literature Search Agent

A DeepSeek-powered coding & literature-search assistant built in Python, tailored for a **fluid/solid mechanics PhD workflow**.

- **Git & file operations**: read/write/replace files, full Git workflow (add → commit → push), GitHub SSH setup.
- **Literature search** (free academic APIs, no API key required):
  - Semantic Scholar, OpenAlex, Crossref, arXiv
  - **Semantic Scholar `/paper/search` relevance search** — domain pre-filtered (Engineering/Physics/Mathematics/Materials Science, JournalArticle/Review/Conference), with **query preprocessing** (hyphens & boolean operators auto-stripped)
  - **Rich per-paper metadata**: title, authors, year, publication date, venue, journal, DOI, abstract, **TLDR**, citation + **influential** citation counts, open-access PDF link, fields of study, publication types, **BibTeX**
  - **Exact title match** (`/paper/search/match`): `find_paper_by_title` resolves **exactly ONE paper** from its title with an explicit **`matchScore`** — DOI, BibTeX, open-access PDF and an embedded citation/reference tree in a single call; 404 "Title match not found" handled gracefully
  - **Deep paper details & citation traversal** (`/paper/{id}`): `get_paper_details(deep=True)` resolves **any ID format** (DOI, arXiv, PMID, PMCID, CorpusId, MAG, ACL, URL, S2 sha…) and returns **author analytics** (hIndex, paperCount, affiliations), a **specter_v2 embedding** summary, and **forward/backward citations & references WITH abstracts** — a full citation-snowballing inspection in one call
  - **Specialized discovery filters**: `min_citation_count` (seminal papers), `publication_date_from/to` (recent advances), `venue` (top-venue restriction)
  - **Chained search**: input a root paper (title / DOI / ID) and expand via **citations (forward)** and **references (backward)** across multiple hops (BFS)
  - **Relevance scoring** (title / keywords / abstract + optional full-text intro & conclusion, citation & recency bonuses)
  - **Markdown report generation**
  - **Reference management**: one-click **BibTeX export** (`references.bib`) and **open-access PDF caching** (`papers/`)

---

## 🚀 Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the agent (on Windows, or use:)
python main_agent.py
# Or simply double-click: run_agent.bat
```

When prompted, enter your **DeepSeek API Key** (or set the environment variable `DEEPSEEK_API_KEY`).

> All literature-search APIs are free and require **no key**: Semantic Scholar, OpenAlex, Crossref, arXiv.
> Semantic Scholar's keyless API shares **one key among all unauthenticated users**, so it is frequently rate-limited (HTTP 429) / overloaded (5xx). The agent **auto-retries with exponential backoff + jitter** (honoring `Retry-After`), throttles to ~1 req/s, and falls back to OpenAlex/Crossref/arXiv when S2 gives up. Default retries: **6** (≈ up to 63 s per S2 call under heavy load). Optionally set `S2_API_KEY` for a personal key with much higher limits (see below).

---

## 🔎 Semantic Scholar Relevance Search Integration (`/paper/search`)

The core search tool (`search_literature`) is built around S2's `/paper/search` endpoint with the practices from its API tutorial baked in:

### Query preprocessing (automatic)
- **Hyphens are replaced with spaces** — S2's `/paper/search` supports **no query syntax** and *hyphenated terms yield no matches*. `fluid-structure interaction` → `fluid structure interaction`, `Navier-Stokes` → `Navier Stokes`.
- **Boolean operators (`AND`/`OR`/`NOT`) are dropped** — S2 treats them as plain tokens, which would only pollute the relevance match.
- The agent's system prompt instructs it to always phrase queries as clean natural phrases (no hyphens, no operators), so you can keep typing naturally.

### Domain pre-filtering (defaults, S2)
- `fieldsOfStudy` → `Engineering, Physics, Mathematics, Materials Science`
- `publicationTypes` → `JournalArticle, Review, Conference`
- Both are applied **by default** to keep results on-topic for mechanics research; pass `fields_of_study=[]` / `publication_types=[]` when the topic is interdisciplinary.

### Rich field selection (S2)
Every result now carries high-yield metadata, not just title/abstract:
`title, abstract, authors, year, publicationDate, venue, journal, DOI, citationCount, influentialCitationCount, referenceCount, isOpenAccess, openAccessPdf.url, fieldsOfStudy, publicationTypes, tldr, citationStyles.bibtex`

The **TLDR** + abstract give you dense summaries for fast relevance screening; **BibTeX** enables one-click reference export; **openAccessPdf.url** enables PDF caching.

### Specialized filters (new parameters of `search_literature`)
| Filter | S2 parameter | OpenAlex equivalent |
|---|---|---|
| `min_citation_count=50` | `minCitationCount` | `cited_by_count:>50` |
| `publication_date_from/to` (`YYYY`, `YYYY-MM`, `YYYY-MM-DD`) | `publicationDateOrYear` | `publication_year` (year part) |
| `venue="Journal of Fluid Mechanics,..."` | `venue` | venue names resolved to `locations.source.id` via `/sources` |

Plus two dedicated convenience tools: **`search_seminal_papers`** (minCitationCount ≥ 50 + Review/JournalArticle) and **`search_recent_advances`** (publicationDateOrYear since a given date).

---

## 🎯 Exact Title Match Integration (`/paper/search/match`)

Alongside exploratory keyword search, the agent is also a **precise reference resolver** built on S2's `/paper/search/match` endpoint — it returns **exactly ONE paper**, the closest title match, together with an explicit **`matchScore`**.

### `find_paper_by_title(title, year, venue, min_match_score)`

- **Title as query** — hyphens / boolean operators are auto-stripped exactly like the relevance search.
- **High-fidelity fields in one call**: DOI, `citationStyles` (BibTeX), `openAccessPdf.url`, TLDR, influential citation count, publication types/date/journal — **plus `citations` and `references` subfields**, so a single matched node can seed a citation tree with zero extra API round-trips.
- **Graceful 404 handling** — `"Title match not found"` is reported as an informative message (never a crash); S2 rate-limit / server overload is **distinguished from a genuine miss** via the tracked HTTP status code.
- **`min_match_score` threshold** — guards against false-positive matches: if the closest match's `matchScore` is below your threshold, the agent refuses to return it and suggests refining the title (default `0.0` = accept the closest match).
- **`year` / `venue` filters** — disambiguate editions (e.g. `year="2000"` pins down Pope's *Turbulent Flows*).

### Intent-based routing (exploration ⇄ precision)

| User intent | Example | Tool |
|---|---|---|
| Broad topic discovery | "PINNs for lid-driven cavity flow" | `search_literature` (up to 100 papers, ranked) |
| **Exact lookup** | "Find the paper *Turbulent Flows* by Pope" | `find_paper_by_title` (exactly 1 paper + `matchScore`) |
| BibTeX generation | "I need the BibTeX for …" | `find_paper_by_title` → `save_to_bibtex` |
| Citation-tree expansion | "Walk the lineage of …" | `find_paper_by_title` (embedded refs/cites) → `chain_search` |
| PDF acquisition | "Download the PDF of …" | `find_paper_by_title` → `verify_and_download_pdf` |

The **auto-resolvers also prefer the match endpoint**: `get_paper_details` (title input) and the root-paper resolution used by `chain_search` / `get_citations` / `get_references` now try the exact title match first and only fall back to free-text keyword search on a 404.

### `verify_and_download_pdf(paper_data, directory="papers")`

Verifies the matched paper's `openAccessPdf.url` and downloads it into `papers/` (only real `%PDF` responses are saved; asks for confirmation).

> ⚙️ **API note:** the dotted field `citationStyles.bibtex` is rejected (HTTP 400) by `/paper/search/match` **and** `/paper/{id}`. The agent automatically requests the whole `citationStyles` object on every S2 endpoint and extracts the BibTeX from it — same export, no API error.

---

## 🔬 Deep Paper Details & Citation Traversal (`/paper/{id}`)

The "Details about a paper" endpoint turns the agent into a **citation-graph traverser**: once a paper node is identified, a single call retrieves its full context *plus* its lineage.

### Universal ID resolution

`get_paper_details` accepts every ID format the S2 endpoint supports (plus the other sources):

| Identifier | Example |
|---|---|
| S2 ID | `649def34f8be52c8b66281af98ae884c09aef38b` / `S2:649def…` |
| Corpus / PubMed / PMC / MAG / ACL | `CorpusId:215416146` · `PMID:19872477` · `PMCID:2323736` · `MAG:112218234` · `ACL:W12-3903` |
| DOI | `DOI:10.18653/v1/N18-3011` · `10.1017/CBO9780511840531` · doi.org URLs |
| arXiv | `ARXIV:2106.15928` · arxiv.org abs/pdf URLs |
| URL (S2-supported domains) | `URL:https://…` — semanticscholar.org, arxiv.org, biorxiv.org, aclweb.org, acm.org |
| OpenAlex | `OA:W2741809807` · openalex.org URLs |
| Title | exact title match first, keyword search fallback |

### Deep mode — `get_paper_details(paper_id, deep=True, detail_limit=20)`

Requests **nested subfields** in a single call (Semantic Scholar only):

- **Author analytics** (`authors_detail`): each author's `url`, `paperCount`, `citationCount`, `hIndex`, `affiliations` — cross-reference the leading researchers in your field.
- **Semantic embedding** (`embedding`): an `embedding.specter_v2` summary (model, vector length + preview) — the vector S2 uses for similarity, kept compact.
- **Citation snowballing** (`citations_summary` / `references_summary`): forward citations & backward references **with abstracts** — read how fluid/solid mechanics methodologies evolved (forward) and trace the foundational mathematics/numerics (backward).
- **Payload management**: S2 allows up to 10 MB per response — the agent caps neighbors at `detail_limit` (default 20), truncates abstracts, and summarizes vectors so the reply stays readable.

### Multi-stage research pipeline

1. **Discovery** — `search_literature` / `find_paper_by_title` locate a relevant paper.
2. **Deep inspection** — `get_paper_details(paper_id, deep=True)` retrieves the full context.
3. **Graph traversal** — inspect `citations_summary` (forward) & `references_summary` (backward); expand with `get_citations` / `get_references` / `chain_search`.
4. **Synthesis** — write a Markdown literature review locally, synthesizing abstracts and citation connections (ask first).

---

## 🛡️ Semantic Scholar Rate-Limit Resilience (shared key)

Semantic Scholar's **keyless** API shares a single key among **all unauthenticated users**, so under heavy traffic it frequently answers `HTTP 429` (rate limited) or `5xx` (server overloaded). To make paper searches succeed with high probability, `agent_tools.py` embeds the retry strategy demonstrated in `main.py`:

- **Exponential backoff with retries** — every S2 call (`search`, DOI lookup, citations, references) retries `429`/`5xx` up to **6 times** by default: `1s → 2s → 4s → 8s → 16s → 32s` (≈ 63 s worst case per request).
- **`Retry-After` honored** — if the server specifies when to retry, the agent waits exactly that long instead of guessing.
- **Jitter** — 0–30 % random noise is added to each backoff step so that many clients sharing the key don't all retry at the same instant (avoids the thundering-herd effect).
- **Client-side throttle** — at least ~1.1 s between S2 requests (matching S2's ≈ 1 req/s unauthenticated limit), which prevents many 429s *before* they happen.
- **Network-error retries** — timeouts and connection resets are also retried rather than failing instantly.
- **Graceful degradation** — if S2 still gives up, `search_literature` continues with **OpenAlex / Crossref / arXiv** and dedupes the results, so the paper is still found via another source. `get_paper_details` reports *"S2 is rate-limited/overloaded — try `openalex`/`crossref`/`auto` or retry later"* instead of a misleading "not found".

### Optional personal API key (`S2_API_KEY`)

Set `S2_API_KEY` in the environment and the agent sends it on every S2 call, lifting the shared-key rate limits substantially:

```bash
set S2_API_KEY=your_personal_s2_key      # Windows (cmd)
export S2_API_KEY=your_personal_s2_key   # Linux / macOS
python main_agent.py
```

### Changing the retry count

**At startup (environment variable):**

```bash
set SEMANTIC_SCHOLAR_MAX_RETRIES=10     # Windows (cmd)
export SEMANTIC_SCHOLAR_MAX_RETRIES=10  # Linux / macOS
python main_agent.py
```

**At runtime (just ask the agent):**

> "Set Semantic Scholar retries to 10"

The agent calls the `set_semantic_scholar_max_retries` tool (value is clamped to 1–20) and confirms the new worst-case backoff.

Higher retries → higher success probability under heavy traffic, at the cost of longer worst-case latency. The other APIs (OpenAlex / Crossref / arXiv) use a lighter retry policy (3 attempts).

---

## ⏭️ Confirmation Prompts (y / n / s)

When the agent wants to **write/modify a file**, **execute a PowerShell command**, **append BibTeX entries** (`save_to_bibtex`) or **download PDFs** (`download_paper_pdf` / `verify_and_download_pdf`), it asks for your confirmation:

- `y` → **allow** the operation
- `n` → **deny** the operation (the agent may still continue with other steps of the task)
- `s` → **skip**: deny the current operation **and end the current task** — the agent gives a final response and returns to the `You>` prompt, ready for your next request

---

## ⭐ Optimized Prompt Templates

Replace the `【BRACKETED】` placeholders with your own content. The templates are **consolidated into the six workflows you'll actually use day-to-day**: daily scanning, review shortlists, paper resolution, deep dives, method-evolution narratives, and library building. Each prompt **chains the agent's tools together**; the **one-liners** trigger the same workflow with a single sentence.

> 💡 **Query hygiene (applies to every template):** phrase queries as **plain natural phrases — no hyphens, no AND/OR/NOT** (e.g. `vortex induced vibration` instead of `vortex-induced vibration`). The code auto-strips them anyway, but clean phrases give S2 the best relevance match. Every result includes a **TLDR** — ask the agent to read `tldr`/`abstract` before presenting the final curated list.

> 🎯 **Exploration vs. precision:** for **topic discovery** (e.g. "turbulence modeling for LES") use **Templates 1–2**; for a **specific paper** — a quoted title, "the paper titled …", a BibTeX lookup, or a local PDF filename — the agent routes to `find_paper_by_title` / `get_paper_details`, see **Templates 3–4**.

---

### Template 1 — Daily Scan (stay current on your topic)

Use when you want a **quick daily/weekly update**: the newest papers on your topic plus what's building on your key papers — no report, just the must-reads.

```
Quick daily scan on my topic 【e.g., vortex induced vibration energy harvesting】:
1. search_recent_advances(query=【topic】, date_from=【e.g., 2026-03】, max_results 8)
   → the newest work since that date.
2. search_literature(query=【topic】, sources: semantic_scholar, openalex,
   max_results 5, year_from 【last year】) → the most relevant recent papers.
3. For my key paper 【title or DOI】: get_citations(limit 10) → who is building on it now.
4. Read each tldr/abstract, drop off-topic hits, and show me a compact table:
   Title (+DOI) | first author | year | venue | citations | one-line TLDR.
```

**Why this works:** `search_recent_advances` drives S2's `publicationDateOrYear` filter (only papers since your date), the relevance search is domain pre-filtered (Engineering/Physics/Mathematics/Materials Science, JournalArticle/Review/Conference), and `get_citations` on your key paper surfaces the newest follow-ups — three quick calls give you the whole "what's new" picture with zero noise. Reading each `tldr` lets you decide what deserves a full read.

**One-liners:**
- "What's new on 【topic】 since 【YYYY-MM】?"
- "Who cited my paper 【title】 recently?"

---

### Template 2 — Topic Review Pack (literature-review shortlist)

Use when you need a **ranked, report-ready shortlist** for a review chapter, a proposal, or a submission.

```
I'm writing the literature review for 【e.g., FSI energy harvesting from VIV】.
1. search_literature(query=【e.g., vortex induced vibration piezoelectric energy harvesting】,
   sources: semantic_scholar, openalex, crossref, max_results 15,
   years 【2010】-【2026】, venue (optional): 【e.g., Journal of Fluid Mechanics,
   Physical Review Fluids】).
2. Also find the SEMINAL works: search_seminal_papers(query=【same topic】,
   min_citation_count 50, max_results 8).
3. Merge both sets and score_papers(query=【your thesis focus】,
   emphasis_terms=【your core terms, e.g. vortex-induced vibration, galloping,
   energy harvesting】, fulltext=true if you want intro/conclusion scoring).
4. Read the tldr/abstract of the top hits, drop off-topic ones, and show me the
   top 12 as a table: Title (+DOI) | first authors | year | venue | citations | score.
5. Generate literature_report.md with this research context: 【your thesis context】.
6. Append the ranked papers' BibTeX to references.bib (save_to_bibtex, ask me first).
```

**Why this works:** chains the **discovery** tools (domain-filtered relevance search + optional venue restriction + the `search_seminal_papers` wrapper for classic foundations) with the **ranking** tool (`score_papers` — title ×4, keywords ×2.5, abstract ×1.5, emphasis ×6/4/2, plus a full-text intro/conclusion bonus when `fulltext=true`) and the **output** tools (Markdown report + BibTeX export). One prompt → a submission-ready shortlist covering both foundations and state-of-the-art. If S2 is rate-limited, the pipeline auto-retries (exponential backoff) and falls back to OpenAlex/Crossref.

**One-liners:**
- "Rank the search results for 【topic】 by relevance (emphasis 【terms】) and generate a report."
- "Seminal + recent papers on 【topic】, top 10 each, into literature_report.md."

---

> 💡 **When Semantic Scholar is busy (HTTP 429):** the agent auto-retries with exponential backoff + jitter (default 6 retries, honoring `Retry-After`) and falls back to OpenAlex/Crossref/arXiv — a busy S2 never silently kills a search. If you keep hitting 429s, say *"Set Semantic Scholar retries to 10"* or set a personal key (`set S2_API_KEY=your_key` on Windows / `export S2_API_KEY=your_key`), then re-run.

---

### Template 3 — Resolve a Paper (title/DOI → metadata, BibTeX, PDF)

Use when you have a **specific paper in mind** — verify a citation, get its BibTeX, or grab the PDF. Highest-frequency daily use.

```
Resolve this paper precisely:
1. find_paper_by_title(title=【e.g., Turbulent Flows】, year=【2000, optional to
   disambiguate】, venue=【optional】, min_match_score=【50, optional guard】)
   OR get_paper_details(paper_id=【DOI / arXiv / PMID / URL if you already have it】).
2. Report: matched title + matchScore, DOI, first authors, year, venue/journal,
   citation & influential-citation counts, TLDR, open-access status + PDF link.
3. Append its BibTeX to references.bib via save_to_bibtex (ask me first).
4. If open access, download the PDF into papers/ via verify_and_download_pdf
   (ask me first).
5. If "Title match not found", suggest 2–3 alternative spellings or fall back to
   search_literature for a fuzzy search.
```

**Why this works:** `find_paper_by_title` hits the **precision endpoint** `/paper/search/match` — exactly ONE paper with an explicit `matchScore`, DOI, BibTeX and open-access info in a single call (404 handled gracefully, `min_match_score` guards against wrong matches). `get_paper_details` accepts **any ID format** (DOI, arXiv, PMID, CorpusId, URL, S2 sha…). `save_to_bibtex` + `verify_and_download_pdf` then complete the reference workflow — no manual cross-referencing.

**One-liners:**
- "BibTeX for 【title or DOI】?"
- "What is the DOI of 【title】?"
- "Find and download the PDF of 【title】."

---

### Template 4 — Deep-Dive & Lineage (one key paper → foundations + follow-ups)

Use when you're **reading a key paper** and want its full scholarly context — the authors' credibility, the ideas it builds on, and the work it spawned.

```
Deep-dive into 【title or DOI】:
1. get_paper_details(paper_id=【DOI or any ID】, deep=True, detail_limit=【20】).
2. Summarize: metadata (title, authors, year, venue/journal, TLDR, citations) and
   author analytics (hIndex / paperCount / affiliations of each author).
3. From the references_summary (backward): the 5 most foundational works
   (title, year, DOI).
4. From the citations_summary (forward): the 5 most recent/influential follow-ups
   (title, year, DOI).
5. If I want the full network: chain_search(root_paper=【DOI】, direction both,
   depth 2, limit 30), then score_papers against 【your research demand】.
6. Show a ranked list and generate literature_report.md.
```

**Why this works:** `deep=True` hits the "Details about a paper" endpoint with nested subfields — author analytics (hIndex/paperCount/affiliations), a specter_v2 embedding summary, and citations & references **with abstracts** — all in one payload-compacted call (capped at `detail_limit`). `chain_search` then snowballs the lineage (BFS over citing/cited papers with precision-first title resolution), and `score_papers` ranks what matters to your research.

**One-liners:**
- "Deep-dive into 【DOI】: who are the authors, what does it build on, what cites it?"
- "Expand 【DOI】 2 hops both directions."

---

### Template 5 — Method Evolution Narrative (citation snowballing → written review)

Use when you need a **written synthesis** of how a method or idea evolved — an introduction, a review chapter, or a related-work section.

```
Trace how 【e.g., physics informed neural networks for fluid mechanics】 evolved:
1. Discovery: search_seminal_papers(query=【topic】, min_citation_count 50,
   max_results 3) + search_recent_advances(query=【topic】, date_from 【2 years ago】,
   max_results 3) → pick 3–4 root papers across the timeline.
2. For each root: get_paper_details(paper_id=【DOI】, deep=True).
3. Read each references_summary → the foundational theory/numerics.
4. Read each citations_summary → how the field evolved afterwards.
5. Synthesize a 2–3 paragraph narrative: foundations → key breakthroughs →
   recent directions, citing DOIs inline.
6. Save the narrative to method_evolution.md (write_file, ask me first) and append
   the root papers' BibTeX to references.bib (save_to_bibtex).
```

**Why this works:** deep mode hands the agent each root's lineage **with abstracts**, so it reads the evolution directly from the details endpoint — no guessing. Combining **seminal** (old foundations) and **recent** (state of the art) roots anchors both ends of the timeline, and `write_file` + `save_to_bibtex` leave you with a citable draft — the agent's full pipeline (Discovery → Deep Inspection → Graph Traversal → Synthesis).

**One-liners:**
- "Write a short 'related work' paragraph for 【topic】, citing DOIs."
- "How did 【method】 evolve? Give me the timeline with key papers."

---

### Template 6 — Build Your Library (local PDFs → metadata, renames, BibTeX)

Use when you have a **folder of PDFs** (or a growing reading list) to turn into a properly-annotated, cite-able reference library.

```
Organize my papers:
1. List the files in 【papers/】.
2. For each PDF named by convention (e.g. Pope_2000_Turbulent_Flows.pdf):
   - parse author_year_title from the filename,
   - resolve the real paper with find_paper_by_title(title=【parsed title】,
     year=【parsed year】),
   - report: resolved title, matchScore, DOI, authors, venue, TLDR,
     open-access availability.
3. Propose consistent renames (Author_Year_ShortTitle.pdf) — rename only if I approve.
4. Append all resolved BibTeX entries to references.bib (save_to_bibtex, ask me first).
5. For any open-access results lacking a local PDF, download them into papers/
   (download_paper_pdf, ask me first).
```

**Why this works:** the **exact title-match resolver** turns filename guesses into authoritative metadata (DOI, BibTeX, TLDR, citation counts) — `matchScore` tells you when a filename was too ambiguous to trust — and the **storage workflow** (`save_to_bibtex` + `download_paper_pdf`) archives everything. Your papers folder becomes a curated library with a matching `.bib` file.

**One-liners:**
- "Fix up the metadata for the PDFs in papers/ and export a .bib file."
- "Collect BibTeX for my reading list: 【titles or DOIs】."

---

## 🧠 Tips for getting the best performance

| Goal | Do this | Why |
|---|---|---|
| Better ranking | Give a **rich, specific query** + `emphasis_terms` with your core thesis keywords | Scorer is keyword-based (title ×4, keywords ×2.5, abstract ×1.5, emphasis ×6/4/2) |
| Journal-quality results | Use `sources: semantic_scholar, openalex, crossref` | arXiv returns preprints, not peer-reviewed journal articles |
| Only target journals | Add `venue: "Journal of Fluid Mechanics,..."` to `search_literature` | S2 `venue` filter + OpenAlex source-ID resolution restrict results to your venues |
| Seminal / classic works | `search_seminal_papers` (min_citation_count ≥ 50) | S2 `minCitationCount` + Review/JournalArticle; OpenAlex `cited_by_count:>N` (Template 2) |
| Newest work | `search_recent_advances` (`date_from="2024-01"`) | S2 `publicationDateOrYear` isolates fresh releases (Template 1) |
| Include preprints | Add `arxiv` to sources | Useful for very recent or niche topics |
| Avoid rate limits | Keep `max_results ≤ 20`; avoid many parallel chain hops | S2 ≈ 1 req/s **shared key**; the agent auto-retries with exponential backoff (default 6) and falls back to OpenAlex/Crossref |
| Build a local library | `save_to_bibtex` + `download_paper_pdf` after a search | S2 results carry `citationStyles.bibtex` + `openAccessPdf.url` — one-click export & caching |
| Fast relevance screening | Ask the agent to read each paper's `tldr` before presenting | Every result now includes a dense one-line TLDR from S2 |
| Find a specific paper by exact title | "Find the paper *Turbulent Flows* by Pope" → `find_paper_by_title` | `/paper/search/match` returns exactly 1 paper + `matchScore`; DOI/BibTeX/PDF in one call (Template 3) |
| Guard against wrong matches | Set `min_match_score` (e.g. 50) in `find_paper_by_title` | The agent refuses matches whose `matchScore` falls below the threshold |
| Resolve a known title for a citation tree | `find_paper_by_title` first, then `chain_search` / `get_citations` / `get_references` | Precision-first routing starts the tree from the *correct* paper (Template 4) |
| Organize local PDFs | Parse filenames → `find_paper_by_title` → rename/BibTeX | Turns `Pope_2000_Turbulent_Flows.pdf` into real metadata + `.bib` entries (Template 6) |
| Deep-dive into one paper | `get_paper_details(paper_id, deep=True)` | Author analytics + specter_v2 embedding + citations/references with abstracts in one call (Template 4) |
| Trace how a method evolved | Deep-dive roots → read references/citations summaries → synthesize narrative | Citation snowballing: foundations (backward) → evolution (forward) (Template 5) |
| Resolve any paper ID | Pass DOI / arXiv / PMID / CorpusId / URL / S2 sha to `get_paper_details` | Universal ID resolution covers all S2 formats + OpenAlex + titles |
| Expand a known paper | Use Template 4/5 (`chain_search`, direction both, depth 2) | BFS on citations+references finds work keyword search misses |
| Literature-review chapter | Template 2 (ranked shortlist) + Template 5 (narrative) | Foundations + evolution in one pipeline |
| Fast sanity check | Template 1 (daily scan, 2 sources, no report) | Minimal API calls, quick turnaround |
| S2 keeps rate-limiting | Set env `S2_API_KEY` (personal key) or `SEMANTIC_SCHOLAR_MAX_RETRIES` | A personal key lifts the shared-key limits; more retries → higher success under heavy traffic |

---

## 🛠 Tool Map (what the prompts actually trigger)

| Prompt instruction | Tool executed |
|---|---|
| "Search literature on … sources/max/year" | `search_literature` |
| "… only in venue Journal of Fluid Mechanics, …" | `search_literature(venue=...)` |
| "… with at least N citations" | `search_literature(min_citation_count=N)` |
| "Seminal / classic papers on …" | `search_seminal_papers` |
| "Recent advances / newest work since …" | `search_recent_advances` |
| "Find the paper titled … / exact title / quoted title / BibTeX for …" | `find_paper_by_title` |
| "Details / deep-dive / author analytics / who cites this paper (by ID)" | `get_paper_details(deep=True)` |
| "Verify & download the PDF of this paper" | `verify_and_download_pdf` |
| "Chained search / expand citations & references … depth …" | `chain_search` (BFS) |
| "Papers that cite X" / "forward" | `get_citations` |
| "Papers referenced by X" / "backward" | `get_references` |
| "Rank / score / emphasis terms / fulltext" | `score_papers` |
| "List top N papers" | `list_top_papers` |
| "Generate .md report / literature_report.md / notes" | `generate_markdown_report` |
| "Save / append to references.bib / BibTeX" | `save_to_bibtex` |
| "Download PDFs into papers/ / open-access PDFs" | `download_paper_pdf` |
| "Set Semantic Scholar retries to N" | `set_semantic_scholar_max_retries` |

---

## ⚠️ Notes & Limitations

- **Chained hops** work cleanly through Semantic Scholar (`S2:…`) and OpenAlex (`OA:…`) IDs; Crossref/arXiv nodes are collected but may not re-expand for a third hop.
- **Full-text scoring** depends on open-access availability of the PDF/HTML.
- **BibTeX export** (`save_to_bibtex`) works only for results that came from **Semantic Scholar** (`citationStyles.bibtex`); OpenAlex/Crossref results contribute metadata but no BibTeX string.
- **Title match** (`find_paper_by_title`) returns only the **single closest** match — use `year`/`venue` filters and/or `min_match_score` to guard against wrong papers, and expect a graceful 404 for misspelled or unknown titles.
- **Field compatibility**: the dotted `citationStyles.bibtex` field is rejected (HTTP 400) by `/paper/search/match` **and** `/paper/{id}`; the agent requests the whole `citationStyles` object on all S2 endpoints, so BibTeX export works everywhere.
- **`matchScore` is relative** to the query, not an absolute quality score — a threshold that works for one title may need tuning for another.
- **Deep mode** (`get_paper_details(deep=True)`) is **Semantic Scholar only** — author analytics, the specter_v2 embedding summary, and citations/references-with-abstracts come from S2's `/paper/{id}`; other sources return standard metadata.
- **Payload management**: deep-mode responses are compacted (neighbors capped at `detail_limit`, abstracts truncated, specter_v2 vectors summarized) because S2 permits up to 10 MB per response.
- **PDF download** only saves responses whose content starts with the PDF magic bytes (`%PDF`); paywalled links are skipped and reported.
- **Venue filtering** on OpenAlex resolves display names to source IDs via the `/sources` endpoint (best effort); if a venue can't be resolved it is silently skipped for that source.
- All APIs are free but rate-limited; be patient on large `chain_search` requests (each hop sleeps ~0.8 s). Semantic Scholar calls auto-retry with exponential backoff (default 6 retries, see [🛡️ Semantic Scholar Rate-Limit Resilience](#🛡️-semantic-scholar-rate-limit-resilience-shared-key)).

---

## 📁 Project Files

| File | Purpose |
|---|---|
| `main_agent.py` | Agent entry point: chat loop, tool executor, DeepSeek integration |
| `agent_tools.py` | All tool implementations (Git, files, literature search) + tool schema list |
| `run_agent.bat` | One-click launcher (Windows) |
| `requirements.txt` | Python dependencies |
| `test_report.md` | Example output of a full search → score → report run |

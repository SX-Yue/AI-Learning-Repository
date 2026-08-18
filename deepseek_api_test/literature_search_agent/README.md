# 📚 Literature Search Agent

A DeepSeek-powered coding & literature-search assistant built in Python.

- **Git & file operations**: read/write/replace files, full Git workflow (add → commit → push), GitHub SSH setup.
- **Literature search** (free academic APIs, no API key required):
  - Semantic Scholar, OpenAlex, Crossref, arXiv
  - Keyword search across papers
  - **Chained search**: input a root paper (title / DOI / ID) and expand via **citations (forward)** and **references (backward)** across multiple hops (BFS)
  - Relevance scoring (title / keywords / abstract + optional full-text intro & conclusion, citation & recency bonuses)
  - Markdown report generation

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
> Semantic Scholar rate limit ≈ 1 request/second — the agent already inserts pauses; keep searches focused.

---

## ⏭️ Confirmation Prompts (y / n / s)

When the agent wants to **write/modify a file** or **execute a PowerShell command**, it asks for your confirmation:

- `y` → **allow** the operation
- `n` → **deny** the operation (the agent may still continue with other steps of the task)
- `s` → **skip**: deny the current operation **and end the current task** — the agent gives a final response and returns to the `You>` prompt, ready for your next request

---

## ⭐ Optimized Prompt Templates

The templates below are designed to **trigger the agent's best workflow** — each phrase maps to a specific tool call (see the "Why this works" notes). Replace the `【BRACKETED】` placeholders with your own content.

---

### Template A — Standard literature search (most common)

Use this when you want a ranked, report-ready shortlist on a research topic.

```
I am a PhD student working on 【e.g., fluid-structure interaction energy harvesting】.

Please perform a literature search with the following requirements:
1. Search query: 【e.g., vortex-induced vibration piezoelectric energy harvesting】
   - sources: semantic_scholar, openalex, crossref   (journal-quality work; skip arXiv)
   - max_results: 15
   - year range: 【2015】 to 【2026】
2. Then rank the results with score_papers.
   Emphasis terms (my core thesis keywords, boost them heavily):
   【e.g., vortex-induced vibration, galloping, energy harvesting, piezoelectric】
3. Show me the top 10 papers as a simple list (title + authors + year + venue + score).
4. Finally generate a detailed Markdown report to literature_report.md
   with this research context: 【e.g., my PhD focuses on FSI energy harvesting from VIV at low Reynolds numbers】
```

**Why this works:** the agent's relevance scorer gives title hits ×4, keywords ×2.5, abstract ×1.5, and `emphasis_terms` an extra ×6/×4/×2 boost. A rich query + explicit emphasis terms therefore sharply improve ranking quality. Requesting a `.md` report triggers `generate_markdown_report` (overview table + per-paper details).

---

### Template B — Chained search from a root paper (expand a seed paper)

Use this when you **already have one key paper** and want to snowball it into a broad related-work collection.

```
Here is my root paper:
Title: 【e.g., An accurate model for numerical prediction of piezoelectric energy
       harvesting from fluid structure interaction problems】
DOI (optional): 【10.1088/0964-1726/23/9/095034】

Please do a CHAINED literature search:
1. chain_search with:
   - root_paper: the title above (or the DOI)
   - direction: both          # forward = papers citing it, backward = its references
   - depth: 2                 # 2 hops of BFS expansion
   - limit: 30
   - neighbors_per_hop: 10
2. Explain briefly what the forward (citing) and backward (referenced) clusters contain.
3. Score the collected papers against my research demand:
   【e.g., I want to build a reduced-order FSI model for piezoelectric energy harvesters】
   and list the top 10.
4. Generate literature_report.md from the ranked results.
```

**Why this works:** the agent resolves a title/DOI automatically (title → Semantic Scholar lookup), then runs a BFS over `citations` + `references` with hop/relation tags. `direction: both, depth: 2` is the sweet spot: 1 hop gives direct neighbors, hop 2 reveals "works citing the works that cite you" — a rich, unbiased expansion that plain keyword search cannot produce.

---

### Template C — Forward-only discovery (find the newest work building on a paper)

```
Find papers that cite this paper, then rank them by relevance to me.
Root paper: 【title or DOI】
- direction: forward
- depth: 1, limit: 20
- rank with score_papers; query = 【your research goal】;
  emphasis = 【your core terms】
- show top 5 and save the full list to a markdown report.
```

**Why this works:** `get_citations` / `chain_search(direction="forward")` is the fastest way to find **recent developments** on an older seminal paper — exactly what a literature-review chapter needs.

---

### Template D — Quick scan (no report)

```
Do a quick literature scan on 【topic】:
- sources: semantic_scholar, openalex
- max_results: 10
- list the top 10 papers with title, first authors, year, venue, citations count.
No report needed.
```

**Why this works:** omitting the report step avoids heavy tool calls; specifying only 2 sources halves API latency while still covering journal articles.

---

### Template E — Deep full-text relevance scoring (slowest, highest quality)

Use when you need the most rigorous ranking and don't mind slower execution.

```
Search literature on 【topic】 (max_results 12, all 4 sources, years 2010-2026).
Then score_papers with:
- query: 【your research demand】
- emphasis_terms: 【your core terms】
- fulltext: true      # fetch open-access PDFs/HTML to score intro & conclusion
Generate literature_report.md including research context:
【your thesis context】.
```

**Why this works:** `fulltext=True` makes the agent download open-access full text and add **+2 per matching term** in the introduction and conclusion sections — catching papers whose abstracts are vague but whose body is on-topic.

---

## 🧠 Tips for getting the best performance

| Goal | Do this | Why |
|---|---|---|
| Better ranking | Give a **rich, specific query** + `emphasis_terms` with your core thesis keywords | Scorer is keyword-based (title ×4, keywords ×2.5, abstract ×1.5, emphasis ×6/4/2) |
| Journal-quality results | Use `sources: semantic_scholar, openalex, crossref` | arXiv returns preprints, not peer-reviewed journal articles |
| Include preprints | Add `arxiv` to sources | Useful for very recent or niche topics |
| Avoid rate limits | Keep `max_results ≤ 20`; avoid many parallel chain hops | Semantic Scholar ≈ 1 req/s; the agent sleeps between calls |
| Expand a known paper | Use Template B (`chain_search`, direction both, depth 2) | BFS on citations+references finds work keyword search misses |
| Literature-review chapter | Template C (forward) for newest works + backward for foundations | Mirrors "what came before / what came after" narrative |
| Fast sanity check | Template D (2 sources, no report) | Minimal API calls, quick turnaround |

---

## 🛠 Tool Map (what the prompts actually trigger)

| Prompt instruction | Tool executed |
|---|---|
| "Search literature on … sources/max/year" | `search_literature` |
| "Chained search / expand citations & references … depth …" | `chain_search` (BFS) |
| "Papers that cite X" / "forward" | `get_citations` |
| "Papers referenced by X" / "backward" | `get_references` |
| "Rank / score / emphasis terms / fulltext" | `score_papers` |
| "List top N papers" | `list_top_papers` |
| "Generate .md report / literature_report.md / notes" | `generate_markdown_report` |

---

## ⚠️ Notes & Limitations

- **Chained hops** work cleanly through Semantic Scholar (`S2:…`) and OpenAlex (`OA:…`) IDs; Crossref/arXiv nodes are collected but may not re-expand for a third hop.
- **Full-text scoring** depends on open-access availability of the PDF/HTML.
- All APIs are free but rate-limited; be patient on large `chain_search` requests (each hop sleeps ~0.8 s).

---

## 📁 Project Files

| File | Purpose |
|---|---|
| `main_agent.py` | Agent entry point: chat loop, tool executor, DeepSeek integration |
| `agent_tools.py` | All tool implementations (Git, files, literature search) + tool schema list |
| `run_agent.bat` | One-click launcher (Windows) |
| `requirements.txt` | Python dependencies |
| `test_report.md` | Example output of a full search → score → report run |

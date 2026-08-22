import sys
import json
import os
from pathlib import Path
from openai import OpenAI

# Import all tools
from agent_tools import (
    read_file, write_file, replace_in_file, list_files, execute_powershell,
    git_auto_workflow, git_status, git_add, git_commit, git_push,
    git_pull, git_log, git_branch, git_checkout, git_diff,
    git_clone, git_stash, git_stash_pop, git_reset,
    setup_github_ssh, test_github_connection, configure_git_user,
    search_literature, get_paper_details, get_citations, get_references,
    chain_search, score_papers, list_top_papers, generate_markdown_report,
    search_seminal_papers, search_recent_advances,
    find_paper_by_title, verify_and_download_pdf,
    save_to_bibtex, download_paper_pdf,
    set_semantic_scholar_max_retries,
    agent_tools, is_git_tool, GIT_REPO_PATH, parse_replace_request
)

sys.stdout.reconfigure(encoding='utf-8')

# Color definitions
YELLOW = "\033[93m"
CYAN = "\033[96m"
GREEN = "\033[92m"
DARK_GRAY = "\033[90m"
MAGENTA = "\033[95m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"

# ==================== Configuration ====================

DEFAULT_GIT_PATH = os.environ.get("GIT_REPO_PATH", str(Path.cwd().resolve()))

# ==================== API Configuration ====================

def load_api_key():
    """Smarter API key loading:
    1. Check the DEEPSEEK_API_KEY environment variable first.
    2. Scan the project directory for api-key.env:
       - If found with a valid key → read it and load it into the
         environment automatically.
       - If found but only contains the template placeholder (sk-*) →
         inform the user and ask them to type in the real key.
    3. If api-key.env is NOT found → ask the user to type in the key.
    """
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if api_key:
        return api_key

    env_file = Path.cwd() / "api-key.env"

    if env_file.exists():
        print(f"{GREEN}📄 Found api-key.env, reading API key...{RESET}")
        try:
            for line in env_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                var_name, _, value = line.partition("=")
                var_name = var_name.strip()
                value = value.strip().strip('"').strip("'")
                if var_name == "DEEPSEEK_API_KEY" and value:
                    # Template placeholder found → ask user for the real key
                    if value == "sk-*" or value.startswith("sk-*") or "YOUR" in value.upper():
                        print(f"{YELLOW}⚠️  api-key.env only contains the template placeholder, "
                              f"please enter your real DeepSeek API Key:{RESET}")
                    else:
                        os.environ[var_name] = value
                        print(f"{GREEN}✅ API key loaded from api-key.env{RESET}")
                        return value
        except Exception as e:
            print(f"{RED}⚠️ Failed to read api-key.env: {e}{RESET}")
    else:
        print(f"{YELLOW}🔎 api-key.env not found in {Path.cwd()}, "
              f"please enter your DeepSeek API Key manually.{RESET}")

    # Fallback: ask the user to type in the key
    api_key = input("🔑 Please enter DeepSeek API Key: ").strip()
    if not api_key:
        print(f"{RED}❌ API Key cannot be empty{RESET}")
        exit(1)
    return api_key


API_KEY = load_api_key()

client = OpenAI(
    api_key=API_KEY,
    base_url="https://api.deepseek.com"
)

# ==================== System Prompt ====================

SYSTEM_PROMPT = f"""You are a powerful coding assistant with full file system and Git operation capabilities.

[Repository Information]
- Git Repository Path: {GIT_REPO_PATH}

[Core Features]

1. **Exact Replacement** (Most Used):
   - When the user says "change A to B", use the replace_in_file tool
   - Example: The user says "Change v1.0 to v2.0 in README.md"
   - Call: replace_in_file(filepath="README.md", old_text="v1.0", new_text="v2.0")

2. **Git Workflow** (Automated):
   - When the user says "commit", "push", or "update code", use git_auto_workflow
   - Example: The user says "Commit changes, message is fix bug" 
   - Call: git_auto_workflow(message="Fix bug")
   - Example: The user says "Push code"
   - Call: git_auto_workflow(message="Update code", push=True)

3. **File Operations**:
   - Read file: read_file
   - Write file: write_file (requires user confirmation)
   - Replace content: replace_in_file (requires user confirmation)
   - List directory: list_files

4. **Advanced Git Operations**:
   - Check status: git_status
   - View history: git_log
   - Checkout branch: git_checkout
   - Pull updates: git_pull
   - View differences: git_diff
   - Clone repository: git_clone

5. **GitHub Connection**:
   - Configure SSH: setup_github_ssh
   - Test connection: test_github_connection
   - Configure user: configure_git_user

[Important Rules]
- Think (reasoning process) in English by default, unless the user explicitly asks you to think in another language
- Answer (final response) in English by default, unless the user explicitly asks you to respond in another language
- Git operations are executed automatically (the user trusts you), no confirmation needed
- File writes (write_file) and file modifications (replace_in_file) require user confirmation
- PowerShell commands require user confirmation
- Always inform the user what you are doing
- Try to use dedicated tools; avoid using execute_powershell if possible

[Literature Search (Academic Research)]
You are a domain-expert literature search assistant for a PhD student in continuum
mechanics, turbulence, fluid-structure interaction and structural analysis.
- Search ONLY through these free academic APIs (no API key needed): Semantic Scholar, Crossref, arXiv, OpenAlex.
- QUERY HYGIENE (mandatory for the `query` parameter, per the S2 /paper/search tutorial):
  * Use PLAIN TEXT only — NO boolean operators (AND/OR/NOT), NO hyphens.
  * Replace hyphens with spaces: "fluid-structure interaction" -> "fluid structure interaction".
  * The code auto-strips hyphens/operators, but still formulate clean natural phrases.
- DEFAULT DOMAIN PRE-FILTERING (S2): fieldsOfStudy = Engineering, Physics, Mathematics,
  Materials Science; publicationTypes = JournalArticle, Review, Conference. Pass
  fields_of_study=[] / publication_types=[] to disable when the topic is interdisciplinary.
- EXACT TITLE LOOKUP (S2 /paper/search/match) — INTENT-BASED ROUTING:
  * Use find_paper_by_title(title, year, venue, min_match_score) for PRECISE,
    single-paper retrieval: explicit/quoted paper titles, "find the paper
    titled ...", BibTeX generation, reference resolution, or seeding a
    citation tree from one known paper. Returns exactly ONE paper + matchScore.
  * Use search_literature / search_seminal_papers / search_recent_advances for
    BROAD topic discovery (topics, not titles). Never keyword-search a title
    when the user names a specific paper.
  * Few-shot examples:
    - "Find the paper 'Turbulent Flows' by Pope"            -> find_paper_by_title(title="Turbulent Flows", year="2000")
    - "What is the DOI of 'An accurate model for numerical prediction of
       piezoelectric energy harvesting'?"                   -> find_paper_by_title(...)
    - "Search literature on vortex induced vibration energy harvesting"
                                                             -> search_literature(...)
  * matchScore guards: if the returned match looks wrong, re-run with a more
    distinctive title, add year/venue, or raise min_match_score.
  * 404 "Title match not found" is normal for misspelled/unknown titles —
    fall back to search_literature for a fuzzy keyword search.
- CITATION-TREE FROM A MATCHED TITLE: the find_paper_by_title result already
  embeds citations & references subfields — use them (or get_citations /
  get_references / chain_search on the matched DOI) to walk the lineage.
- DEEP PAPER INSPECTION (S2 'Details about a paper', GET /paper/{id}) —
  MULTI-STAGE RESEARCH PIPELINE:
  * Stage 1 (Discovery): locate a paper with search_literature /
    find_paper_by_title (keyword or exact title).
  * Stage 2 (Deep Inspection): once a paperId/DOI is identified, call
    get_paper_details(paper_id, deep=True) to retrieve the full context —
    author analytics (url, paperCount, citationCount, hIndex, affiliations),
    a specter_v2 embedding summary, and citations & references WITH abstracts.
  * Stage 3 (Graph Traversal): inspect the citations_summary (forward — how
    methodologies evolved) and references_summary (backward — the foundations)
    returned by deep mode; expand further with get_citations / get_references /
    chain_search when needed.
  * Stage 4 (Synthesis): write a Markdown literature review locally with
    write_file, synthesizing abstracts and citation connections (ask first).
  * get_paper_details accepts universal IDs: <sha>/S2:..., CorpusId:...,
    PMID:..., PMCID:..., MAG:..., ACL:..., DOI:..., ARXIV:..., URL:<url>
    (semanticscholar/arxiv/biorxiv/aclweb/acm), OA:<Wid>, or a paper title.
  * Payloads in deep mode are auto-compacted (neighbors capped, vectors
    summarized) so large /paper/{id} responses stay readable.
- AUTOMATED BIBTEX SYNC: after a successful title match, append its BibTeX to
  references.bib via save_to_bibtex(papers_json) (asks for confirmation).
- LOCAL PAPER ORGANIZATION: if the user points at local PDF filenames
  (e.g. "Pope_2000_Turbulent_Flows.pdf"), parse the filename, resolve real
  metadata with find_paper_by_title, and propose renaming/tagging or BibTeX.
- Typical workflow:
  1. search_literature(query, sources=[...], year_from, year_to, min_citation_count,
     publication_date_from/to, venue) → initial candidates (each result now includes
     title, authors, year, venue, journal, DOI, TLDR, abstract, citation + influential
     citation counts, publication types, fields of study, open-access PDF URL, BibTeX).
  2. Specialized discovery:
     - search_seminal_papers(query, min_citation_count=50) → classic/foundational works (Review+JournalArticle)
     - search_recent_advances(query, date_from="2024-01") → newest work via publicationDateOrYear
     - venue= (e.g. "Journal of Fluid Mechanics,Physical Review Fluids") → top-venue filter
  3. (optional) get_citations / get_references / chain_search(root_paper, direction, depth) → chained expansion from a root article the user provides (or you find)
  4. score_papers(query, papers_json, emphasis_terms, fulltext) → relevance ranking (title ×4, keywords ×2.5, abstract ×1.5, emphasis ×6/4/2, citation + recency bonus, intro/conclusion if open-access)
  5. list_top_papers(papers_json, top_n) → show simple title + authors + year list in the command line
  6. If the user asks for a detailed report: generate_markdown_report(query, papers_json, filepath, notes)
  7. Storage workflow (on request):
     - save_to_bibtex(papers_json, filepath="references.bib") → append S2 citationStyles.bibtex entries
     - download_paper_pdf(papers_json, directory="papers", max_papers=5) → cache open-access PDFs
- RELEVANCE FILTERING: before presenting the curated list, read each paper's `tldr` and
  `abstract` and discard clearly off-topic hits.
- STRUCTURED REPORTING: format the final answer with a Markdown-style summary per paper —
  Title (+ S2 link/DOI), first authors, year, venue/journal, citation count, one-line TLDR,
  and PDF link when open access. Always tell the user the number of papers found and present
  the top-ranked ones (title + authors + year).
- Semantic Scholar's keyless API shares ONE key among all unauthenticated users, so it is frequently rate-limited (HTTP 429) / overloaded (5xx). The code auto-retries with exponential backoff + jitter (honoring Retry-After) and throttles to ~1 req/s (default 6 retries ≈ up to ~63 s per S2 call); the pipeline falls back to OpenAlex/Crossref/arXiv when S2 gives up. If the user asks to change the retry count, use the set_semantic_scholar_max_retries tool (env override: SEMANTIC_SCHOLAR_MAX_RETRIES; an optional personal key via env S2_API_KEY lifts the shared-key limits). Keep queries focused.

[Workflow Example]
User: "Change v1.0 to v2.0 in README.md, then commit and push"
Steps:
  1. replace_in_file("README.md", "v1.0", "v2.0")
  2. git_auto_workflow(message="Update version to v2.0")
"""

chat_history = [
    {"role": "system", "content": SYSTEM_PROMPT}
]

# ==================== Context Usage Tracking ====================
# Visualize DeepSeek context-window usage in the chat (same pattern as the
# reference agent git_available_agent_English_ver_context).

# Context window size of the DeepSeek model in tokens (V4 Flash = 1M).
# Adjust CONTEXT_WINDOW if you switch to a model with a different window.
CONTEXT_WINDOW = 1000000

# Token usage of the most recent API response:
# {"prompt_tokens", "completion_tokens", "total_tokens"}
last_usage = None


def _record_usage(response):
    """Store token usage from an API response for the context-usage bar and
    print a compact per-call token line (↑prompt ↓completion · total).
    Returns True if usage info was available."""
    global last_usage
    usage = getattr(response, "usage", None)
    if not usage:
        return False
    last_usage = {
        "prompt_tokens": usage.prompt_tokens,
        "completion_tokens": usage.completion_tokens,
        "total_tokens": usage.total_tokens,
    }
    print(f"{DARK_GRAY}⚡ Tokens: ↑{usage.prompt_tokens:,} ↓{usage.completion_tokens:,} "
          f"· total {usage.total_tokens:,}{RESET}")
    return True


def display_context_usage():
    """Draw a colored progress bar of the current context usage
    (green < 50 %, yellow < 80 %, red ≥ 80 %)."""
    if last_usage and last_usage.get("prompt_tokens"):
        prompt_tokens = last_usage["prompt_tokens"]
        percentage = min(prompt_tokens / CONTEXT_WINDOW * 100, 100.0)
        bar_length = 20
        filled = int(percentage / 100 * bar_length)
        bar = "█" * filled + "░" * (bar_length - filled)
        if percentage < 50:
            color = GREEN
        elif percentage < 80:
            color = YELLOW
        else:
            color = RED
        print(f"{color}📊 Context usage: {percentage:6.1f}% [{bar}] "
              f"({prompt_tokens:,}/{CONTEXT_WINDOW:,} tokens){RESET}")
    else:
        print(f"{DARK_GRAY}📊 Context usage: 0.0% (no conversation yet){RESET}")

# ==================== Skip Operation ====================

class OperationSkipped(Exception):
    """Raised when the user chooses 's' (skip) at a confirmation prompt.
    Denies the requested operation and tells the main loop to ask the AI
    for a final response, then return to the 'You>' prompt."""
    pass

# ==================== Tool Executor ====================

def execute_tool(func_name: str, args: dict) -> str:
    """Unified tool execution entry point"""
    print(f"\n{MAGENTA}🔧 Executing tool: {func_name}{RESET}")
    
    is_git = is_git_tool(func_name)
    
    if args:
        print(f"{DARK_GRAY}Parameters: {json.dumps(args, ensure_ascii=False, indent=2)}{RESET}")
    
    # ==================== Basic Tools ====================
    
    if func_name == "read_file":
        return read_file(args.get("filepath"))
        
    elif func_name == "write_file":
        filepath = args.get("filepath")
        content = args.get("content")
        
        print(f"\n{YELLOW}⚠️  Confirmation required: Write to file{RESET}")
        print(f"📄 File: {filepath}")
        print(f"📝 Content preview: {content[:200]}...")
        
        confirm = input(f"{YELLOW}Allow this operation? (y/n/s - s=skip & return): {RESET}").strip().lower()
        if confirm == 'y':
            return write_file(filepath, content)
        elif confirm == 's':
            raise OperationSkipped()
        else:
            return "❌ Operation cancelled: User declined to write to file"
            
    elif func_name == "replace_in_file":
        # Exact replacement - also writes to file, requires confirmation
        filepath = args.get("filepath")
        old_text = args.get("old_text")
        new_text = args.get("new_text")
        
        print(f"\n{YELLOW}⚠️  Confirmation required: Modify file (replacement){RESET}")
        print(f"📄 File: {filepath}")
        print(f"  Old: {old_text[:100]}{'...' if len(old_text) > 100 else ''}")
        print(f"  New: {new_text[:100]}{'...' if len(new_text) > 100 else ''}")
        
        confirm = input(f"{YELLOW}Allow this operation? (y/n/s - s=skip & return): {RESET}").strip().lower()
        if confirm == 'y':
            print(f"📝 Exact replacement: {filepath}")
            print(f"  Old: {old_text[:50]}{'...' if len(old_text) > 50 else ''}")
            print(f"  New: {new_text[:50]}{'...' if len(new_text) > 50 else ''}")
            return replace_in_file(filepath, old_text, new_text)
        elif confirm == 's':
            raise OperationSkipped()
        else:
            return "❌ Operation cancelled: User declined to modify file"
            
    elif func_name == "list_files":
        return list_files(args.get("directory", "."))
        
    elif func_name == "execute_powershell":
        command = args.get("command")
        timeout = args.get("timeout", 30)
        
        print(f"\n{YELLOW}⚠️  Confirmation required: Execute PowerShell command{RESET}")
        print(f"💻 Command: {command}")
        
        confirm = input(f"{YELLOW}Allow this operation? (y/n/s - s=skip & return): {RESET}").strip().lower()
        if confirm == 'y':
            return execute_powershell(command, timeout)
        elif confirm == 's':
            raise OperationSkipped()
        else:
            return "❌ Operation cancelled: User declined to execute PowerShell command"
    
    # ==================== Git Tools ====================
    
    elif func_name == "git_auto_workflow":
        message = args.get("message", "Update code")
        files = args.get("files", ".")
        push = args.get("push", True)
        print(f"{GREEN}🚀 Starting automated Git workflow...{RESET}")
        return git_auto_workflow(message, files, push)
        
    elif func_name == "git_status":
        return git_status()
        
    elif func_name == "git_add":
        files = args.get("files", ".")
        return git_add(files)
        
    elif func_name == "git_commit":
        return git_commit(args.get("message"))
        
    elif func_name == "git_push":
        remote = args.get("remote", "origin")
        branch = args.get("branch", "")
        return git_push(remote, branch)
        
    elif func_name == "git_pull":
        remote = args.get("remote", "origin")
        branch = args.get("branch", "")
        return git_pull(remote, branch)
        
    elif func_name == "git_log":
        count = args.get("count", 10)
        return git_log(count)
        
    elif func_name == "git_branch":
        return git_branch()
        
    elif func_name == "git_checkout":
        return git_checkout(args.get("branch"))
        
    elif func_name == "git_diff":
        staged = args.get("staged", False)
        return git_diff(staged)
        
    elif func_name == "git_clone":
        repo_url = args.get("repo_url")
        target_dir = args.get("target_dir", "")
        return git_clone(repo_url, target_dir)
        
    elif func_name == "git_stash":
        return git_stash()
        
    elif func_name == "git_stash_pop":
        return git_stash_pop()
        
    elif func_name == "git_reset":
        mode = args.get("mode", "mixed")
        target = args.get("target", "HEAD")
        return git_reset(mode, target)
    
    # ==================== GitHub Connection Tools ====================
    
    elif func_name == "setup_github_ssh":
        return setup_github_ssh()
        
    elif func_name == "test_github_connection":
        return test_github_connection()
        
    elif func_name == "configure_git_user":
        name = args.get("name", "")
        email = args.get("email", "")
        return configure_git_user(name, email)
    
    # ==================== Literature Search Tools ====================
    
    elif func_name == "search_literature":
        return search_literature(
            args.get("query"),
            max_results=args.get("max_results", 10),
            sources=args.get("sources"),
            year_from=args.get("year_from"),
            year_to=args.get("year_to"),
        )
        
    elif func_name == "get_paper_details":
        return get_paper_details(
            args.get("paper_id"),
            source=args.get("source", "auto"),
            deep=args.get("deep", False),
            detail_limit=args.get("detail_limit", 20),
        )
        
    elif func_name == "find_paper_by_title":
        return find_paper_by_title(
            args.get("title"),
            year=args.get("year"),
            venue=args.get("venue"),
            min_match_score=args.get("min_match_score", 0.0),
        )
        
    elif func_name == "verify_and_download_pdf":
        # Downloads a PDF into the repository → requires confirmation (file creation)
        paper_data = args.get("paper_data")
        directory = args.get("directory", "papers")
        
        print(f"\n{YELLOW}⚠️  Confirmation required: Download open-access PDF{RESET}")
        print(f"📂 Directory: {directory}")
        
        confirm = input(f"{YELLOW}Allow this operation? (y/n/s - s=skip & return): {RESET}").strip().lower()
        if confirm == 'y':
            return verify_and_download_pdf(paper_data, directory)
        elif confirm == 's':
            raise OperationSkipped()
        else:
            return "❌ Operation cancelled: User declined to download PDF"
        
    elif func_name == "get_citations":
        return get_citations(args.get("paper_id"), args.get("limit", 20))
        
    elif func_name == "get_references":
        return get_references(args.get("paper_id"), args.get("limit", 20))
        
    elif func_name == "chain_search":
        return chain_search(
            args.get("root_paper"),
            direction=args.get("direction", "both"),
            depth=args.get("depth", 2),
            limit=args.get("limit", 30),
            neighbors_per_hop=args.get("neighbors_per_hop", 10),
        )
        
    elif func_name == "score_papers":
        return score_papers(
            args.get("query"),
            args.get("papers_json"),
            emphasis_terms=args.get("emphasis_terms"),
            fulltext=args.get("fulltext", False),
        )
        
    elif func_name == "list_top_papers":
        return list_top_papers(args.get("papers_json"), args.get("top_n", 10))
        
    elif func_name == "generate_markdown_report":
        return generate_markdown_report(
            args.get("query"),
            args.get("papers_json"),
            filepath=args.get("filepath", "literature_report.md"),
            notes=args.get("notes"),
            top_n=args.get("top_n", 20),
        )
        
    elif func_name == "search_seminal_papers":
        return search_seminal_papers(
            args.get("query"),
            min_citation_count=args.get("min_citation_count", 50),
            max_results=args.get("max_results", 10),
            year_from=args.get("year_from"),
            year_to=args.get("year_to"),
            sources=args.get("sources"),
        )
        
    elif func_name == "search_recent_advances":
        return search_recent_advances(
            args.get("query"),
            date_from=args.get("date_from", "2024-01"),
            max_results=args.get("max_results", 10),
            sources=args.get("sources"),
            venue=args.get("venue"),
        )
        
    elif func_name == "save_to_bibtex":
        # Appends to a local .bib file → requires confirmation (file modification)
        papers_json = args.get("papers_json")
        filepath = args.get("filepath", "references.bib")
        
        print(f"\n{YELLOW}⚠️  Confirmation required: Append BibTeX entries to file{RESET}")
        print(f"📄 File: {filepath}")
        
        confirm = input(f"{YELLOW}Allow this operation? (y/n/s - s=skip & return): {RESET}").strip().lower()
        if confirm == 'y':
            return save_to_bibtex(papers_json, filepath)
        elif confirm == 's':
            raise OperationSkipped()
        else:
            return "❌ Operation cancelled: User declined to append BibTeX entries"
        
    elif func_name == "download_paper_pdf":
        # Downloads PDFs into the repository → requires confirmation (file creation)
        papers_json = args.get("papers_json")
        directory = args.get("directory", "papers")
        max_papers = args.get("max_papers", 5)
        
        print(f"\n{YELLOW}⚠️  Confirmation required: Download open-access PDFs{RESET}")
        print(f"📂 Directory: {directory}  (up to {max_papers} files)")
        
        confirm = input(f"{YELLOW}Allow this operation? (y/n/s - s=skip & return): {RESET}").strip().lower()
        if confirm == 'y':
            return download_paper_pdf(papers_json, directory, max_papers)
        elif confirm == 's':
            raise OperationSkipped()
        else:
            return "❌ Operation cancelled: User declined to download PDFs"
        
    elif func_name == "set_semantic_scholar_max_retries":
        return set_semantic_scholar_max_retries(args.get("value"))
    
    else:
        return f"❌ Error: Unknown tool {func_name}"

# ==================== Main Loop ====================

print(f"""
{BOLD}{GREEN}══════════════════════════════════════════════════════════════{RESET}
{BOLD}{GREEN}   🤖 Git Repository Control + File System Agent{RESET}
{BOLD}{YELLOW}   📁 Repository: {GIT_REPO_PATH}{RESET}
{BOLD}{GREEN}══════════════════════════════════════════════════════════════{RESET}

{BOLD}{CYAN}📘 FILE OPERATIONS{RESET}
  📖 Read        →  "Read config.json"
  🔍 Replace     →  "Change v1.0 to v2.0 in README.md"  ⚠️ requires confirmation
  ✍️ Write       →  "Create file hello.py"  ⚠️ requires confirmation
  📂 List        →  "List files in src/"

{BOLD}{CYAN}🚀 GIT OPERATIONS{RESET}
  💾 Commit      →  "Commit changes, message: fix bug A"
  📊 Status      →  "Check Git status"
  🌿 Branch      →  "Checkout main" / "List branches"
  📜 History     →  "Show last 5 commits"
  🔄 Pull        →  "Pull latest changes"
  🔀 Stash       →  "Stash my changes"

{BOLD}{CYAN}🔑 GITHUB CONNECTION{RESET}
  🔧 SSH Setup   →  "Configure GitHub SSH"
  ✅ Test        →  "Test GitHub connection"
  👤 Identity    →  "Set git user to John / john@example.com"

{BOLD}{CYAN}📚 LITERATURE SEARCH{RESET}
  🔎 Search      →  "Search literature on vortex-induced vibration of cylinders (years 2015-2026)"
  🎯 Title       →  "Find the paper titled 'Turbulent Flows' by Pope (exact match + BibTeX)"
  🔬 Deep        →  "Deep-dive into paper DOI:10.xxxx — author analytics, citations & references"
  ⭐ Seminal     →  "Find the seminal papers on fluid structure interaction (min 50 citations)"
  🆕 Advances    →  "Find the newest work on turbulence modeling since 2024"
  🏛️ Top Venue   →  "Search in Journal of Fluid Mechanics and Physical Review Fluids"
  🔗 Chain       →  "Expand citations/references from root paper DOI:10.xxxx, depth 2"
  🏆 Score       →  "Rank the results by relevance to my thesis topic"
  📋 List        →  "List the top 10 papers (title + authors + year)"
  📝 Report      →  "Generate a detailed .md report of the search results"
  📚 BibTeX      →  "Save the results to references.bib"  ⚠️ requires confirmation
  📄 PDFs        →  "Download the open-access PDFs into papers/"  ⚠️ requires confirmation

{BOLD}{MAGENTA}⚙️  CONTROLS{RESET}
  🚪 exit        →  Quit the agent
  🧹 clear       →  Clear conversation history
  ⏭️ skip        →  At (y/n/s) prompts: deny the operation & return to You>
  📊 usage       →  Context-window bar is shown before every prompt

{BOLD}{DARK_GRAY}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RESET}
""")

while True:
    display_context_usage()
    try:
        user_input = input(f"\n{YELLOW}👤 You{RESET}\n> ")
    except (KeyboardInterrupt, EOFError):
        print(f"\n{YELLOW}👋 Goodbye!{RESET}")
        break

    if user_input.strip().lower() == 'exit':
        print(f"{YELLOW}👋 Goodbye!{RESET}")
        break
    
    if user_input.strip().lower() == 'clear':
        chat_history = [chat_history[0]]  # Keep system prompt
        print(f"{GREEN}🧹 Chat history cleared{RESET}")
        continue

    chat_history.append({"role": "user", "content": user_input})

    # ==================== Tool Calling Loop ====================
    
    while True:
        print(f"{DARK_GRAY}⏳ AI is thinking... (Press Ctrl+C to stop){RESET}")

        try:
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=chat_history,
                tools=agent_tools,
                stream=False,
                extra_body={
                    "thinking": {"type": "enabled"},
                    "reasoning_effort": "high"
                }
            )

            # Record token usage from this response (powers the usage bar)
            _record_usage(response)

            message = response.choices[0].message
            
            # Display AI reasoning process
            ai_thinking = getattr(message, 'reasoning_content', None)
            if ai_thinking is None and hasattr(message, 'model_extra') and message.model_extra:
                ai_thinking = message.model_extra.get('reasoning_content', "")
            
            if ai_thinking:
                print(f"\n{CYAN}💭 AI Reasoning Process:{RESET}")
                print(f"{CYAN}{ai_thinking}{RESET}")

            chat_history.append(message)

            # ==================== Handle Tool Calls ====================
            
            if message.tool_calls:
                skip_remaining = False  # Track if the user has triggered a skip
                
                for tool_call in message.tool_calls:
                    func_name = tool_call.function.name
                    
                    # If a previous tool in this batch was skipped, dummy-fill the rest
                    if skip_remaining:
                        chat_history.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": func_name,
                            "content": f"⏭️ Operation '{func_name}' was aborted because the user skipped a previous step."
                        })
                        continue

                    args = json.loads(tool_call.function.arguments)
                    
                    # Execute tool
                    try:
                        result = execute_tool(func_name, args)
                    except OperationSkipped:
                        print(f"\n{YELLOW}⏭️ Operation skipped by user. Cancelling remaining tools...{RESET}")
                        result = (
                            f"⏭️ Operation '{func_name}' was SKIPPED by the user "
                            f"(they chose 's' = skip). The operation was NOT executed. "
                            f"Give your final response now: acknowledge the skip and "
                            f"briefly summarize what you would have done. "
                            f"Do not call any more tools."
                        )
                        skip_remaining = True
                    
                    # Display results (truncated)
                    result_preview = result[:500] + ("..." if len(result) > 500 else "")
                    print(f"{GREEN}📊 Tool Result:{RESET}")
                    print(f"{GREEN}{result_preview}{RESET}")
                    
                    # Return result to AI
                    chat_history.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": func_name,
                        "content": result
                    })
                
                continue  # Continue loop, let AI decide the next step based on the result
                
            # ==================== Display Final Response ====================
            
            else:
                ai_text = message.content or ""
                print(f"\n{GREEN}🤖 AI Response:{RESET}")
                print(f"{GREEN}{ai_text}{RESET}")
                break

        except KeyboardInterrupt:
            print(f"\n{YELLOW}⏹️  Stopped AI thinking, starting a new conversation turn{RESET}")
            # Rollback orphaned messages to prevent 400 errors
            while chat_history:
                last_msg = chat_history[-1]
                # Handle both dictionary (user) and object (assistant) messages
                role = getattr(last_msg, 'role', None) or last_msg.get('role', '')
                
                if role == "tool":
                    chat_history.pop()
                elif role == "assistant" and getattr(last_msg, 'tool_calls', None):
                    chat_history.pop() # Remove the orphaned tool_calls message
                    break
                elif role == "user":
                    chat_history.pop()
                    break
                else:
                    break
            break

        except Exception as e:
            print(f"\n{RED}❌ Error: {e}{RESET}")
            break
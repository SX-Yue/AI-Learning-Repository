import os
import subprocess
from pathlib import Path
import re
import json
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from collections import deque

try:
    import requests
except ImportError:
    requests = None

try:
    import pypdf
except ImportError:
    pypdf = None

# ==================== Path Security Check ====================

BASE_DIR = Path.cwd().resolve()

def is_safe_path(target_path: str) -> bool:
    try:
        requested_path = Path(target_path).resolve()
        return requested_path.is_relative_to(BASE_DIR)
    except Exception:
        return False

# ==================== Basic File Operations ====================

def read_file(filepath):
    if not is_safe_path(filepath):
        return f"Error: Access denied. You are only allowed to read files within {BASE_DIR}."
    try:
        # Try multiple encodings
        encodings = ['utf-8', 'gbk', 'latin-1']
        for encoding in encodings:
            try:
                with open(filepath, 'r', encoding=encoding) as f:
                    return f.read()
            except UnicodeDecodeError:
                continue
        return f"Error: Cannot decode file with any known encoding"
    except Exception as e:
        return f"Error reading file: {e}"

def write_file(filepath, content):
    if not is_safe_path(filepath):
        return f"Error: Access denied. You are only allowed to modify files within {BASE_DIR}."
    try:
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return f"✅ Successfully wrote to file: {filepath}"
    except Exception as e:
        return f"Error writing file: {e}"

def list_files(directory="."):
    try:
        files = os.listdir(directory)
        result = []
        for f in files:
            path = os.path.join(directory, f)
            if os.path.isdir(path):
                result.append(f"{f}/")
            else:
                result.append(f)
        return "\n".join(result)
    except Exception as e:
        return f"Error listing directory: {e}"

# ==================== Exact Replacement Feature ====================

def replace_in_file(filepath, old_text, new_text):
    """
    Exactly replace file content.
    Supports: ignoring leading/trailing spaces, auto-detecting encoding.
    """
    if not is_safe_path(filepath):
        return f"❌ Permission denied: Cannot modify files outside of {BASE_DIR}"
    
    try:
        content = read_file(filepath)
        if not content.startswith("Error"):
            # Exact replacement
            if old_text in content:
                new_content = content.replace(old_text, new_text)
                write_file(filepath, new_content)
                return f"✅ Replaced: {old_text[:50]} → {new_text[:50]}"
            else:
                # Try ignoring leading/trailing spaces
                old_trim = old_text.strip()
                if old_trim in content:
                    new_content = content.replace(old_trim, new_text.strip())
                    write_file(filepath, new_content)
                    return f"✅ Replaced (ignored spaces): {old_text[:50]} → {new_text[:50]}"
                return f"❌ Content to replace not found: {old_text[:50]}"
        else:
            return content
    except Exception as e:
        return f"❌ Replacement failed: {e}"

# ==================== PowerShell Execution ====================

def execute_powershell(command: str, timeout: int = 30) -> str:
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
            capture_output=True,
            text=True,
            timeout=timeout
        )
        
        output = result.stdout.strip()
        error = result.stderr.strip()
        
        MAX_CHARS = 4000
        if len(output) > MAX_CHARS:
            output = output[:MAX_CHARS] + f"\n\n...[OUTPUT TRUNCATED]..."
        if len(error) > MAX_CHARS:
            error = error[:MAX_CHARS] + f"\n\n...[ERROR TRUNCATED]..."
        
        if result.returncode == 0:
            if not output and not error:
                return "✅ Command executed successfully (no output)"
            return output if not error else f"Output:\n{output}\nWarnings:\n{error}"
        else:
            return f"❌ Command failed (Exit Code {result.returncode}).\nError:\n{error}\nOutput:\n{output}"
            
    except subprocess.TimeoutExpired:
        return f"❌ Command timed out ({timeout} seconds)"
    except Exception as e:
        return f"❌ Execution error: {str(e)}"

# ==================== Core Git Features (From First Version) ====================

# Global Git repository path
GIT_REPO_PATH = os.environ.get("GIT_REPO_PATH", str(Path.cwd().resolve()))

def _git_execute(command: str) -> str:
    """Internal function: Execute Git command"""
    # If the command includes the -C parameter, execute directly; otherwise, append it
    if "-C" in command:
        full_command = f"git {command}"
    else:
        full_command = f"git -C \"{GIT_REPO_PATH}\" {command}"
    return execute_powershell(full_command)

def git_status() -> str:
    """Check Git status"""
    return _git_execute("status")

def git_add(files: str = ".") -> str:
    """Add files to the staging area"""
    return _git_execute(f"add {files}")

def git_commit(message: str) -> str:
    """Commit changes"""
    safe_message = message.replace('"', '\\"').replace("'", "\\'")
    return _git_execute(f'commit -m "{safe_message}"')

def git_push(remote: str = "origin", branch: str = "") -> str:
    """Push to remote"""
    if branch:
        return _git_execute(f"push {remote} {branch}")
    else:
        # Get current branch
        branch_result = _git_execute("branch --show-current")
        if "❌" in branch_result:
            return f"❌ Cannot get current branch: {branch_result}"
        current_branch = branch_result.strip()
        if current_branch and "✅" not in current_branch:
            return _git_execute(f"push {remote} {current_branch}")
        else:
            return _git_execute(f"push {remote}")

def git_pull(remote: str = "origin", branch: str = "") -> str:
    """Pull updates"""
    if branch:
        return _git_execute(f"pull {remote} {branch}")
    else:
        return _git_execute(f"pull {remote}")

def git_log(count: int = 10) -> str:
    """View commit history"""
    return _git_execute(f"log --oneline -{count}")

def git_branch() -> str:
    """View branches"""
    return _git_execute("branch -a")

def git_checkout(branch: str) -> str:
    """Checkout branch"""
    return _git_execute(f"checkout {branch}")

def git_diff(staged: bool = False) -> str:
    """View differences"""
    if staged:
        return _git_execute("diff --staged")
    else:
        return _git_execute("diff")

def git_clone(repo_url: str, target_dir: str = "") -> str:
    """Clone repository"""
    if target_dir:
        return execute_powershell(f"git clone {repo_url} {target_dir}")
    else:
        return execute_powershell(f"git clone {repo_url}")

def git_stash() -> str:
    """Stash changes"""
    return _git_execute("stash")

def git_stash_pop() -> str:
    """Pop stash"""
    return _git_execute("stash pop")

def git_reset(mode: str = "mixed", target: str = "HEAD") -> str:
    """Reset git state"""
    return _git_execute(f"reset --{mode} {target}")

# ==================== Smart Git Workflow (Core of First Version) ====================

def git_auto_workflow(message: str, files: str = ".", push: bool = True) -> str:
    """
    Smart Git Workflow: add → commit → (optional) push
    This is the core feature of the first version.
    """
    results = []
    results.append("🚀 Starting automated Git workflow...")
    results.append("━" * 50)
    
    # 1. Check status
    status = git_status()
    if "❌" in status:
        results.append(f"❌ Status check failed: {status}")
        return "\n".join(results)
    
    results.append(f"📊 Current status:\n{status}")
    results.append("━" * 50)
    
    # 2. Add files
    add_result = git_add(files)
    if "❌" in add_result:
        results.append(f"❌ Failed to add files: {add_result}")
        return "\n".join(results)
    results.append(f"✅ Added: {files}")
    
    # 3. Commit
    commit_result = git_commit(message)
    if "❌" in commit_result:
        results.append(f"❌ Commit failed: {commit_result}")
        # Check if there are no changes to commit
        if "nothing to commit" in commit_result.lower():
            results.append("ℹ️ No changes to commit")
        return "\n".join(results)
    results.append(f"✅ Committed: {message}")
    
    # 4. Push
    if push:
        results.append("📤 Pushing to remote repository...")
        push_result = git_push()
        if "❌" in push_result:
            results.append(f"⚠️ Push failed: {push_result}")
        else:
            results.append(f"✅ Push successful")
    
    results.append("━" * 50)
    results.append("🎉 Workflow completed!")
    return "\n".join(results)

# ==================== GitHub SSH Connection Configuration ====================

def setup_github_ssh() -> str:
    """Configure GitHub SSH connection"""
    results = []
    results.append("🔑 GitHub SSH Configuration")
    results.append("━" * 50)
    
    ssh_dir = Path.home() / ".ssh"
    ssh_dir.mkdir(exist_ok=True)
    
    ssh_key_path = ssh_dir / "id_rsa"
    ssh_pub_path = ssh_dir / "id_rsa.pub"
    
    # Check if key already exists
    if ssh_key_path.exists() and ssh_pub_path.exists():
        results.append("✅ SSH key already exists")
        with open(ssh_pub_path, 'r') as f:
            pub_key = f.read().strip()
        results.append(f"\n📋 Your SSH public key:\n{pub_key}")
        results.append("\n📌 Please add this public key to GitHub:")
        results.append("   Settings → SSH and GPG keys → New SSH Key")
        results.append("   https://github.com/settings/keys")
        return "\n".join(results)
    
    # Generate new key
    email = input("📧 Please enter your GitHub email: ").strip()
    if not email:
        return "❌ Email cannot be empty"
    
    import subprocess
    # Generate key (no password)
    result = subprocess.run(
        f'ssh-keygen -t rsa -b 4096 -C "{email}" -f "{ssh_key_path}" -N "" -q',
        shell=True,
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        return f"❌ Failed to generate key: {result.stderr}"
    
    results.append("✅ SSH key generated successfully")
    
    # Start ssh-agent and add key
    subprocess.run('ssh-agent', shell=True, capture_output=True)
    subprocess.run(f'ssh-add "{ssh_key_path}"', shell=True, capture_output=True)
    results.append("✅ SSH Agent started")
    
    # Display public key
    if ssh_pub_path.exists():
        with open(ssh_pub_path, 'r') as f:
            pub_key = f.read().strip()
        results.append(f"\n📋 Your SSH public key:\n{pub_key}")
        results.append("\n📌 Please add this public key to GitHub:")
        results.append("   Settings → SSH and GPG keys → New SSH Key")
        results.append("   https://github.com/settings/keys")
        
        # Try to copy to clipboard
        try:
            import pyperclip
            pyperclip.copy(pub_key)
            results.append("✅ Public key copied to clipboard!")
        except:
            pass
    
    return "\n".join(results)

def test_github_connection() -> str:
    """Test GitHub connection"""
    result = execute_powershell("ssh -T git@github.com", timeout=10)
    if "successfully authenticated" in result:
        return "✅ GitHub SSH connection successful!\n" + result
    elif "Permission denied" in result:
        return "❌ SSH connection failed (Permission denied). Please check:\n" + result
    else:
        return "❌ SSH connection failed:\n" + result

def configure_git_user(name: str = "", email: str = "") -> str:
    """Configure Git user"""
    results = []
    if not name:
        name = input("Please enter Git username: ").strip()
    if not email:
        email = input("Please enter Git email: ").strip()
    
    if name:
        result = _git_execute(f'config --global user.name "{name}"')
        results.append(f"✅ Username set: {name}")
    if email:
        result = _git_execute(f'config --global user.email "{email}"')
        results.append(f"✅ Email set: {email}")
    
    return "\n".join(results) if results else "No information configured"

# ==================== Command Parsing (From First Version) ====================

def parse_replace_request(user_input: str) -> dict:
    """
    Parse replacement request from user input.
    Supports: change A to B, replace A with B, modify A to B, etc.
    """
    # Detect keywords
    if not any(k in user_input.lower() for k in ['change', 'replace', 'modify', 'swap']):
        return None
    
    # Extract file path
    file_match = re.search(r'([A-Za-z]:[\\/][^\s]+\.\w+)', user_input)
    if not file_match:
        # Try matching relative path
        file_match = re.search(r'([^\s]+\.\w+)', user_input)
    if not file_match:
        return None
    filepath = file_match.group(1)
    
    # Try multiple patterns to extract old → new
    patterns = [
        r'change\s*["\']?([^"\']+)["\']?\s*to\s*["\']?([^"\']+)["\']?',
        r'replace\s*["\']?([^"\']+)["\']?\s*with\s*["\']?([^"\']+)["\']?',
        r'modify\s*["\']?([^"\']+)["\']?\s*to\s*["\']?([^"\']+)["\']?',
        r'change\s*([^\s]+)\s*to\s*([^\s]+)',
        r'replace\s*([^\s]+)\s*with\s*([^\s]+)',
    ]
    
    for pattern in patterns:
        m = re.search(pattern, user_input, re.IGNORECASE)
        if m:
            old_text = m.group(1).strip()
            new_text = m.group(2).strip()
            return {'filepath': filepath, 'old': old_text, 'new': new_text}
    
    return None

# ==================== Literature Search (Free Academic APIs) ====================
# Powered by free, keyless academic APIs: Semantic Scholar, Crossref, arXiv, OpenAlex.
# Designed for a PhD student in fluid/solid mechanics research.

LITERATURE_SOURCES = ["semantic_scholar", "openalex", "crossref", "arxiv"]

_LIT_HEADERS = {
    "User-Agent": "LiteratureSearchAgent/1.0 (academic research; mailto:phd.researcher@example.com)"
}
_LIT_TIMEOUT = 30

SEMANTIC_SCHOLAR_FIELDS = (
    "title,authors,year,venue,abstract,externalIds,openAccessPdf,"
    "citationCount,referenceCount,url,publicationTypes"
)

# --- Internal HTTP helpers ---

def _lit_get(url, params=None, timeout=_LIT_TIMEOUT):
    """Safe HTTP GET. Returns response object or None."""
    if requests is None:
        return None
    try:
        resp = requests.get(url, params=params, headers=_LIT_HEADERS, timeout=timeout)
        resp.raise_for_status()
        return resp
    except Exception:
        return None

def _lit_sleep(seconds=1.2):
    time.sleep(seconds)

def _make_paper(source, **kw):
    """Build a unified paper dict from any API."""
    return {
        "id": kw.get("id", ""),
        "source": source,
        "title": kw.get("title", ""),
        "authors": kw.get("authors", []),
        "year": kw.get("year"),
        "venue": kw.get("venue", ""),
        "abstract": kw.get("abstract", ""),
        "keywords": kw.get("keywords", []),
        "doi": kw.get("doi", ""),
        "citations_count": kw.get("citations_count", 0),
        "references_count": kw.get("references_count", 0),
        "open_access_url": kw.get("open_access_url", ""),
        "url": kw.get("url", ""),
        "source_id": kw.get("source_id", ""),
        "external_ids": kw.get("external_ids", {}),
    }

# ---------- Semantic Scholar ----------

def _s2_item_to_paper(item):
    if not item:
        return None
    authors = [a.get("name", "") for a in (item.get("authors") or [])]
    ext = item.get("externalIds") or {}
    oa = item.get("openAccessPdf") or {}
    return _make_paper(
        "semantic_scholar",
        id="S2:" + str(item.get("paperId", "")),
        source_id=str(item.get("paperId", "")),
        title=item.get("title", ""),
        authors=authors,
        year=item.get("year"),
        venue=item.get("venue", ""),
        abstract=item.get("abstract", ""),
        keywords=[],
        doi=(ext.get("DOI") or ""),
        citations_count=item.get("citationCount", 0),
        references_count=item.get("referenceCount", 0),
        open_access_url=(oa.get("url") or ""),
        url=item.get("url", ""),
        external_ids=ext,
    )

def _s2_search(query, limit, year_from=None, year_to=None):
    url = "https://api.semanticscholar.org/graph/v1/paper/search"
    params = {"query": query, "limit": min(limit, 100), "fields": SEMANTIC_SCHOLAR_FIELDS}
    if year_from or year_to:
        params["year"] = f"{year_from or ''}-{year_to or ''}"
    resp = _lit_get(url, params)
    if resp is None:
        return []
    data = resp.json()
    papers = [_s2_item_to_paper(i) for i in (data.get("data") or [])]
    return [p for p in papers if p]

def _s2_paper_by_id(native_id):
    url = f"https://api.semanticscholar.org/graph/v1/paper/{native_id}"
    resp = _lit_get(url, {"fields": SEMANTIC_SCHOLAR_FIELDS})
    if resp is None:
        return None
    return _s2_item_to_paper(resp.json())

def _s2_citations(native_id, limit=20):
    url = f"https://api.semanticscholar.org/graph/v1/paper/{native_id}/citations"
    resp = _lit_get(url, {"fields": SEMANTIC_SCHOLAR_FIELDS, "limit": min(limit, 100)})
    if resp is None:
        return []
    papers = []
    for d in (resp.json().get("data") or []):
        p = _s2_item_to_paper(d.get("citingPaper") or {})
        if p:
            papers.append(p)
    return papers

def _s2_references(native_id, limit=20):
    url = f"https://api.semanticscholar.org/graph/v1/paper/{native_id}/references"
    resp = _lit_get(url, {"fields": SEMANTIC_SCHOLAR_FIELDS, "limit": min(limit, 100)})
    if resp is None:
        return []
    papers = []
    for d in (resp.json().get("data") or []):
        p = _s2_item_to_paper(d.get("citedPaper") or {})
        if p:
            papers.append(p)
    return papers

# ---------- OpenAlex ----------

def _openalex_abstract(inverted_index):
    """Rebuild abstract text from OpenAlex's inverted index."""
    if not inverted_index:
        return ""
    pos = {}
    for word, idxs in inverted_index.items():
        for i in idxs:
            pos[i] = word
    return " ".join(pos[i] for i in sorted(pos))

def _openalex_item_to_paper(item):
    if not item:
        return None
    authors = [a.get("author", {}).get("display_name", "") for a in (item.get("authorships") or [])]
    abstract = _openalex_abstract(item.get("abstract_inverted_index"))
    oa = item.get("open_access") or {}
    loc = item.get("primary_location") or {}
    src = loc.get("source") or {}
    keywords = [c.get("display_name", "") for c in (item.get("keywords") or [])]
    if not keywords:
        keywords = [c.get("display_name", "") for c in (item.get("concepts") or [])[:5]]
    wid = str(item.get("id", "")).rsplit("/", 1)[-1]
    return _make_paper(
        "openalex",
        id="OA:" + wid,
        source_id=wid,
        title=item.get("title") or item.get("display_name", ""),
        authors=[a for a in authors if a],
        year=item.get("publication_year"),
        venue=(src.get("display_name") or ""),
        abstract=abstract,
        keywords=keywords,
        doi=(item.get("doi") or "").replace("https://doi.org/", ""),
        citations_count=item.get("cited_by_count", 0),
        references_count=item.get("referenced_works_count", 0),
        open_access_url=(oa.get("oa_url") or ""),
        url=item.get("id", ""),
    )

def _openalex_search(query, limit, year_from=None, year_to=None):
    url = "https://api.openalex.org/works"
    params = {"search": query, "per-page": min(limit, 100)}
    filters = []
    if year_from or year_to:
        filters.append(f"publication_year:{year_from or ''}-{year_to or ''}")
    if filters:
        params["filter"] = ",".join(filters)
    resp = _lit_get(url, params)
    if resp is None:
        return []
    papers = [_openalex_item_to_paper(i) for i in (resp.json().get("results") or [])]
    return [p for p in papers if p]

def _openalex_work(wid):
    resp = _lit_get(f"https://api.openalex.org/works/{wid}")
    if resp is None:
        return None
    return _openalex_item_to_paper(resp.json())

def _openalex_by_doi(doi):
    doi = (doi or "").strip().lower()
    if doi.startswith("https://doi.org/"):
        doi = doi[len("https://doi.org/"):]
    if not doi:
        return None
    resp = _lit_get(f"https://api.openalex.org/works/https://doi.org/{doi}")
    if resp is None:
        return None
    return _openalex_item_to_paper(resp.json())

def _openalex_works_batch(ids):
    ids = [i for i in ids if i][:50]
    if not ids:
        return []
    resp = _lit_get("https://api.openalex.org/works",
                    {"filter": "openalex_id:" + "|".join(ids), "per-page": len(ids)})
    if resp is None:
        return []
    papers = [_openalex_item_to_paper(i) for i in (resp.json().get("results") or [])]
    return [p for p in papers if p]

def _openalex_citations(wid, limit=20):
    resp = _lit_get("https://api.openalex.org/works",
                    {"filter": f"cites:{wid}", "per-page": min(limit, 100)})
    if resp is None:
        return []
    papers = [_openalex_item_to_paper(i) for i in (resp.json().get("results") or [])]
    return [p for p in papers if p]

def _openalex_references(wid, limit=20):
    item = _lit_get(f"https://api.openalex.org/works/{wid}")
    if item is None:
        return []
    ref_ids = [str(x).rsplit("/", 1)[-1] for x in (item.json().get("referenced_works") or [])]
    return _openalex_works_batch(ref_ids[:limit])

# ---------- Crossref ----------

def _crossref_item_to_paper(item):
    authors = []
    for a in (item.get("author") or []):
        name = " ".join(x for x in [a.get("given", ""), a.get("family", "")] if x)
        if name:
            authors.append(name)
    year = None
    for k in ("published-print", "published-online", "issued"):
        dp = (item.get(k) or {}).get("date-parts")
        if dp and dp[0]:
            year = dp[0][0]
            break
    abstract = re.sub(r"<[^>]+>", "", item.get("abstract", "") or "").strip()
    oa_url = ""
    for l in (item.get("link") or []):
        if l.get("URL"):
            oa_url = l["URL"]
            break
    keywords = (item.get("subject") or [])[:6]
    return _make_paper(
        "crossref",
        id="CR:" + (item.get("DOI") or ""),
        source_id=item.get("DOI", ""),
        title=(item.get("title") or [""])[0],
        authors=authors,
        year=year,
        venue=(item.get("container-title") or [""])[0],
        abstract=abstract,
        keywords=keywords,
        doi=item.get("DOI", ""),
        citations_count=item.get("is-referenced-by-count", 0),
        references_count=len(item.get("reference") or []),
        open_access_url=oa_url,
        url=item.get("URL", ""),
    )

def _crossref_search(query, limit, year_from=None, year_to=None):
    url = "https://api.crossref.org/works"
    params = {"query": query, "rows": min(limit, 100)}
    filters = []
    if year_from:
        filters.append(f"from-pub-date:{year_from}-01-01")
    if year_to:
        filters.append(f"until-pub-date:{year_to}-12-31")
    if filters:
        params["filter"] = ",".join(filters)
    resp = _lit_get(url, params)
    if resp is None:
        return []
    items = (resp.json().get("message") or {}).get("items") or []
    papers = [_crossref_item_to_paper(i) for i in items]
    return [p for p in papers if p]

def _crossref_by_doi(doi):
    doi = (doi or "").strip().lower().replace("https://doi.org/", "")
    if not doi:
        return None
    resp = _lit_get(f"https://api.crossref.org/works/{doi}")
    if resp is None:
        return None
    return _crossref_item_to_paper(resp.json())

# ---------- arXiv ----------

_ARXIV_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
}

def _arxiv_item_to_paper(entry):
    title = re.sub(r"\s+", " ", (entry.findtext("atom:title", "", _ARXIV_NS) or "").strip())
    abstract = re.sub(r"\s+", " ", (entry.findtext("atom:summary", "", _ARXIV_NS) or "").strip())
    published = entry.findtext("atom:published", "", _ARXIV_NS)
    year = int(published[:4]) if (published and published[:4].isdigit()) else None
    authors = [a.findtext("atom:name", "", _ARXIV_NS).strip() for a in entry.findall("atom:author", _ARXIV_NS)]
    authors = [a for a in authors if a]
    id_url = entry.findtext("atom:id", "", _ARXIV_NS)
    aid = id_url.rsplit("/", 1)[-1]
    pdf_url = ""
    for link in entry.findall("atom:link", _ARXIV_NS):
        if link.attrib.get("title") == "pdf":
            pdf_url = link.attrib.get("href", "")
    doi = entry.findtext("arxiv:doi", "", _ARXIV_NS)
    journal_ref = entry.findtext("arxiv:journal_ref", "", _ARXIV_NS)
    cats = [c.attrib.get("term", "") for c in entry.findall("atom:category", _ARXIV_NS)]
    return _make_paper(
        "arxiv",
        id="ARXIV:" + aid,
        source_id=aid,
        title=title,
        authors=authors,
        year=year,
        venue="arXiv preprint" + (f" ({journal_ref})" if journal_ref else ""),
        abstract=abstract,
        keywords=cats,
        doi=doi or "",
        citations_count=0,
        references_count=0,
        open_access_url=pdf_url or id_url,
        url=id_url,
    )

def _arxiv_search(query, limit, year_from=None, year_to=None):
    url = "http://export.arxiv.org/api/query"
    params = {"search_query": f"all:{query}", "start": 0, "max_results": min(limit, 100)}
    resp = _lit_get(url, params)
    if resp is None:
        return []
    try:
        root = ET.fromstring(resp.text)
    except ET.ParseError:
        return []
    papers = []
    for e in root.findall("atom:entry", _ARXIV_NS):
        p = _arxiv_item_to_paper(e)
        if p:
            if year_from and (p["year"] or 0) < year_from:
                continue
            if year_to and (p["year"] or 0) > year_to:
                continue
            papers.append(p)
    return papers

def _arxiv_by_id(aid):
    aid = (aid or "").strip().lower()
    if not aid:
        return None
    resp = _lit_get(f"http://export.arxiv.org/api/query?id_list={aid}")
    if resp is None:
        return None
    try:
        root = ET.fromstring(resp.text)
    except ET.ParseError:
        return None
    entries = root.findall("atom:entry", _ARXIV_NS)
    return _arxiv_item_to_paper(entries[0]) if entries else None

# ---------- Paper ID resolution ----------

def _resolve_paper_id(paper_id):
    """Parse a user-supplied paper identifier.
    Returns ('s2'|'openalex'|'doi'|'arxiv'|'title', value)."""
    pid = str(paper_id).strip()
    low = pid.lower()
    if low.startswith("s2:") or low.startswith("s2/"):
        v = pid.split(":", 1)[1].strip() if ":" in pid else pid.split("/", 1)[1].strip()
        return ("s2", v)
    if low.startswith("oa:") or "openalex.org" in low:
        v = pid.split(":", 1)[1].strip() if ":" in pid else pid.rsplit("/", 1)[-1].strip()
        return ("openalex", v)
    if low.startswith("arxiv:") or "arxiv.org" in low:
        v = pid.split(":", 1)[1].strip() if ":" in pid else pid.rsplit("/", 1)[-1].strip()
        return ("arxiv", v)
    if low.startswith("doi:") or low.startswith("doi/"):
        v = pid.split(":", 1)[1].strip() if ":" in pid else pid.split("/", 1)[1].strip()
        return ("doi", v)
    m = re.match(r"^10\.\d{4,9}/\S+", low)
    if m:
        return ("doi", m.group(0))
    return ("title", pid)

def _resolve_for_chaining(paper_id):
    """Resolve any paper identifier to a source-specific native id usable for
    citation/reference queries. Returns (source, native_id) or (None, None)."""
    kind, value = _resolve_paper_id(paper_id)
    if kind == "s2":
        return "semantic_scholar", value
    if kind == "openalex":
        return "openalex", value
    if kind == "doi":
        p = _openalex_by_doi(value)
        if p:
            return "openalex", p["source_id"]
        _lit_sleep(0.5)
        p = _s2_paper_by_id("DOI:" + value)
        if p:
            return "semantic_scholar", p["source_id"]
        return None, None
    if kind == "arxiv":
        p = _s2_paper_by_id("arXiv:" + value)
        if p:
            return "semantic_scholar", p["source_id"]
        p = _arxiv_by_id(value)
        if p:
            return "arxiv", p["source_id"]
        return None, None
    # title → search Semantic Scholar
    papers = _s2_search(value, 3)
    if papers:
        return "semantic_scholar", papers[0]["source_id"]
    return None, None

def _fetch_neighbors(source, native_id, rel_type, limit=20):
    """rel_type: 'citations' or 'references'."""
    if source == "semantic_scholar":
        if rel_type == "citations":
            return _s2_citations(native_id, limit)
        return _s2_references(native_id, limit)
    if source == "openalex":
        if rel_type == "citations":
            return _openalex_citations(native_id, limit)
        return _openalex_references(native_id, limit)
    return []

# ---------- Unified public tools ----------

def _dedup_papers(papers):
    seen = set()
    out = []
    for p in papers:
        key = None
        if p.get("doi"):
            key = "doi:" + p["doi"].lower().replace("https://doi.org/", "")
        if not key:
            norm = re.sub(r"[^a-z0-9]", "", (p.get("title") or "").lower())
            if norm:
                key = "title:" + norm
        if not key:
            continue
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out

def _compact_papers(papers, abstract_limit=280):
    out = []
    for p in papers:
        ab = p.get("abstract") or ""
        if len(ab) > abstract_limit:
            ab = ab[:abstract_limit].rstrip() + "..."
        item = {
            "id": p.get("id", ""),
            "source": p.get("source", ""),
            "title": p.get("title", ""),
            "authors": (p.get("authors") or [])[:8],
            "year": p.get("year"),
            "venue": p.get("venue", ""),
            "doi": p.get("doi", ""),
            "keywords": (p.get("keywords") or [])[:8],
            "citations_count": p.get("citations_count", 0),
            "references_count": p.get("references_count", 0),
            "open_access_url": p.get("open_access_url", ""),
            "abstract": ab,
        }
        for k in ("_hop", "_via", "_relation"):
            if k in p:
                item[k] = p[k]
        out.append(item)
    return out

def search_literature(query, max_results=10, sources=None, year_from=None, year_to=None):
    """
    Search academic literature across free APIs: Semantic Scholar, OpenAlex,
    Crossref, arXiv. Returns a JSON object with deduplicated results.
    """
    if requests is None:
        return "❌ The 'requests' library is not installed. Run: pip install requests"
    if sources is None:
        sources = LITERATURE_SOURCES
    if isinstance(sources, str):
        sources = [s.strip() for s in re.split(r"[,;]", sources) if s.strip()]
    valid = set(LITERATURE_SOURCES)
    bad = [s for s in sources if str(s).lower() not in valid]
    if bad:
        return f"❌ Unknown source(s): {', '.join(bad)}. Valid: {', '.join(LITERATURE_SOURCES)}"

    per_source = max(2, int(max_results) // len(sources) + 1)
    all_papers = []
    for src in sources:
        s = str(src).lower()
        try:
            if s == "semantic_scholar":
                all_papers += _s2_search(query, per_source, year_from, year_to)
                _lit_sleep(1.2)
            elif s == "openalex":
                all_papers += _openalex_search(query, per_source, year_from, year_to)
            elif s == "crossref":
                all_papers += _crossref_search(query, per_source, year_from, year_to)
            elif s == "arxiv":
                all_papers += _arxiv_search(query, per_source, year_from, year_to)
        except Exception:
            continue
    papers = _dedup_papers([p for p in all_papers if p])
    summary = {
        "query": query,
        "searched_sources": [str(s).lower() for s in sources],
        "total_unique_found": len(papers),
        "results": _compact_papers(papers),
    }
    return json.dumps(summary, ensure_ascii=False, indent=2)

def get_paper_details(paper_id, source="auto"):
    """
    Fetch full details (title, authors, year, venue, abstract, keywords,
    citation/reference counts, DOI, open-access links) of a single paper.
    Accepts: 'DOI:10.xxx', '10.xxx/yyy', 'S2:paperId', 'OA:Wxxx',
    'ARXIV:2401.00123', an arXiv/OpenAlex URL, or a paper title.
    """
    kind, value = _resolve_paper_id(paper_id)
    paper = None
    try:
        if kind == "s2":
            paper = _s2_paper_by_id(value)
        elif kind == "openalex":
            paper = _openalex_work(value)
        elif kind == "doi":
            paper = _openalex_by_doi(value)
            if paper is None:
                _lit_sleep(0.5)
                paper = _s2_paper_by_id("DOI:" + value)
            if paper is None:
                _lit_sleep(0.5)
                paper = _crossref_by_doi(value)
        elif kind == "arxiv":
            paper = _s2_paper_by_id("arXiv:" + value)
            if paper is None:
                paper = _arxiv_by_id(value)
        else:
            papers = _s2_search(value, 3)
            if papers:
                paper = papers[0]
    except Exception as e:
        return f"❌ Error fetching paper details: {e}"
    if paper is None:
        return f"❌ Paper not found for identifier: {paper_id}"
    return json.dumps(paper, ensure_ascii=False, indent=2)

def get_citations(paper_id, limit=20):
    """Get papers that CITE the given paper (forward chaining). Returns JSON."""
    source, native_id = _resolve_for_chaining(paper_id)
    if source is None:
        return f"❌ Could not resolve paper: {paper_id}"
    papers = _dedup_papers(_fetch_neighbors(source, native_id, "citations", limit))
    return json.dumps({"paper_id": paper_id, "relation": "citations", "total": len(papers),
                       "results": _compact_papers(papers)}, ensure_ascii=False, indent=2)

def get_references(paper_id, limit=20):
    """Get papers REFERENCED by the given paper (backward chaining). Returns JSON."""
    source, native_id = _resolve_for_chaining(paper_id)
    if source is None:
        return f"❌ Could not resolve paper: {paper_id}"
    papers = _dedup_papers(_fetch_neighbors(source, native_id, "references", limit))
    return json.dumps({"paper_id": paper_id, "relation": "references", "total": len(papers),
                       "results": _compact_papers(papers)}, ensure_ascii=False, indent=2)

def chain_search(root_paper, direction="both", depth=2, limit=30, neighbors_per_hop=10):
    """
    Chained literature search starting from a root paper.
    - direction: 'forward' (papers citing the root), 'backward' (references),
                 'both' (default)
    - depth: number of hops to traverse (1 = direct neighbors only)
    - limit: maximum number of unique papers to collect
    Returns JSON with all papers found, tagged with hop distance and source relation.
    """
    source, native_id = _resolve_for_chaining(root_paper)
    if source is None:
        return f"❌ Could not resolve root paper: {root_paper}"

    direction = str(direction).lower()
    if direction not in ("forward", "backward", "both"):
        return f"❌ Invalid direction '{direction}'. Use forward/backward/both."
    try:
        depth = int(depth)
        limit = int(limit)
        neighbors_per_hop = int(neighbors_per_hop)
    except (TypeError, ValueError):
        return "❌ depth/limit/neighbors_per_hop must be integers."

    collected = []
    seen = set()
    node_id = ("S2:" + native_id) if source == "semantic_scholar" else ("OA:" + native_id)
    queue = deque([(node_id, 0)])
    seen.add(f"{source}:{native_id}")

    while queue and len(collected) < limit:
        cur_id, hop = queue.popleft()
        if hop >= depth:
            continue
        src, nid = _resolve_for_chaining(cur_id)
        if src is None:
            continue
        rels = []
        if direction in ("forward", "both"):
            rels.append("citations")
        if direction in ("backward", "both"):
            rels.append("references")
        for rel in rels:
            nbrs = _fetch_neighbors(src, nid, rel, neighbors_per_hop)
            for n in nbrs:
                key = f"{n['source']}:{n['source_id']}"
                if key in seen:
                    continue
                seen.add(key)
                n["_hop"] = hop + 1
                n["_via"] = cur_id
                n["_relation"] = rel
                collected.append(n)
                if hop + 1 < depth:
                    child = ("S2:" + n["source_id"]) if n["source"] == "semantic_scholar" \
                            else ("OA:" + n["source_id"]) if n["source"] == "openalex" else n["id"]
                    queue.append((child, hop + 1))
            _lit_sleep(0.8)
        if len(collected) >= limit:
            break

    collected = _dedup_papers(collected)
    return json.dumps({"root_paper": root_paper, "direction": direction, "depth": depth,
                       "total_unique_found": len(collected),
                       "results": _compact_papers(collected)}, ensure_ascii=False, indent=2)

# ---------- Relevance scoring ----------

_LIT_STOPWORDS = set("""a an the and or but if of to in on for with without at by from
as is are was were be been has have had do does did this that these those it its their
our your we you i they he she not no nor so such than then too very can will would should
could may might about into over under between through during before after above below
again further once here there why how all any both each few more most other some only own
same what when where which who whom whose""".split())

def _extract_query_terms(query):
    tokens = re.findall(r"[a-z0-9][a-z0-9\-\+\.]*", (query or "").lower())
    tokens = [t for t in tokens if t not in _LIT_STOPWORDS and len(t) > 1]
    terms = list(dict.fromkeys(tokens))
    for n in (2, 3):
        for i in range(len(tokens) - n + 1):
            phrase = " ".join(tokens[i:i + n])
            if all(t not in _LIT_STOPWORDS for t in tokens[i:i + n]):
                terms.append(phrase)
    return terms

def _score_single_paper(p, terms, emphasis_terms):
    score = 0.0
    reasons = []
    title = (p.get("title") or "").lower()
    abstract = (p.get("abstract") or "").lower()
    keywords = " ".join(p.get("keywords") or []).lower()

    title_hits, kw_hits, ab_hits = [], [], []
    for t in terms:
        if t and t in title:
            score += 4.0
            title_hits.append(t)
        if t and t in keywords:
            score += 2.5
            kw_hits.append(t)
        if t and t in abstract:
            score += 1.5
            ab_hits.append(t)
    for t in emphasis_terms:
        if t and t in title:
            score += 6.0
            title_hits.append("★" + t)
        if t and t in keywords:
            score += 4.0
            kw_hits.append("★" + t)
        if t and t in abstract:
            score += 2.0
            ab_hits.append("★" + t)

    if title_hits:
        reasons.append("title: " + ", ".join(dict.fromkeys(title_hits))[:120])
    if kw_hits:
        reasons.append("keywords: " + ", ".join(dict.fromkeys(kw_hits))[:120])
    if ab_hits:
        reasons.append("abstract: " + ", ".join(dict.fromkeys(ab_hits))[:120])

    cites = p.get("citations_count") or 0
    if cites > 0:
        score += min(3.0, cites / 200.0)
    year = p.get("year") or 0
    if year >= 2024:
        score += 1.0
    elif year >= 2020:
        score += 0.6
    elif year >= 2015:
        score += 0.3
    return round(score, 2), "; ".join(reasons)

def _fetch_text_from_url(url, max_chars=4000):
    """Fetch readable text from an open-access URL (HTML or PDF, best effort)."""
    if not url or requests is None:
        return ""
    try:
        resp = requests.get(url, headers=_LIT_HEADERS, timeout=20, allow_redirects=True)
        if resp.status_code != 200:
            return ""
        ctype = resp.headers.get("Content-Type", "")
        if "pdf" in ctype.lower() or url.lower().endswith(".pdf"):
            if pypdf is None:
                return ""
            from io import BytesIO
            reader = pypdf.PdfReader(BytesIO(resp.content))
            text = ""
            for page in reader.pages[:8]:
                try:
                    text += (page.extract_text() or "") + "\n"
                except Exception:
                    continue
            return text[:max_chars]
        text = resp.text
        text = re.sub(r"<script.*?</script>", " ", text, flags=re.S | re.I)
        text = re.sub(r"<style.*?</style>", " ", text, flags=re.S | re.I)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text[:max_chars]
    except Exception:
        return ""

def _extract_intro_conclusion(text):
    intro = conclusion = ""
    if not text:
        return intro, conclusion
    low = text.lower()
    for kw in ("introduction", "1. introduction", "1 introduction", "background"):
        i = low.find(kw)
        if i >= 0:
            intro = text[i:i + 600]
            break
    for kw in ("conclusion", "conclusions", "summary and conclusions", "concluding remarks"):
        i = low.find(kw)
        if i >= 0:
            conclusion = text[i:i + 600]
            break
    return intro, conclusion

def score_papers(query, papers_json, emphasis_terms=None, fulltext=False):
    """
    Score & rank papers by relevance to the query.
    Scoring basis: title (×4), keywords (×2.5), abstract (×1.5), emphasis terms
    (×6/×4/×2), citation bonus, recency bonus. If fulltext=True, attempts to
    fetch open-access full text to extract introduction & conclusion for extra scoring.
    papers_json: JSON string from search_literature/chain_search/get_citations/get_references
                 or a Python list of paper dicts.
    Returns JSON with ranked results and per-paper scores + reasons.
    """
    if isinstance(papers_json, str):
        try:
            data = json.loads(papers_json)
        except json.JSONDecodeError:
            return "❌ papers_json is not valid JSON."
        papers = data.get("ranked", data.get("results", data)) if isinstance(data, dict) else data
    else:
        papers = papers_json
    if not isinstance(papers, list) or not papers:
        return "❌ No papers to score."

    terms = _extract_query_terms(query)
    emphasis = _extract_query_terms(emphasis_terms) if emphasis_terms else []

    scored = []
    for p in papers:
        score, reasons = _score_single_paper(p, terms, emphasis)
        intro = conclusion = ""
        if fulltext and p.get("open_access_url"):
            text = _fetch_text_from_url(p["open_access_url"])
            intro, conclusion = _extract_intro_conclusion(text)
            if intro:
                bonus = round(sum(2.0 for t in terms if t and t in intro.lower()), 2)
                if bonus:
                    score += bonus
                    reasons += f"; intro bonus +{bonus}"
            if conclusion:
                bonus = round(sum(2.0 for t in terms if t and t in conclusion.lower()), 2)
                if bonus:
                    score += bonus
                    reasons += f"; conclusion bonus +{bonus}"
        item = dict(p)
        item["relevance_score"] = round(score, 2)
        item["score_reasons"] = reasons
        item["_intro_snippet"] = intro[:400]
        item["_conclusion_snippet"] = conclusion[:400]
        scored.append(item)

    scored.sort(key=lambda x: x["relevance_score"], reverse=True)
    result = {
        "query": query,
        "scoring_terms": terms,
        "emphasis_terms": emphasis,
        "total_scored": len(scored),
        "ranked": [{
            "rank": i + 1,
            "id": p.get("id", ""),
            "title": p.get("title", ""),
            "authors": (p.get("authors") or [])[:8],
            "year": p.get("year"),
            "venue": p.get("venue", ""),
            "doi": p.get("doi", ""),
            "keywords": (p.get("keywords") or [])[:8],
            "citations_count": p.get("citations_count", 0),
            "references_count": p.get("references_count", 0),
            "open_access_url": p.get("open_access_url", ""),
            "relevance_score": p["relevance_score"],
            "score_reasons": p["score_reasons"],
            "abstract": (p.get("abstract") or "")[:400],
            "_intro_snippet": p["_intro_snippet"],
            "_conclusion_snippet": p["_conclusion_snippet"],
        } for i, p in enumerate(scored)],
    }
    return json.dumps(result, ensure_ascii=False, indent=2)

# ---------- Display & report ----------

# Make console output safe on legacy encodings (e.g. GBK on Windows)
try:
    import sys as _sys
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    _sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

def list_top_papers(papers_json, top_n=10):
    """
    Display a simple command-line list of papers (title + authors + year).
    papers_json: JSON string or a Python list of paper dicts.
    """
    if isinstance(papers_json, str):
        try:
            data = json.loads(papers_json)
        except json.JSONDecodeError:
            return "❌ papers_json is not valid JSON."
        papers = data.get("ranked", data.get("results", data)) if isinstance(data, dict) else data
    else:
        papers = papers_json
    if not isinstance(papers, list) or not papers:
        return "No papers to display."
    lines = []
    for i, p in enumerate(papers[:top_n], 1):
        title = p.get("title", "?")
        authors = p.get("authors") or []
        year = p.get("year") or "?"
        score = p.get("relevance_score")
        score_txt = f"  [score: {score}]" if score is not None else ""
        lines.append(f"{i:>3}. {title}{score_txt}")
        lines.append(f"     {', '.join(authors[:6])}{' et al.' if len(authors) > 6 else ''} ({year})")
        doi = p.get("doi")
        if doi:
            lines.append(f"     DOI: {doi}")
    return "\n".join(lines)

def generate_markdown_report(query, papers_json, filepath="literature_report.md", notes=None, top_n=20):
    """
    Generate a highly human-readable Markdown report of the search results.
    - papers_json: JSON from score_papers / search_literature / chain_search
    - filepath: output .md file (written inside the repository)
    - notes: optional research context (e.g., your thesis topic)
    Returns confirmation with file path and a preview.
    """
    if isinstance(papers_json, str):
        try:
            data = json.loads(papers_json)
        except json.JSONDecodeError:
            return "❌ papers_json is not valid JSON."
        papers = data.get("ranked", data.get("results", data)) if isinstance(data, dict) else data
    else:
        papers = papers_json
    if not isinstance(papers, list) or not papers:
        return "❌ No papers to include in the report."

    papers = papers[:top_n]
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    md = []
    md.append("# 📚 Literature Search Report\n")
    md.append(f"> **Query:** `{query}`  ")
    md.append(f"> **Generated:** {now}  ")
    md.append(f"> **Papers included:** {len(papers)}  ")
    if notes:
        md.append(f"> **Research context:** {notes}  ")
    md.append("")
    md.append("---\n")

    md.append("## 📑 Overview (ranked)\n")
    md.append("| # | Title | Authors | Year | Venue | Score |")
    md.append("|---|-------|---------|------|-------|-------|")
    for i, p in enumerate(papers, 1):
        title = (p.get("title") or "?")[:70]
        authors = ", ".join((p.get("authors") or [])[:3])
        if len(p.get("authors") or []) > 3:
            authors += " et al."
        year = p.get("year") or "?"
        venue = (p.get("venue") or "")[:40]
        score = p.get("relevance_score")
        score_txt = f"{score}" if score is not None else "—"
        md.append(f"| {i} | {title} | {authors} | {year} | {venue} | {score_txt} |")
    md.append("")
    md.append("---\n")

    md.append("## 🔬 Paper Details\n")
    for i, p in enumerate(papers, 1):
        title = p.get("title") or "Untitled"
        md.append(f"### {i}. {title}\n")
        authors = p.get("authors") or []
        md.append(f"- **Authors:** {', '.join(authors) if authors else 'N/A'}")
        md.append(f"- **Year:** {p.get('year') or 'N/A'}")
        md.append(f"- **Venue/Journal:** {p.get('venue') or 'N/A'}")
        md.append(f"- **DOI:** {p.get('doi') or 'N/A'}")
        md.append(f"- **Citations:** {p.get('citations_count') or 0} | **References:** {p.get('references_count') or 0}")
        if p.get("relevance_score") is not None:
            md.append(f"- **Relevance score:** {p['relevance_score']}")
            if p.get("score_reasons"):
                md.append(f"- **Why it matches:** {p['score_reasons']}")
        oa = p.get("open_access_url")
        if oa:
            md.append(f"- **Open access:** [{oa}]({oa})")
        url = p.get("url")
        if url and url != oa:
            md.append(f"- **Source page:** [{url}]({url})")
        kw = p.get("keywords")
        if kw:
            md.append(f"- **Keywords:** {', '.join(kw[:10])}")
        md.append("")
        ab = p.get("abstract")
        if ab:
            md.append("**Abstract**")
            md.append("")
            md.append(f"> {ab}\n")
        intro = p.get("_intro_snippet")
        concl = p.get("_conclusion_snippet")
        if intro:
            md.append("**Introduction excerpt**")
            md.append("")
            md.append(f"> {intro}\n")
        if concl:
            md.append("**Conclusion excerpt**")
            md.append("")
            md.append(f"> {concl}\n")
        md.append("---\n")

    md.append("## ℹ️ Methodology")
    md.append("")
    md.append("- Sources: Semantic Scholar, OpenAlex, Crossref, arXiv (free academic APIs, no key required).")
    md.append("- Relevance scored by keyword matching in title / keywords / abstract (plus introduction & conclusion when full text was accessible), with citation and recency bonuses.")
    md.append("- Full-text PDF/HTML parsing is best-effort and depends on open-access availability.")

    content = "\n".join(md)
    result = write_file(filepath, content)
    if result.startswith("✅") or "Successfully wrote" in result:
        preview = "\n".join(md[:18])
        return f"Report written to: {filepath}\n\nReport preview (first 18 lines):\n{preview}"
    return result

# ==================== Tool List (Includes all Git features) ====================

agent_tools = [
    # Basic File Operations
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read file content",
            "parameters": {
                "type": "object",
                "properties": {
                    "filepath": {"type": "string", "description": "File path"}
                },
                "required": ["filepath"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write file content (overwrite mode)",
            "parameters": {
                "type": "object",
                "properties": {
                    "filepath": {"type": "string", "description": "File path"},
                    "content": {"type": "string", "description": "Content to write"}
                },
                "required": ["filepath", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "replace_in_file",
            "description": "[Exact Replacement] Find and replace specified content in a file. Used when the user says 'Change A to B'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filepath": {"type": "string", "description": "File path"},
                    "old_text": {"type": "string", "description": "Old content to find"},
                    "new_text": {"type": "string", "description": "New content to replace with"}
                },
                "required": ["filepath", "old_text", "new_text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List directory contents",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {"type": "string", "description": "Directory path, default is current directory", "default": "."}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "execute_powershell",
            "description": "Execute PowerShell command",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Command to execute"},
                    "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 30}
                },
                "required": ["command"]
            }
        }
    },
    
    # Core Git Features
    {
        "type": "function",
        "function": {
            "name": "git_auto_workflow",
            "description": "[Most Used] Complete Git workflow: automatically executes add → commit → push. Used for committing code, pushing updates, etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "Commit message"},
                    "files": {"type": "string", "description": "Files to add, default is '.'", "default": "."},
                    "push": {"type": "boolean", "description": "Whether to push", "default": True}
                },
                "required": ["message"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_status",
            "description": "Check Git repository status",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_add",
            "description": "Add files to staging area",
            "parameters": {
                "type": "object",
                "properties": {
                    "files": {"type": "string", "description": "Files to add", "default": "."}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_commit",
            "description": "Commit staged changes",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "Commit message"}
                },
                "required": ["message"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_push",
            "description": "Push to remote repository",
            "parameters": {
                "type": "object",
                "properties": {
                    "remote": {"type": "string", "description": "Remote name", "default": "origin"},
                    "branch": {"type": "string", "description": "Branch name"}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_pull",
            "description": "Pull updates from remote",
            "parameters": {
                "type": "object",
                "properties": {
                    "remote": {"type": "string", "description": "Remote name", "default": "origin"},
                    "branch": {"type": "string", "description": "Branch name"}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_log",
            "description": "View commit history",
            "parameters": {
                "type": "object",
                "properties": {
                    "count": {"type": "integer", "description": "Number of commits to display", "default": 10}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_branch",
            "description": "View all branches",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_checkout",
            "description": "Checkout branch",
            "parameters": {
                "type": "object",
                "properties": {
                    "branch": {"type": "string", "description": "Branch name"}
                },
                "required": ["branch"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_diff",
            "description": "View differences",
            "parameters": {
                "type": "object",
                "properties": {
                    "staged": {"type": "boolean", "description": "Whether to view staging area", "default": False}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_clone",
            "description": "Clone remote repository",
            "parameters": {
                "type": "object",
                "properties": {
                    "repo_url": {"type": "string", "description": "Repository URL"},
                    "target_dir": {"type": "string", "description": "Target directory"}
                },
                "required": ["repo_url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_stash",
            "description": "Stash current changes",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_stash_pop",
            "description": "Pop stashed changes",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_reset",
            "description": "Reset Git state",
            "parameters": {
                "type": "object",
                "properties": {
                    "mode": {"type": "string", "description": "Reset mode: soft/mixed/hard", "default": "mixed"},
                    "target": {"type": "string", "description": "Target commit", "default": "HEAD"}
                },
                "required": []
            }
        }
    },
    
    # GitHub Connection Configuration
    {
        "type": "function",
        "function": {
            "name": "setup_github_ssh",
            "description": "Configure GitHub SSH connection (generate key, display public key)",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "test_github_connection",
            "description": "Test if GitHub SSH connection is successful",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "configure_git_user",
            "description": "Configure Git username and email",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Username"},
                    "email": {"type": "string", "description": "Email"}
                },
                "required": []
            }
        }
    },
    
    # Literature Search (Academic APIs: Semantic Scholar, Crossref, arXiv, OpenAlex)
    {
        "type": "function",
        "function": {
            "name": "search_literature",
            "description": "Search academic literature across free academic APIs (Semantic Scholar, OpenAlex, Crossref, arXiv). Returns deduplicated JSON results with title, authors, year, venue, DOI, keywords, abstract, open-access links, citation counts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query, e.g. 'fluid-structure interaction of wind turbine blades'"},
                    "max_results": {"type": "integer", "description": "Maximum number of results (default 10)", "default": 10},
                    "sources": {"type": "array", "items": {"type": "string"}, "description": "Sources to search. Valid: semantic_scholar, openalex, crossref, arxiv", "default": ["semantic_scholar", "openalex", "crossref", "arxiv"]},
                    "year_from": {"type": "integer", "description": "Earliest publication year (optional)"},
                    "year_to": {"type": "integer", "description": "Latest publication year (optional)"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_paper_details",
            "description": "Fetch full details of a single paper (title, authors, year, venue, abstract, keywords, citation/reference counts, DOI, open-access links). Accepts DOI ('10.xxxx/yyy' or 'DOI:10.xxxx'), 'S2:paperId', 'OA:Wxxx', 'ARXIV:2401.00123', URLs, or a paper title.",
            "parameters": {
                "type": "object",
                "properties": {
                    "paper_id": {"type": "string", "description": "Paper identifier: DOI, S2:ID, OA:WID, ARXIV:ID, URL, or title"},
                    "source": {"type": "string", "description": "Source hint (auto/semantic_scholar/openalex/crossref/arxiv)", "default": "auto"}
                },
                "required": ["paper_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_citations",
            "description": "Get papers that CITE the given paper (forward chaining). Use to discover newer works building on a root paper. Returns JSON list.",
            "parameters": {
                "type": "object",
                "properties": {
                    "paper_id": {"type": "string", "description": "Paper identifier (DOI, S2:ID, OA:WID, ARXIV:ID, or title)"},
                    "limit": {"type": "integer", "description": "Max number of citing papers (default 20)", "default": 20}
                },
                "required": ["paper_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_references",
            "description": "Get papers REFERENCED by the given paper (backward chaining). Use to discover the foundational works of a root paper. Returns JSON list.",
            "parameters": {
                "type": "object",
                "properties": {
                    "paper_id": {"type": "string", "description": "Paper identifier (DOI, S2:ID, OA:WID, ARXIV:ID, or title)"},
                    "limit": {"type": "integer", "description": "Max number of referenced papers (default 20)", "default": 20}
                },
                "required": ["paper_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "chain_search",
            "description": "Chained literature search from a root paper: BFS traversal of citations (forward) and/or references (backward) up to N hops. Use to expand a small seed into a broad related-work collection. Returns JSON with hop distances.",
            "parameters": {
                "type": "object",
                "properties": {
                    "root_paper": {"type": "string", "description": "Root paper identifier (DOI, S2:ID, OA:WID, ARXIV:ID, or title)"},
                    "direction": {"type": "string", "description": "forward (citations), backward (references), or both", "default": "both"},
                    "depth": {"type": "integer", "description": "Number of hops to traverse (default 2)", "default": 2},
                    "limit": {"type": "integer", "description": "Maximum unique papers to collect (default 30)", "default": 30},
                    "neighbors_per_hop": {"type": "integer", "description": "Neighbors fetched per hop (default 10)", "default": 10}
                },
                "required": ["root_paper"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "score_papers",
            "description": "Score & rank papers by relevance to the user's research demand. Uses title, keywords, abstract (+ introduction/conclusion from open-access full text if fulltext=True), citation and recency bonuses. Input: the JSON string returned by search_literature/chain_search/get_citations/get_references. Returns ranked JSON.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The user's research demand / search query"},
                    "papers_json": {"type": "string", "description": "JSON string of papers (from search_literature, chain_search, get_citations, get_references)"},
                    "emphasis_terms": {"type": "string", "description": "Comma-separated extra terms to strongly boost (optional)"},
                    "fulltext": {"type": "boolean", "description": "If true, fetch open-access full text to score introduction & conclusion (slower)", "default": False}
                },
                "required": ["query", "papers_json"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_top_papers",
            "description": "Display a simple command-line list of papers: title + authors + year (+ score if available). Input: JSON string from score_papers/search_literature/chain_search.",
            "parameters": {
                "type": "object",
                "properties": {
                    "papers_json": {"type": "string", "description": "JSON string of papers"},
                    "top_n": {"type": "integer", "description": "How many to show (default 10)", "default": 10}
                },
                "required": ["papers_json"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_markdown_report",
            "description": "Generate a highly human-readable Markdown (.md) report of the search results with clear structure: overview table, per-paper details (authors, year, venue, DOI, abstract, keywords, open-access links, relevance score & reasons, intro/conclusion excerpts), methodology. Writes the file inside the repository.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search query / research demand"},
                    "papers_json": {"type": "string", "description": "JSON string of papers (preferably scored by score_papers)"},
                    "filepath": {"type": "string", "description": "Output .md file path (default literature_report.md)", "default": "literature_report.md"},
                    "notes": {"type": "string", "description": "Optional research context to include in the report header"},
                    "top_n": {"type": "integer", "description": "Max papers to include (default 20)", "default": 20}
                },
                "required": ["query", "papers_json"]
            }
        }
    }
]

# Tag Git tools (auto-execute, no confirmation needed)
GIT_TOOL_NAMES = {
    "git_auto_workflow", "git_status", "git_add", "git_commit", 
    "git_push", "git_pull", "git_log", "git_branch", "git_checkout",
    "git_diff", "git_clone", "git_stash", "git_stash_pop", "git_reset",
    "setup_github_ssh", "test_github_connection", "configure_git_user"
}

def is_git_tool(func_name: str) -> bool:
    return func_name in GIT_TOOL_NAMES
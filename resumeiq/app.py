import os
import json
import sqlite3
import io
import re
from flask import Flask, render_template, request, jsonify, send_file, g
from werkzeug.utils import secure_filename
import PyPDF2
import docx
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from google import genai
from google.genai import types
import nltk
from nltk import pos_tag, word_tokenize
from nltk.chunk import RegexpParser

# ── Download NLTK data once at startup ────────────────────
for _d in [
    "punkt",
    "punkt_tab",
    "averaged_perceptron_tagger",
    "averaged_perceptron_tagger_eng",
    "stopwords",
]:
    try:
        nltk.download(_d, quiet=True)
    except Exception:
        pass

try:
    from nltk.corpus import stopwords as _nltk_sw

    _NLTK_STOPS = set(_nltk_sw.words("english"))
except Exception:
    _NLTK_STOPS = set()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SESSION_SECRET", "resumeiq-secret-key")
app.config["UPLOAD_FOLDER"] = os.path.join(os.path.dirname(__file__), "uploads")
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024
app.config["DATABASE"] = os.path.join(os.path.dirname(__file__), "database.db")

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

ALLOWED_EXTENSIONS = {"pdf", "docx"}

# Configure Gemini
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
gemini_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(app.config["DATABASE"])
        db.row_factory = sqlite3.Row
    return db


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()


def init_db():
    with app.app_context():
        db = get_db()
        db.execute("""
            CREATE TABLE IF NOT EXISTS resumes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                data TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS ats_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_title TEXT NOT NULL,
                company TEXT,
                resume_name TEXT,
                score_data TEXT NOT NULL,
                job_description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS job_applications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_title TEXT NOT NULL,
                company TEXT NOT NULL,
                job_url TEXT,
                status TEXT DEFAULT 'saved',
                applied_date TEXT,
                ats_score INTEGER,
                ats_report_id INTEGER,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        db.commit()


def extract_text_from_pdf(file_path):
    text = ""
    with open(file_path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        for page in reader.pages:
            text += page.extract_text() or ""
    return text


def extract_text_from_docx(file_path):
    doc = docx.Document(file_path)
    return "\n".join([para.text for para in doc.paragraphs])


# ══════════════════════════════════════════════════════════
#  NLP KEYWORD EXTRACTION
# ══════════════════════════════════════════════════════════

# Comprehensive stop-word set: NLTK base + domain additions
FULL_STOP_WORDS = _NLTK_STOPS | {
    # Generic JD / HR language
    "work",
    "working",
    "role",
    "position",
    "candidate",
    "team",
    "company",
    "organization",
    "employer",
    "employee",
    "individual",
    "person",
    "opportunity",
    "job",
    "career",
    "hire",
    "hiring",
    "recruit",
    "apply",
    "application",
    "applicant",
    "responsible",
    "responsibility",
    "responsibilities",
    "required",
    "requirement",
    "requirements",
    "preferred",
    "desired",
    "must",
    "include",
    "including",
    "etc",
    # Generic descriptors
    "strong",
    "excellent",
    "good",
    "great",
    "exceptional",
    "outstanding",
    "effective",
    "efficient",
    "successful",
    "proven",
    "demonstrated",
    "relevant",
    "related",
    "similar",
    "equivalent",
    "appropriate",
    # Generic nouns
    "experience",
    "skill",
    "skills",
    "ability",
    "abilities",
    "knowledge",
    "understanding",
    "background",
    "familiarity",
    "proficiency",
    "expertise",
    "year",
    "years",
    "month",
    "months",
    "time",
    "day",
    "week",
    "level",
    "field",
    "area",
    "domain",
    "industry",
    "sector",
    "market",
    "project",
    "task",
    "function",
    "process",
    "result",
    "goal",
    "objective",
    "value",
    "benefit",
    "impact",
    "outcome",
    # Soft-skill filler (not technical)
    "communication",
    "leadership",
    "collaboration",
    "teamwork",
    "creativity",
    "innovation",
    "initiative",
    "motivation",
    "problem",
    "solving",
    "thinking",
    "analytical",
    "detail",
    "oriented",
    "organized",
    "proactive",
    "flexible",
    "adaptable",
    "passionate",
    "driven",
    "dedicated",
    "committed",
    # Common JD action verbs (not tech skills)
    "develop",
    "developing",
    "build",
    "building",
    "create",
    "creating",
    "design",
    "designing",
    "implement",
    "implementing",
    "deliver",
    "manage",
    "managing",
    "lead",
    "leading",
    "support",
    "supporting",
    "maintain",
    "maintaining",
    "improve",
    "improving",
    "ensure",
    "provide",
    "providing",
    "help",
    "helping",
    "use",
    "using",
    "utilize",
    "perform",
    "execute",
    "contribute",
    "participate",
    "coordinate",
    # Miscellaneous fillers
    "plus",
    "also",
    "well",
    "high",
    "low",
    "new",
    "best",
    "large",
    "small",
    "fast",
    "complex",
    "multiple",
    "various",
    "different",
    "other",
    "additional",
    "general",
    "specific",
    "key",
    "main",
    "primary",
    "major",
    "minor",
    "overall",
    "basic",
    "advanced",
    "cross",
    "remote",
    "hybrid",
    "onsite",
    "office",
    "location",
}

# Non-technical / administrative acronyms — do NOT extract these
GENERIC_ACRONYMS = {
    "US",
    "USA",
    "UK",
    "EU",
    "UN",
    "IT",
    "HR",
    "PM",
    "QA",
    "BA",
    "OK",
    "ID",
    "PR",
    "AS",
    "IS",
    "OR",
    "DO",
    "TO",
    "OF",
    "BY",
    "AT",
    "IN",
    "ON",
    "UP",
    "NO",
    "SO",
    "AN",
    "BE",
    "MY",
    "KPI",
    "ROI",
    "CEO",
    "CTO",
    "CFO",
    "COO",
    "VP",
    "SVP",
    "EVP",
    "PTO",
    "EOE",
    "EEO",
    "OKR",
    "SOP",
    "SOW",
    "POC",
    "AM",
    "PM",
    "EST",
    "PST",
    "CST",
    "MST",
    "GMT",
    "UTC",
    "JD",
    "CV",
    "BS",
    "BA",
    "MS",
    "MA",
    "MBA",
    "PHD",
    "MD",
    "GPA",
}

# Location strings — exclude from technical keywords
LOCATION_TERMS = {
    "new york",
    "san francisco",
    "los angeles",
    "chicago",
    "seattle",
    "austin",
    "boston",
    "denver",
    "atlanta",
    "miami",
    "dallas",
    "houston",
    "washington",
    "dc",
    "philadelphia",
    "san jose",
    "san diego",
    "portland",
    "minneapolis",
    "detroit",
    "london",
    "toronto",
    "vancouver",
    "sydney",
    "new york city",
    "bay area",
    "silicon valley",
    "united states",
    "canada",
    "remote",
    "hybrid",
    "onsite",
    "on-site",
    "in office",
}

# Degree / education substrings — exclude phrases containing these
DEGREE_SUBSTRINGS = {
    "bachelor",
    "master",
    "phd",
    "ph.d",
    "doctorate",
    "degree",
    "b.s.",
    "m.s.",
    "b.e.",
    "m.e.",
    "m.tech",
    "b.tech",
    "mba",
    "associate",
    "diploma",
    "equivalent experience",
    "or equivalent",
    "university",
    "college",
    "graduate",
    "undergraduate",
    "coursework",
}

# Whole-phrase fluff patterns
GENERIC_JD_PHRASES = {
    "ability to work",
    "strong work ethic",
    "attention to detail",
    "fast paced",
    "fast-paced environment",
    "detail oriented",
    "detail-oriented",
    "self starter",
    "self-starter",
    "team player",
    "communication skills",
    "interpersonal skills",
    "problem solving skills",
    "critical thinking",
    "time management",
    "organizational skills",
    "passion for",
    "plus is",
    "nice to have",
    "good to have",
    "is a plus",
    "years of experience",
    "year of experience",
    "years experience",
    "highly motivated",
    "highly skilled",
    "results driven",
    "results-driven",
    "work experience",
    "professional experience",
    "prior experience",
    "equal opportunity",
    "equal opportunity employer",
    "affirmative action",
    "health insurance",
    "dental vision",
    "paid time off",
    "paid vacation",
    "competitive salary",
    "competitive compensation",
    "stock options",
    "work life balance",
    "work-life balance",
    "unlimited pto",
    "must have",
    "nice to have",
    "required skills",
    "preferred skills",
}


def _is_valid_keyword(phrase: str) -> bool:
    """Return True if phrase is a meaningful technical keyword."""
    phrase = phrase.strip()
    words = phrase.split()
    if not words or len(phrase) < 2 or len(phrase) > 60:
        return False
    if re.match(r"^\d+[\d.,]*$", phrase):  # pure number
        return False
    if all(w in FULL_STOP_WORDS for w in words):
        return False
    if phrase in GENERIC_JD_PHRASES:
        return False
    if phrase in LOCATION_TERMS:
        return False
    if any(d in phrase for d in DEGREE_SUBSTRINGS):
        return False
    return True


def extract_technical_keywords(text: str) -> dict:
    """
    NLP-based technical keyword extractor.
    Uses NLTK POS-tagging + noun-phrase chunking, acronym detection,
    CamelCase detection, and special-char tech term patterns.

    Returns dict mapping  lowercase_key -> display_form
    so callers can do case-insensitive matching but show pretty display names.
    """
    kw: dict[str, str] = {}  # lower_key -> display

    # ── Pass 1: ALL-CAPS acronyms  (FPGA, UVM, ASIC, STA) ──
    for acr in re.findall(r"\b[A-Z][A-Z0-9+#]{1,6}\b", text):
        if acr not in GENERIC_ACRONYMS:
            kw[acr.lower()] = acr

    # ── Pass 2: CamelCase / PascalCase  (SystemVerilog, TensorFlow) ──
    for term in re.findall(r"\b[A-Z][a-z]+(?:[A-Z][a-z0-9]+)+\b", text):
        lo = term.lower()
        if lo not in FULL_STOP_WORDS:
            kw.setdefault(lo, term)

    # ── Pass 3: Special-char tech tokens  (C++, C#, Node.js, .NET) ──
    for term in re.findall(
        r"\b(?:[A-Za-z][A-Za-z0-9]*(?:\+\+|#|\.(?:js|net|py|rb|go|ts|rs|sh|sql)))\b",
        text,
        re.IGNORECASE,
    ):
        kw.setdefault(term.lower(), term)

    # ── Pass 4: NLTK noun-phrase chunking ──
    try:
        grammar = r"NP: {<JJ|JJR>?<NN|NNP|NNS|NNPS|CD>{1,3}}"
        cp = RegexpParser(grammar)
        for sent in nltk.sent_tokenize(text):
            try:
                tokens = word_tokenize(sent)
                tagged = pos_tag(tokens)
            except Exception:
                continue
            tree = cp.parse(tagged)
            for subtree in tree.subtrees(filter=lambda t: t.label() == "NP"):
                phrase = " ".join(w.lower() for w, _ in subtree.leaves()).strip()
                # strip leading ordinals / numbers ("3+ years" → "years" is then filtered)
                phrase = re.sub(r"^\d+\+?\s*", "", phrase).strip()
                if _is_valid_keyword(phrase) and len(phrase.split()) <= 4:
                    kw.setdefault(phrase, phrase)
    except Exception:
        pass

    # ── Pass 5: bigrams and trigrams from cleaned token stream ──
    tokens = re.findall(r"[a-z][a-z0-9+#./]{1,}", text.lower())
    tokens = [t for t in tokens if t not in FULL_STOP_WORDS]
    for n in (2, 3):
        for i in range(len(tokens) - n + 1):
            ngram = " ".join(tokens[i : i + n])
            if _is_valid_keyword(ngram):
                kw.setdefault(ngram, ngram)

    # ── Pass 6: individual technical tokens (fallback) ──
    for tok in re.findall(r"\b[a-z][a-z0-9+#./]{2,}\b", text.lower()):
        if tok not in FULL_STOP_WORDS and _is_valid_keyword(tok):
            kw.setdefault(tok, tok)

    # ── Deduplicate: drop short key if whole-word-contained in a longer key ──
    all_keys = list(kw.keys())
    noise = set()
    for k in all_keys:
        for other in all_keys:
            if k != other and len(k) < len(other):
                if re.search(r"(?<![a-z])" + re.escape(k) + r"(?![a-z])", other):
                    noise.add(k)
                    break
    return {k: v for k, v in kw.items() if k not in noise}


# ══════════════════════════════════════════════════════════
#  RESUME HEALTH CHECK  (no JD required)
# ══════════════════════════════════════════════════════════

_ACTION_VERBS = [
    "developed",
    "managed",
    "led",
    "built",
    "designed",
    "implemented",
    "launched",
    "improved",
    "delivered",
    "created",
    "optimized",
    "architected",
    "drove",
    "reduced",
    "increased",
    "generated",
    "deployed",
    "maintained",
    "collaborated",
    "executed",
    "owned",
    "migrated",
    "automated",
    "scaled",
    "spearheaded",
    "established",
    "streamlined",
    "negotiated",
    "mentored",
]
_SECTION_HEADERS = [
    "experience",
    "education",
    "skills",
    "summary",
    "objective",
    "profile",
    "certifications",
    "projects",
    "publications",
    "awards",
    "work history",
    "employment",
    "qualifications",
]


def analyze_resume_health(resume_text: str) -> dict:
    """
    Score a resume on 6 dimensions without needing a job description.
    Returns a structured health report with breakdown, strengths, warnings, and quick fixes.
    """
    text = resume_text or ""
    lower = text.lower()

    strengths: list[str] = []
    warnings: list[str] = []
    critical: list[str] = []
    quick_fixes: list[str] = []
    breakdown: dict = {}

    # ── 1. Contact Information  /20 ──────────────────────────
    has_email = bool(
        re.search(r"\b[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-z]{2,}\b", text)
    )
    has_phone = bool(re.search(r"(\+?\d[\d\s\-().]{6,}\d)", text))
    has_linkedin = bool(re.search(r"linkedin\.com/", lower))
    has_location = bool(
        re.search(r"\b(?:remote|hybrid|[a-z]{3,}(?:,\s*[a-z]{2,}))\b", lower)
    )
    c_score = (
        (6 if has_email else 0)
        + (5 if has_phone else 0)
        + (5 if has_linkedin else 0)
        + (4 if has_location else 0)
    )

    if has_email:
        strengths.append("Email address found — ATS can route your application.")
    if has_phone:
        strengths.append("Phone number detected.")
    if has_linkedin:
        strengths.append("LinkedIn profile URL present — recruiter-friendly.")
    if not has_email:
        critical.append("No email address found. ATS systems require a contact email.")
    if not has_phone:
        warnings.append("No phone number detected. Add it so recruiters can reach you.")
    if not has_linkedin:
        quick_fixes.append("Add your LinkedIn URL (linkedin.com/in/yourname).")
    if not has_location:
        quick_fixes.append(
            "Include your city/state or 'Remote' to pass location filters."
        )
    breakdown["contact"] = {"score": c_score, "max": 20, "label": "Contact Info"}

    # ── 2. Professional Summary  /15 ─────────────────────────
    has_summary_header = bool(
        re.search(
            r"\b(summary|objective|profile|about me|professional profile)\b", lower
        )
    )
    first_600 = text[:600]
    long_sentences = [
        s.strip() for s in re.split(r"[.!?]", first_600) if len(s.strip()) > 25
    ]
    has_summary_body = len(long_sentences) >= 2
    s_score = (8 if has_summary_header else 0) + (7 if has_summary_body else 0)

    if s_score >= 12:
        strengths.append(
            "Professional summary section detected — helps ATS and recruiter context."
        )
    elif s_score == 0:
        critical.append(
            "No professional summary found. A 3–4 sentence summary dramatically increases ATS pass rate."
        )
    else:
        warnings.append(
            "Summary section may be too brief. Aim for 3–4 focused sentences at the top."
        )
    breakdown["summary"] = {
        "score": s_score,
        "max": 15,
        "label": "Professional Summary",
    }

    # ── 3. Work Experience  /25 ──────────────────────────────
    has_exp_header = bool(
        re.search(
            r"\b(experience|work history|employment|career history|professional experience)\b",
            lower,
        )
    )
    verb_hits = sum(1 for v in _ACTION_VERBS if v in lower)
    has_dates = bool(
        re.search(
            r"\b(20\d{2}|19\d{2}|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\b",
            lower,
        )
    )
    has_quant = bool(
        re.search(
            r"(?:\d+\s*(?:%|percent|million|billion|\$|k\b|x\b|users|customers|engineers|products))",
            lower,
        )
    )
    e_score = (
        (10 if has_exp_header else 0)
        + min(verb_hits, 10)
        + (3 if has_dates else 0)
        + (2 if has_quant else 0)
    )
    e_score = min(e_score, 25)

    if has_exp_header:
        strengths.append("Experience section found with a proper ATS-readable header.")
    if verb_hits >= 5:
        strengths.append(
            f"{verb_hits} action verbs detected — strong, active language."
        )
    if has_quant:
        strengths.append(
            "Quantified achievements (numbers/% /metrics) detected — excellent for standing out."
        )
    if not has_exp_header:
        critical.append(
            "No Experience section header found. ATS parsers specifically look for 'Experience' or 'Work History'."
        )
    if verb_hits < 3:
        warnings.append(
            "Few action verbs found. Start bullet points with words like 'Developed', 'Led', 'Optimized'."
        )
    if not has_quant:
        warnings.append(
            "No quantified achievements detected. Add numbers (%, $, users, time saved) to your bullet points."
        )
    if not has_dates:
        warnings.append(
            "Employment dates not detected. Include start/end dates for each role (e.g. Jan 2021 – Present)."
        )
    breakdown["experience"] = {"score": e_score, "max": 25, "label": "Work Experience"}

    # ── 4. Skills Section  /20 ───────────────────────────────
    has_skills_header = bool(
        re.search(
            r"\b(skills|technologies|tools|competencies|technical skills|core competencies)\b",
            lower,
        )
    )
    # Count distinct technical-looking tokens
    tech_tokens = re.findall(r"\b[A-Za-z][A-Za-z0-9+#./]{2,}\b", text)
    unique_tech = len(
        {t.lower() for t in tech_tokens if t.lower() not in FULL_STOP_WORDS}
    )
    sk_score = (10 if has_skills_header else 0) + min(unique_tech // 3, 10)
    sk_score = min(sk_score, 20)

    if has_skills_header:
        strengths.append(
            "Dedicated Skills section found — ATS can parse this as structured data."
        )
    if unique_tech >= 12:
        strengths.append(
            f"Rich technical vocabulary detected ({unique_tech}+ distinct terms)."
        )
    if not has_skills_header:
        critical.append(
            "No Skills section found. Add a dedicated 'Skills' section listing your tools, languages, and frameworks."
        )
    elif unique_tech < 8:
        warnings.append(
            "Skills section appears thin. List specific tools, languages, platforms, and frameworks you use."
        )
    breakdown["skills"] = {"score": sk_score, "max": 20, "label": "Skills Section"}

    # ── 5. Education  /10 ────────────────────────────────────
    has_edu_header = bool(
        re.search(
            r"\b(education|university|college|degree|bachelor|master|phd|b\.s|m\.s|b\.e|m\.tech)\b",
            lower,
        )
    )
    has_grad_year = bool(re.search(r"\b(20\d{2}|19\d{2})\b", lower))
    ed_score = (7 if has_edu_header else 0) + (3 if has_grad_year else 0)

    if has_edu_header:
        strengths.append("Education section detected.")
    if not has_edu_header:
        warnings.append(
            "No Education section found. Add your highest qualification with institution and year."
        )
    breakdown["education"] = {"score": ed_score, "max": 10, "label": "Education"}

    # ── 6. ATS Readability  /10 ──────────────────────────────
    word_count = len(text.split())
    header_hits = sum(1 for h in _SECTION_HEADERS if h in lower)
    has_bullets = bool(re.search(r"[•\-\*]", text))
    length_ok = 350 <= word_count <= 1200
    r_score = (
        min(header_hits * 2, 6) + (2 if has_bullets else 0) + (2 if length_ok else 0)
    )
    r_score = min(r_score, 10)

    if header_hits >= 3:
        strengths.append(
            f"{header_hits} standard section headers detected — good ATS parse compatibility."
        )
    if has_bullets:
        strengths.append("Bullet points detected — ATS-friendly formatting.")
    if word_count < 350:
        warnings.append(
            f"Resume seems short ({word_count} words). Most ATS systems prefer 450–900 words."
        )
    elif word_count > 1200:
        warnings.append(
            f"Resume may be too long ({word_count} words). Trim to 1–2 pages for best ATS results."
        )
    if not has_bullets:
        quick_fixes.append(
            "Use bullet points (•) in Experience — ATS parsers handle them better than paragraph blocks."
        )
    breakdown["readability"] = {"score": r_score, "max": 10, "label": "ATS Readability"}

    # ── Overall ──────────────────────────────────────────────
    overall = sum(v["score"] for v in breakdown.values())
    if overall >= 80:
        verdict = "Excellent"
    elif overall >= 65:
        verdict = "Good"
    elif overall >= 45:
        verdict = "Fair"
    else:
        verdict = "Needs Work"

    return {
        "mode": "health",
        "overall": overall,
        "breakdown": breakdown,
        "verdict": verdict,
        "strengths": strengths,
        "warnings": warnings,
        "critical": critical,
        "quick_fixes": quick_fixes,
        "word_count": word_count,
    }


# ══════════════════════════════════════════════════════════
#  JOB MATCH SCORING  (requires JD)
# ══════════════════════════════════════════════════════════


def calculate_ats_score_rich(resume_text, job_description):
    resume_lower = resume_text.lower()
    kw_map = extract_technical_keywords(job_description)

    if not kw_map:
        return {
            "mode": "match",
            "overall": 0,
            "keywords": 0,
            "skills": 0,
            "experience": 0,
            "format": 0,
            "verdict": "Needs Work",
            "strengths": [],
            "warnings": [
                "Could not extract meaningful keywords from the job description."
            ],
            "critical": [],
            "matching_keywords": [],
            "missing_keywords": [],
        }

    matching_display, missing_display = [], []
    for lo_key, display in kw_map.items():
        if lo_key in resume_lower or display.lower() in resume_lower:
            matching_display.append(display)
        else:
            missing_display.append(display)

    total = len(kw_map)
    keyword_score = min(round(len(matching_display) / total * 100), 100)

    # Skills: single-token entries (acronyms, short tech terms)
    skill_entries = {k: v for k, v in kw_map.items() if len(k.split()) == 1}
    skill_match = [
        v
        for k, v in skill_entries.items()
        if k in resume_lower or v.lower() in resume_lower
    ]
    skills_score = (
        min(round(len(skill_match) / len(skill_entries) * 100), 100)
        if skill_entries
        else keyword_score
    )

    # Experience: action-verb / seniority signals
    exp_signals = [
        "managed",
        "led",
        "developed",
        "built",
        "designed",
        "implemented",
        "delivered",
        "architected",
        "launched",
        "improved",
        "optimized",
        "years",
        "senior",
        "lead",
        "cross-functional",
        "stakeholder",
        "project",
    ]
    exp_hit = sum(1 for w in exp_signals if w in resume_lower)
    exp_score = min(
        round(exp_hit / len(exp_signals) * 100 * 0.5 + keyword_score * 0.5), 100
    )

    # Format: ATS-friendly section headers in resume
    sections = [
        "experience",
        "education",
        "skills",
        "summary",
        "objective",
        "certifications",
        "projects",
        "work",
        "employment",
    ]
    format_hit = sum(1 for s in sections if s in resume_lower)
    format_score = min(round(format_hit / 5 * 100), 100)

    overall = round(
        keyword_score * 0.40
        + skills_score * 0.30
        + exp_score * 0.15
        + format_score * 0.15
    )

    if overall >= 75:
        verdict = "Excellent"
    elif overall >= 60:
        verdict = "Good"
    elif overall >= 40:
        verdict = "Fair"
    else:
        verdict = "Needs Work"

    strengths, warnings, critical = [], [], []

    if keyword_score >= 70:
        strengths.append(
            f"Strong keyword coverage — {len(matching_display)} of {total} technical keywords matched."
        )
    if skills_score >= 70:
        strengths.append("Good technical skills alignment with the job requirements.")
    if format_score >= 80:
        strengths.append("Resume uses ATS-friendly section headers.")
    if exp_score >= 60:
        strengths.append("Strong action verbs and experience signals detected.")

    top_missing = missing_display[:6]
    if top_missing and keyword_score < 80:
        warnings.append(f"Add these missing keywords: {', '.join(top_missing)}.")
    if format_score < 60:
        warnings.append(
            "Add standard section headers: Summary, Experience, Education, Skills."
        )
    if skills_score < 50:
        warnings.append(
            "Your Skills section may be missing key technical terms from the JD."
        )
    if "%" not in resume_text and "percent" not in resume_lower:
        warnings.append(
            "Quantify achievements with numbers (%, $, time saved) to strengthen impact."
        )

    if overall < 40:
        critical.append(
            "Major mismatch — this resume needs significant tailoring for this role."
        )
    if len(matching_display) < total * 0.15:
        critical.append(
            "Fewer than 15% of job keywords appear in your resume. Tailor it specifically for this role."
        )

    # Sort: put high-value (multi-word / acronym) keywords first in missing
    missing_sorted = sorted(missing_display, key=lambda x: (-len(x.split()), x))

    return {
        "mode": "match",
        "overall": overall,
        "keywords": keyword_score,
        "skills": skills_score,
        "experience": exp_score,
        "format": format_score,
        "verdict": verdict,
        "strengths": strengths,
        "warnings": warnings,
        "critical": critical,
        "matching_keywords": sorted(matching_display)[:25],
        "missing_keywords": missing_sorted[:25],
    }


def call_gemini(prompt):
    if not gemini_client:
        return (
            None,
            "Gemini API key not configured. Please add GEMINI_API_KEY to your secrets.",
        )
    try:
        response = gemini_client.models.generate_content(
            model="gemini-2.5-flash", contents=prompt
        )
        return response.text, None
    except Exception as e:
        return None, str(e)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/resumes", methods=["GET"])
def list_resumes():
    db = get_db()
    resumes = db.execute(
        "SELECT id, name, created_at, updated_at FROM resumes ORDER BY updated_at DESC"
    ).fetchall()
    return jsonify([dict(r) for r in resumes])


@app.route("/api/resumes", methods=["POST"])
def save_resume():
    data = request.get_json()
    if not data or not data.get("name"):
        return jsonify({"error": "Resume name is required"}), 400
    db = get_db()
    resume_id = data.get("id")
    if resume_id:
        db.execute(
            "UPDATE resumes SET name=?, data=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (data["name"], json.dumps(data), resume_id),
        )
    else:
        cur = db.execute(
            "INSERT INTO resumes (name, data) VALUES (?, ?)",
            (data["name"], json.dumps(data)),
        )
        resume_id = cur.lastrowid
    db.commit()
    return jsonify({"success": True, "id": resume_id})


@app.route("/api/resumes/<int:resume_id>", methods=["GET"])
def get_resume(resume_id):
    db = get_db()
    resume = db.execute("SELECT * FROM resumes WHERE id=?", (resume_id,)).fetchone()
    if not resume:
        return jsonify({"error": "Resume not found"}), 404
    data = json.loads(resume["data"])
    data["id"] = resume["id"]
    return jsonify(data)


@app.route("/api/resumes/<int:resume_id>", methods=["DELETE"])
def delete_resume(resume_id):
    db = get_db()
    db.execute("DELETE FROM resumes WHERE id=?", (resume_id,))
    db.commit()
    return jsonify({"success": True})


def _parse_uploaded_file(file) -> tuple[str, str]:
    """Save, parse, and delete an uploaded resume file. Returns (text, filename)."""
    filename = secure_filename(file.filename)
    file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(file_path)
    try:
        ext = filename.rsplit(".", 1)[1].lower()
        text = (
            extract_text_from_pdf(file_path)
            if ext == "pdf"
            else extract_text_from_docx(file_path)
        )
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)
    return text, filename


# ── Resume Health Check (no JD needed) ───────────────────


@app.route("/api/ats-health-check", methods=["POST"])
def ats_health_check():
    """
    Analyse a resume for ATS readability without a job description.
    Accepts either a file upload (multipart) or JSON with resume_text.
    """
    resume_text = ""

    if "resume" in request.files:
        file = request.files["resume"]
        if not file or not allowed_file(file.filename):
            return jsonify({"error": "Only PDF and DOCX files are allowed"}), 400
        resume_text, _ = _parse_uploaded_file(file)
    elif request.is_json:
        data = request.get_json() or {}
        resume_text = data.get("resume_text", "").strip()
    else:
        return jsonify({"error": "Send a file upload or JSON with resume_text"}), 400

    if not resume_text.strip():
        return jsonify({"error": "Could not extract text from the resume"}), 400

    return jsonify(analyze_resume_health(resume_text))


# ── Job Match ATS Check (JD required) ────────────────────


@app.route("/api/ats-check", methods=["POST"])
def ats_check():
    if "resume" not in request.files:
        return jsonify({"error": "No resume file uploaded"}), 400
    file = request.files["resume"]
    job_description = request.form.get("job_description", "").strip()
    if not job_description:
        return jsonify({"error": "Job description is required for job-match mode"}), 400
    if not file or not allowed_file(file.filename):
        return jsonify({"error": "Only PDF and DOCX files are allowed"}), 400

    resume_text, _ = _parse_uploaded_file(file)
    result = calculate_ats_score_rich(resume_text, job_description)
    return jsonify(result)


@app.route("/api/ats-check-text", methods=["POST"])
def ats_check_text():
    data = request.get_json()
    if not data:
        return jsonify({"error": "JSON body required"}), 400
    resume_text = data.get("resume_text", "").strip()
    job_description = data.get("job_description", "").strip()
    if not resume_text:
        return jsonify({"error": "resume_text is required"}), 400
    if not job_description:
        return jsonify({"error": "job_description is required"}), 400
    result = calculate_ats_score_rich(resume_text, job_description)
    return jsonify(result)


@app.route("/api/ai/summary", methods=["POST"])
def generate_summary():
    data = request.get_json()
    resume_data = data.get("resume", {})
    name = resume_data.get("personalInfo", {}).get("fullName", "the candidate")
    title = resume_data.get("personalInfo", {}).get("jobTitle", "")
    skills = ", ".join([s.get("name", "") for s in resume_data.get("skills", [])[:10]])
    exp = resume_data.get("experience", [])
    exp_summary = "; ".join(
        [f"{e.get('position', '')} at {e.get('company', '')}" for e in exp[:3]]
    )

    prompt = f"""Write a professional resume summary (3-4 sentences) for:
Name: {name}
Target Role: {title}
Skills: {skills}
Experience: {exp_summary}

Write in first person, be specific, quantify achievements where possible. Return only the summary text, no labels or extra formatting."""

    result, error = call_gemini(prompt)
    if error:
        return jsonify({"error": error}), 500
    return jsonify({"summary": result})


@app.route("/api/ai/improve-bullet", methods=["POST"])
def improve_bullet():
    data = request.get_json()
    bullet = data.get("bullet", "")
    role = data.get("role", "")
    if not bullet:
        return jsonify({"error": "Bullet point text is required"}), 400

    prompt = f"""Improve this resume bullet point for a {role} role. Make it stronger using action verbs, specific metrics, and impact. Return only 1-2 improved bullet points, no extra text or formatting.

Original: {bullet}"""

    result, error = call_gemini(prompt)
    if error:
        return jsonify({"error": error}), 500
    return jsonify({"improved": result})


@app.route("/api/ai/cover-letter", methods=["POST"])
def generate_cover_letter():
    data = request.get_json()
    resume_data = data.get("resume", {})
    job_title = data.get("jobTitle", "")
    company = data.get("company", "")
    job_description = data.get("jobDescription", "")

    name = resume_data.get("personalInfo", {}).get("fullName", "Applicant")
    skills = ", ".join([s.get("name", "") for s in resume_data.get("skills", [])[:8]])
    exp = resume_data.get("experience", [])
    exp_summary = "; ".join(
        [f"{e.get('position', '')} at {e.get('company', '')}" for e in exp[:2]]
    )

    prompt = f"""Write a professional cover letter for:
Applicant: {name}
Applying for: {job_title} at {company}
Their skills: {skills}
Their experience: {exp_summary}
Job description excerpt: {job_description[:500] if job_description else "Not provided"}

Write a compelling 3-paragraph cover letter. Be professional, enthusiastic, and specific. Return only the letter text."""

    result, error = call_gemini(prompt)
    if error:
        return jsonify({"error": error}), 500
    return jsonify({"cover_letter": result})


@app.route("/api/ai/suggest-skills", methods=["POST"])
def suggest_skills():
    data = request.get_json()
    resume_data = data.get("resume", {})
    job_title = data.get("jobTitle", "")
    existing_skills = [s.get("name", "") for s in resume_data.get("skills", [])]
    exp = resume_data.get("experience", [])
    exp_roles = [e.get("position", "") for e in exp]

    prompt = f"""Suggest 10 relevant skills to add to a resume for:
Target role: {job_title}
Current experience roles: {", ".join(exp_roles)}
Already has: {", ".join(existing_skills)}

Return a JSON array of skill objects like: [{{"name": "Python", "level": "Advanced"}}, ...]
Include only skills they likely DON'T already have. Return only valid JSON, no markdown."""

    result, error = call_gemini(prompt)
    if error:
        return jsonify({"error": error}), 500

    try:
        clean = result.strip()
        if clean.startswith("```"):
            clean = re.sub(r"```(?:json)?\n?", "", clean).strip("`").strip()
        skills = json.loads(clean)
        return jsonify({"skills": skills})
    except Exception:
        return jsonify({"skills": [], "raw": result})


@app.route("/api/export-pdf", methods=["POST"])
def export_pdf():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No resume data provided"}), 400

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=0.75 * inch,
        leftMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )

    navy = colors.HexColor("#1a2b4a")
    dark_gray = colors.HexColor("#333333")
    mid_gray = colors.HexColor("#555555")
    light_gray = colors.HexColor("#777777")

    styles = getSampleStyleSheet()
    name_style = ParagraphStyle(
        "Name",
        fontSize=22,
        textColor=navy,
        fontName="Helvetica-Bold",
        spaceAfter=2,
        alignment=TA_CENTER,
    )
    contact_style = ParagraphStyle(
        "Contact",
        fontSize=9,
        textColor=mid_gray,
        fontName="Helvetica",
        spaceAfter=4,
        alignment=TA_CENTER,
    )
    section_style = ParagraphStyle(
        "Section",
        fontSize=11,
        textColor=navy,
        fontName="Helvetica-Bold",
        spaceBefore=10,
        spaceAfter=2,
        textTransform="uppercase",
    )
    subtitle_style = ParagraphStyle(
        "Subtitle",
        fontSize=10,
        textColor=dark_gray,
        fontName="Helvetica-Bold",
        spaceAfter=1,
    )
    meta_style = ParagraphStyle(
        "Meta",
        fontSize=9,
        textColor=light_gray,
        fontName="Helvetica-Oblique",
        spaceAfter=2,
    )
    body_style = ParagraphStyle(
        "Body",
        fontSize=9,
        textColor=dark_gray,
        fontName="Helvetica",
        spaceAfter=2,
        leading=13,
    )
    bullet_style = ParagraphStyle(
        "Bullet",
        fontSize=9,
        textColor=dark_gray,
        fontName="Helvetica",
        spaceAfter=1,
        leftIndent=12,
        leading=13,
        bulletIndent=4,
    )

    story = []
    pi = data.get("personalInfo", {})

    if pi.get("fullName"):
        story.append(Paragraph(pi["fullName"], name_style))
    if pi.get("jobTitle"):
        story.append(
            Paragraph(
                pi["jobTitle"],
                ParagraphStyle(
                    "Title",
                    fontSize=12,
                    textColor=mid_gray,
                    fontName="Helvetica",
                    spaceAfter=4,
                    alignment=TA_CENTER,
                ),
            )
        )

    contact_parts = []
    for field in ["email", "phone", "location", "linkedin", "website"]:
        if pi.get(field):
            contact_parts.append(pi[field])
    if contact_parts:
        story.append(Paragraph(" | ".join(contact_parts), contact_style))

    story.append(HRFlowable(width="100%", thickness=2, color=navy, spaceAfter=6))

    if data.get("summary"):
        story.append(Paragraph("Professional Summary", section_style))
        story.append(
            HRFlowable(
                width="100%",
                thickness=0.5,
                color=colors.HexColor("#cccccc"),
                spaceAfter=4,
            )
        )
        story.append(Paragraph(data["summary"], body_style))

    if data.get("experience"):
        story.append(Paragraph("Experience", section_style))
        story.append(
            HRFlowable(
                width="100%",
                thickness=0.5,
                color=colors.HexColor("#cccccc"),
                spaceAfter=4,
            )
        )
        for exp in data["experience"]:
            title_co = f"{exp.get('position', '')} — {exp.get('company', '')}"
            story.append(Paragraph(title_co, subtitle_style))
            dates = f"{exp.get('startDate', '')} – {exp.get('endDate', 'Present')}  |  {exp.get('location', '')}"
            story.append(Paragraph(dates.strip(" |"), meta_style))
            if exp.get("description"):
                for line in exp["description"].split("\n"):
                    line = line.strip().lstrip("•-").strip()
                    if line:
                        story.append(Paragraph(f"• {line}", bullet_style))
            story.append(Spacer(1, 4))

    if data.get("education"):
        story.append(Paragraph("Education", section_style))
        story.append(
            HRFlowable(
                width="100%",
                thickness=0.5,
                color=colors.HexColor("#cccccc"),
                spaceAfter=4,
            )
        )
        for edu in data["education"]:
            deg_school = f"{edu.get('degree', '')} — {edu.get('institution', '')}"
            story.append(Paragraph(deg_school, subtitle_style))
            meta = f"{edu.get('graduationYear', '')}  {('GPA: ' + edu.get('gpa', '')) if edu.get('gpa') else ''}"
            if meta.strip():
                story.append(Paragraph(meta.strip(), meta_style))
            if edu.get("description"):
                story.append(Paragraph(edu["description"], body_style))
            story.append(Spacer(1, 4))

    if data.get("skills"):
        story.append(Paragraph("Skills", section_style))
        story.append(
            HRFlowable(
                width="100%",
                thickness=0.5,
                color=colors.HexColor("#cccccc"),
                spaceAfter=4,
            )
        )
        skill_groups = {}
        for skill in data["skills"]:
            level = skill.get("level", "Other")
            skill_groups.setdefault(level, []).append(skill.get("name", ""))
        for level, names in skill_groups.items():
            story.append(Paragraph(f"<b>{level}:</b> {', '.join(names)}", body_style))

    if data.get("certifications"):
        story.append(Paragraph("Certifications", section_style))
        story.append(
            HRFlowable(
                width="100%",
                thickness=0.5,
                color=colors.HexColor("#cccccc"),
                spaceAfter=4,
            )
        )
        for cert in data["certifications"]:
            story.append(
                Paragraph(
                    f"• <b>{cert.get('name', '')}</b> — {cert.get('issuer', '')} ({cert.get('date', '')})",
                    bullet_style,
                )
            )

    if data.get("projects"):
        story.append(Paragraph("Projects", section_style))
        story.append(
            HRFlowable(
                width="100%",
                thickness=0.5,
                color=colors.HexColor("#cccccc"),
                spaceAfter=4,
            )
        )
        for proj in data["projects"]:
            story.append(Paragraph(proj.get("name", ""), subtitle_style))
            if proj.get("technologies"):
                story.append(Paragraph(f"Tech: {proj['technologies']}", meta_style))
            if proj.get("description"):
                story.append(Paragraph(proj["description"], body_style))
            story.append(Spacer(1, 4))

    doc.build(story)
    buffer.seek(0)
    name = data.get("personalInfo", {}).get("fullName", "Resume").replace(" ", "_")
    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"{name}_Resume.pdf",
        mimetype="application/pdf",
    )


# ── ATS REPORT ROUTES ────────────────────────────────────


@app.route("/api/ats-reports", methods=["GET"])
def list_ats_reports():
    db = get_db()
    rows = db.execute(
        "SELECT id, job_title, company, resume_name, created_at FROM ats_reports ORDER BY created_at DESC"
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/ats-reports", methods=["POST"])
def save_ats_report():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    job_title = data.get("job_title", "Untitled Role")
    company = data.get("company", "")
    resume_name = data.get("resume_name", "")
    score_data = data.get("score_data", {})
    job_description = data.get("job_description", "")
    db = get_db()
    cur = db.execute(
        "INSERT INTO ats_reports (job_title, company, resume_name, score_data, job_description) VALUES (?,?,?,?,?)",
        (job_title, company, resume_name, json.dumps(score_data), job_description),
    )
    db.commit()
    return jsonify({"success": True, "id": cur.lastrowid})


@app.route("/api/ats-reports/<int:report_id>", methods=["GET"])
def get_ats_report(report_id):
    db = get_db()
    row = db.execute("SELECT * FROM ats_reports WHERE id=?", (report_id,)).fetchone()
    if not row:
        return jsonify({"error": "Report not found"}), 404
    result = dict(row)
    result["score_data"] = json.loads(result["score_data"])
    return jsonify(result)


@app.route("/api/ats-reports/<int:report_id>", methods=["DELETE"])
def delete_ats_report(report_id):
    db = get_db()
    db.execute("DELETE FROM ats_reports WHERE id=?", (report_id,))
    db.commit()
    return jsonify({"success": True})


@app.route("/api/ats-reports/<int:report_id>/export-pdf")
def export_ats_report_pdf(report_id):
    db = get_db()
    row = db.execute("SELECT * FROM ats_reports WHERE id=?", (report_id,)).fetchone()
    if not row:
        return jsonify({"error": "Report not found"}), 404

    report = dict(row)
    score_data = json.loads(report["score_data"])
    return _build_ats_pdf(report, score_data)


@app.route("/api/ats-reports/export-pdf", methods=["POST"])
def export_ats_report_pdf_inline():
    """Export ATS report PDF without saving first."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data"}), 400
    report = {
        "job_title": data.get("job_title", "Role"),
        "company": data.get("company", ""),
        "resume_name": data.get("resume_name", ""),
        "created_at": "Now",
    }
    score_data = data.get("score_data", {})
    return _build_ats_pdf(report, score_data)


def _build_ats_pdf(report, score_data):
    from reportlab.platypus import Table, TableStyle
    from reportlab.graphics.shapes import Drawing, Circle, String, Rect
    from reportlab.graphics import renderPDF

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=0.75 * inch,
        leftMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )

    navy = colors.HexColor("#0F1C2E")
    blue = colors.HexColor("#2563EB")
    green = colors.HexColor("#16A34A")
    amber = colors.HexColor("#D97706")
    red = colors.HexColor("#DC2626")
    slate = colors.HexColor("#64748B")
    light = colors.HexColor("#F8FAFC")

    def score_color(s):
        return green if s >= 75 else (amber if s >= 50 else red)

    h1 = ParagraphStyle(
        "H1",
        fontSize=20,
        textColor=navy,
        fontName="Helvetica-Bold",
        spaceAfter=4,
        alignment=TA_CENTER,
    )
    h2 = ParagraphStyle(
        "H2",
        fontSize=13,
        textColor=navy,
        fontName="Helvetica-Bold",
        spaceBefore=14,
        spaceAfter=4,
    )
    sub = ParagraphStyle(
        "Sub",
        fontSize=10,
        textColor=slate,
        fontName="Helvetica",
        spaceAfter=2,
        alignment=TA_CENTER,
    )
    body = ParagraphStyle(
        "Body",
        fontSize=9,
        textColor=colors.HexColor("#334155"),
        fontName="Helvetica",
        spaceAfter=3,
        leading=13,
    )
    chip_good = ParagraphStyle(
        "Good",
        fontSize=8,
        textColor=green,
        fontName="Helvetica",
        spaceAfter=2,
        leading=12,
    )
    chip_bad = ParagraphStyle(
        "Bad", fontSize=8, textColor=red, fontName="Helvetica", spaceAfter=2, leading=12
    )

    overall = score_data.get("overall", 0)
    col = score_color(overall)

    story = []

    # ── Header ──
    story.append(Paragraph("ATS Compatibility Report", h1))
    role = report.get("job_title", "")
    co = report.get("company", "")
    story.append(Paragraph(f"{role}{' — ' + co if co else ''}", sub))
    story.append(Paragraph(f"Generated: {report.get('created_at', '')[:16]}", sub))
    story.append(HRFlowable(width="100%", thickness=2, color=navy, spaceAfter=12))

    # ── Score row: big number + breakdown table ──
    score_text = f'<font size="36" color="{col.hexval() if hasattr(col, "hexval") else "#000"}">{overall}</font>'
    score_para = Paragraph(
        f'<para alignment="center"><font size="40"><b>{overall}</b></font><br/><font size="10" color="#64748B">/ 100  ·  {score_data.get("verdict", "")}</font></para>',
        h1,
    )

    bands = [
        ("Keyword Match", score_data.get("keywords", 0)),
        ("Skills Alignment", score_data.get("skills", 0)),
        ("Experience Relevance", score_data.get("experience", 0)),
        ("Format & Readability", score_data.get("format", 0)),
    ]
    band_rows = [["Category", "Score", "Rating"]]
    for label, val in bands:
        rating = "Excellent" if val >= 75 else ("Good" if val >= 50 else "Needs Work")
        band_rows.append([label, f"{val}%", rating])

    band_table = Table(band_rows, colWidths=[2.8 * inch, 0.9 * inch, 1.2 * inch])
    band_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), navy),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 9),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 1), (-1, -1), 9),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [light, colors.white]),
                ("ALIGN", (1, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                ("ROWHEIGHT", (0, 0), (-1, -1), 18),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )

    layout = Table([[score_para, band_table]], colWidths=[1.8 * inch, None])
    layout.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (0, 0), 20),
            ]
        )
    )
    story.append(layout)
    story.append(Spacer(1, 12))

    # ── Keywords ──
    matching = score_data.get("matching_keywords", [])
    missing = score_data.get("missing_keywords", [])

    if matching or missing:
        story.append(Paragraph("Keyword Analysis", h2))
        story.append(
            HRFlowable(
                width="100%",
                thickness=0.5,
                color=colors.HexColor("#E2E8F0"),
                spaceAfter=6,
            )
        )
        kw_data = [["✓ Matching Keywords", "✗ Missing Keywords"]]
        match_str = ",  ".join(matching[:20]) or "—"
        miss_str = ",  ".join(missing[:20]) or "—"
        kw_data.append([match_str, miss_str])
        kw_table = Table(kw_data, colWidths=[3.5 * inch, 3.5 * inch])
        kw_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (0, 0), colors.HexColor("#F0FDF4")),
                    ("BACKGROUND", (1, 0), (1, 0), colors.HexColor("#FEF2F2")),
                    ("TEXTCOLOR", (0, 0), (0, 0), green),
                    ("TEXTCOLOR", (1, 0), (1, 0), red),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        story.append(kw_table)
        story.append(Spacer(1, 10))

    # ── Feedback sections ──
    def feedback_block(title, items, bg, border_col):
        if not items:
            return
        story.append(Paragraph(title, h2))
        story.append(
            HRFlowable(
                width="100%",
                thickness=0.5,
                color=colors.HexColor("#E2E8F0"),
                spaceAfter=4,
            )
        )
        for item in items:
            t = Table([[Paragraph(f"• {item}", body)]], colWidths=[6.8 * inch])
            t.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), bg),
                        ("LEFTPADDING", (0, 0), (-1, -1), 10),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                        ("TOPPADDING", (0, 0), (-1, -1), 5),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                        ("LINEBEFORE", (0, 0), (0, -1), 3, border_col),
                    ]
                )
            )
            story.append(t)
            story.append(Spacer(1, 3))

    feedback_block(
        "✓ Strengths",
        score_data.get("strengths", []),
        colors.HexColor("#F0FDF4"),
        green,
    )
    feedback_block(
        "⚠ Suggestions",
        score_data.get("warnings", []),
        colors.HexColor("#FFFBEB"),
        amber,
    )
    feedback_block(
        "✗ Critical Issues",
        score_data.get("critical", []),
        colors.HexColor("#FEF2F2"),
        red,
    )

    # ── Improvement suggestions from Gemini ──
    story.append(Spacer(1, 8))
    story.append(
        HRFlowable(
            width="100%", thickness=1, color=colors.HexColor("#E2E8F0"), spaceAfter=6
        )
    )
    story.append(Paragraph("Generated by ResumeIQ · Powered by Gemini AI", sub))

    doc.build(story)
    buffer.seek(0)
    safe_title = re.sub(r"[^a-zA-Z0-9_]", "_", report.get("job_title", "ATS_Report"))
    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"ATS_Report_{safe_title}.pdf",
        mimetype="application/pdf",
    )


# ── JOB TRACKER ROUTES ───────────────────────────────────


@app.route("/api/jobs", methods=["GET"])
def list_jobs():
    db = get_db()
    rows = db.execute(
        "SELECT * FROM job_applications ORDER BY updated_at DESC"
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/jobs", methods=["POST"])
def create_job():
    data = request.get_json()
    if not data or not data.get("job_title") or not data.get("company"):
        return jsonify({"error": "job_title and company are required"}), 400
    db = get_db()
    cur = db.execute(
        """INSERT INTO job_applications
           (job_title, company, job_url, status, applied_date, ats_score, ats_report_id, notes)
           VALUES (?,?,?,?,?,?,?,?)""",
        (
            data["job_title"],
            data["company"],
            data.get("job_url", ""),
            data.get("status", "saved"),
            data.get("applied_date", ""),
            data.get("ats_score"),
            data.get("ats_report_id"),
            data.get("notes", ""),
        ),
    )
    db.commit()
    return jsonify({"success": True, "id": cur.lastrowid})


@app.route("/api/jobs/<int:job_id>", methods=["PUT"])
def update_job(job_id):
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    db = get_db()
    db.execute(
        """UPDATE job_applications SET
           job_title=?, company=?, job_url=?, status=?, applied_date=?,
           ats_score=?, ats_report_id=?, notes=?, updated_at=CURRENT_TIMESTAMP
           WHERE id=?""",
        (
            data.get("job_title", ""),
            data.get("company", ""),
            data.get("job_url", ""),
            data.get("status", "saved"),
            data.get("applied_date", ""),
            data.get("ats_score"),
            data.get("ats_report_id"),
            data.get("notes", ""),
            job_id,
        ),
    )
    db.commit()
    return jsonify({"success": True})


@app.route("/api/jobs/<int:job_id>", methods=["DELETE"])
def delete_job(job_id):
    db = get_db()
    db.execute("DELETE FROM job_applications WHERE id=?", (job_id,))
    db.commit()
    return jsonify({"success": True})


# ── AI IMPROVEMENT SUGGESTIONS ───────────────────────────


@app.route("/api/ai/improve-resume", methods=["POST"])
def improve_resume():
    """Gemini-powered targeted improvement suggestions for a resume vs JD."""
    data = request.get_json()
    resume_text = data.get("resume_text", "")
    job_description = data.get("job_description", "")
    job_title = data.get("job_title", "the role")
    if not resume_text or not job_description:
        return jsonify({"error": "resume_text and job_description are required"}), 400

    prompt = f"""You are an expert resume coach. Analyze this resume against the job description for {job_title}.

RESUME:
{resume_text[:2000]}

JOB DESCRIPTION:
{job_description[:1500]}

Provide exactly 5 specific, actionable improvement suggestions. Each suggestion should directly address a gap between the resume and JD.
Format as a JSON array of strings: ["suggestion 1", "suggestion 2", ...]
Return only valid JSON, no markdown or extra text."""

    result, error = call_gemini(prompt)
    if error:
        return jsonify({"error": error}), 500
    try:
        clean = result.strip()
        if clean.startswith("```"):
            clean = re.sub(r"```(?:json)?\n?", "", clean).strip("`").strip()
        suggestions = json.loads(clean)
        return jsonify({"suggestions": suggestions})
    except Exception:
        return jsonify({"suggestions": [], "raw": result})


if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)

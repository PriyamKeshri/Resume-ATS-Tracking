import io
import json
import os
import re

import streamlit as st
from google import genai
from google.genai import types
from dotenv import load_dotenv
from fpdf import FPDF

from resume_parser import extract_text

# Config

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY", "")
model_name = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")

st.set_page_config(
    page_title="Resume ATS Tracker",
    layout="wide",
)

# --------------------------------------------------------------------------
# Styling — editorial: serif headline, small-caps section labels, outlined
# tags and a ring-style score gauge instead of colored candy.
# --------------------------------------------------------------------------

st.markdown(
    """
    <style>
    .hero-title {
        font-family: Georgia, 'Times New Roman', serif;
        font-size: 2.3rem;
        font-weight: 400;
        margin-bottom: 0.3rem;
    }
    .hero-eyebrow {
        text-transform: uppercase;
        letter-spacing: 0.12em;
        font-size: 0.72rem;
        opacity: 0.6;
        margin-bottom: 0.9rem;
    }
    .hero-rule {
        border: none;
        border-top: 1px solid rgba(128, 128, 128, 0.35);
        margin: 0 0 1rem 0;
    }
    .hero-subtitle {
        opacity: 0.75;
        font-size: 0.95rem;
        margin-bottom: 0.3rem;
    }
    h3 {
        text-transform: uppercase !important;
        letter-spacing: 0.07em !important;
        font-size: 0.85rem !important;
        font-weight: 600 !important;
        opacity: 0.8;
    }
    .tag {
        display: inline-block;
        padding: 3px 10px;
        margin: 3px 6px 3px 0;
        border-radius: 4px;
        font-size: 0.82rem;
        border: 1px solid rgba(128, 128, 128, 0.4);
    }
    .tag-good {
        border-color: rgba(22, 101, 52, 0.55);
    }
    .tag-bad {
        border-color: rgba(153, 27, 27, 0.55);
    }
    .score-ring {
        width: 110px;
        height: 110px;
        border-radius: 50%;
        border: 4px solid;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        margin: 0 auto;
    }
    .score-ring .score-num {
        font-size: 1.8rem;
        font-weight: 600;
        line-height: 1;
    }
    .score-ring .score-denom {
        font-size: 0.68rem;
        opacity: 0.6;
        margin-top: 2px;
    }
    .tier-label {
        text-align: center;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        font-size: 0.72rem;
        font-weight: 600;
        margin-top: 8px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# --------------------------------------------------------------------------
# Header
# --------------------------------------------------------------------------

st.markdown('<div class="hero-title">Resume ATS Tracker</div>', unsafe_allow_html=True)
st.markdown('<div class="hero-eyebrow">Match analysis report</div>', unsafe_allow_html=True)
st.markdown('<hr class="hero-rule" />', unsafe_allow_html=True)
st.markdown(
    '<div class="hero-subtitle">Upload a resume and paste a job description to get an '
    "ATS-style match score, keyword gap analysis, and tailored improvement suggestions "
    "— powered by Gemini.</div>",
    unsafe_allow_html=True,
)
st.caption(f"Model: `{model_name}`" + (" · API key loaded " if api_key else " · API key not set"))

st.write("")

col1, col2 = st.columns(2)

with col1:
    with st.container(border=True):
        st.subheader("1. Resume")
        resume_file = st.file_uploader(
            "Upload resume (PDF, DOCX, or TXT)", type=["pdf", "docx", "txt"]
        )
        resume_text_manual = st.text_area(
            "...or paste resume text directly",
            height=220,
            placeholder="Paste resume content here if you'd rather not upload a file.",
        )

with col2:
    with st.container(border=True):
        st.subheader("2. Job Description")
        jd_text = st.text_area(
            "Paste the target job description",
            height=300,
            placeholder="Paste the full job posting text here...",
        )

st.write("")
analyze_clicked = st.button("Analyze Resume", type="primary", use_container_width=True)


# Prompts

ANALYSIS_PROMPT = """You are an expert ATS (Applicant Tracking System) and technical recruiter.
Compare the RESUME to the JOB DESCRIPTION below and evaluate how well the resume would score
in a real ATS + human recruiter screen.

Return ONLY valid JSON (no markdown fences, no commentary) matching exactly this schema:

{{
  "match_score": <integer 0-100, overall ATS/keyword + relevance match score>,
  "verdict": "<one short sentence summarizing fit>",
  "matched_keywords": ["...keywords/skills from the JD found in the resume..."],
  "missing_keywords": ["...important keywords/skills from the JD missing from the resume..."],
  "strengths": ["...bullet points on what the resume does well for this JD..."],
  "weaknesses": ["...bullet points on gaps or weaknesses relative to this JD..."],
  "suggestions": ["...specific, actionable edits to improve the resume for this JD..."],
  "formatting_issues": ["...any ATS-parsing risks: tables, images, columns, headers/footers, fonts, etc. Empty list if none obviously detectable from text..."]
}}

RESUME:
\"\"\"
{resume}
\"\"\"

JOB DESCRIPTION:
\"\"\"
{jd}
\"\"\"
"""

COVER_LETTER_PROMPT = """You are an expert career coach writing a cover letter for a job applicant.

Using ONLY facts present in the RESUME below, write a concise, compelling cover letter
(3-4 short paragraphs) tailored to the JOB DESCRIPTION. Requirements:
- Professional but natural tone — no generic clichés like "I am writing to express my interest".
- Open with a specific, engaging hook relevant to the role/company.
- Highlight the 2-3 most relevant pieces of experience/skills for THIS job.
- Do not fabricate experience, employers, titles, or metrics not present in the resume.
- Close with a brief, confident call to action.
- Return ONLY the cover letter body text — no subject line, no markdown, no commentary.

RESUME:
\"\"\"
{resume}
\"\"\"

JOB DESCRIPTION:
\"\"\"
{jd}
\"\"\"
"""

BULLET_REWRITE_PROMPT = """You are an expert resume writer optimizing bullet points for both ATS
keyword matching and human readability.

From the RESUME below, pick the 5-8 bullet points that are weakest or least aligned with the
JOB DESCRIPTION (vague language, missing metrics, missing relevant keywords, weak verbs), and
rewrite each one to be stronger. Rules:
- Do NOT invent facts, numbers, employers, or tools that aren't implied by the original bullet.
- Prefer strong action verbs and, where the original implies a metric, make it explicit.
- Naturally weave in relevant keywords from the job description where truthful.
- Keep each rewritten bullet to one line.

Return ONLY valid JSON (no markdown fences, no commentary) matching exactly this schema:

{{
  "rewrites": [
    {{"original": "<verbatim original bullet>", "improved": "<rewritten bullet>", "reason": "<short reason for the change>"}}
  ]
}}

RESUME:
\"\"\"
{resume}
\"\"\"

JOB DESCRIPTION:
\"\"\"
{jd}
\"\"\"
"""

GRAMMAR_PROMPT = """You are a meticulous proofreader reviewing a resume before it goes out to
employers. Check ONLY for grammar, spelling, punctuation, and tense-consistency errors — do not
comment on content, keyword coverage, or formatting; that is handled elsewhere.

For every error you find, report the exact original snippet (verbatim, as it appears in the
resume), the corrected version, the error type, and a one-line explanation. If the resume is
clean, return an empty list.

Return ONLY valid JSON (no markdown fences, no commentary) matching exactly this schema:

{{
  "issues": [
    {{"original": "<verbatim snippet with the error>", "corrected": "<corrected snippet>", "type": "<spelling | grammar | punctuation | tense | other>", "explanation": "<brief explanation>"}}
  ]
}}

RESUME:
\"\"\"
{resume}
\"\"\"
"""

# Helpers


def parse_json_response(raw_text: str) -> dict:
    """Best-effort extraction of a JSON object from the model's response."""
    text = raw_text.strip()
    # Strip markdown code fences if present.
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Fallback: grab the first {...} block.
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return json.loads(match.group(0))
    raise ValueError("Could not parse a JSON object from the model response.")


def call_gemini_json(api_key: str, model_name: str, prompt: str) -> dict:
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=model_name,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.2,
            response_mime_type="application/json",
        ),
    )
    return parse_json_response(response.text)


def call_gemini_text(api_key: str, model_name: str, prompt: str) -> str:
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=model_name,
        contents=prompt,
        config=types.GenerateContentConfig(temperature=0.4),
    )
    return response.text.strip()


def analyze_resume(api_key: str, model_name: str, resume: str, jd: str) -> dict:
    prompt = ANALYSIS_PROMPT.format(resume=resume[:15000], jd=jd[:8000])
    return call_gemini_json(api_key, model_name, prompt)


def generate_cover_letter(api_key: str, model_name: str, resume: str, jd: str) -> str:
    prompt = COVER_LETTER_PROMPT.format(resume=resume[:15000], jd=jd[:8000])
    return call_gemini_text(api_key, model_name, prompt)


def rewrite_bullets(api_key: str, model_name: str, resume: str, jd: str) -> list:
    prompt = BULLET_REWRITE_PROMPT.format(resume=resume[:15000], jd=jd[:8000])
    data = call_gemini_json(api_key, model_name, prompt)
    return data.get("rewrites", [])


def check_grammar(api_key: str, model_name: str, resume: str) -> list:
    prompt = GRAMMAR_PROMPT.format(resume=resume[:15000])
    data = call_gemini_json(api_key, model_name, prompt)
    return data.get("issues", [])


def score_tier(score: int) -> str:
    if score >= 80:
        return "Strong match"
    if score >= 60:
        return "Moderate match"
    return "Weak match"


def score_hex(score: int) -> str:
    if score >= 80:
        return "#3b6d11"  # green
    if score >= 60:
        return "#854f0b"  # amber
    return "#791f1f"  # red


def render_score_badge(score: int) -> str:
    color = score_hex(score)
    return (
        f'<div class="score-ring" style="border-color:{color};">'
        f'<span class="score-num">{score}</span>'
        f'<span class="score-denom">/ 100</span>'
        f"</div>"
        f'<div class="tier-label" style="color:{color};">{score_tier(score)}</div>'
    )


def render_pills(items: list, kind: str) -> str:
    css_class = "tag-good" if kind == "good" else "tag-bad"
    mark = "✓" if kind == "good" else "✕"
    if not items:
        return '<span style="opacity:0.6;">None</span>'
    return "".join(f'<span class="tag {css_class}">{mark} {k}</span>' for k in items)


def _pdf_safe(text: str) -> str:
    """Core PDF fonts only support Latin-1 — drop anything outside that range."""
    if not text:
        return ""
    return text.encode("latin-1", errors="replace").decode("latin-1")


def build_pdf_report(
    result: dict,
    cover_letter: str = None,
    bullet_rewrites: list = None,
    grammar_issues: list = None,
) -> bytes:
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    def mc(h, text):
        # fpdf2's multi_cell defaults to leaving the cursor at the right edge
        # of the cell (new_x="RIGHT") — pin it back to the left margin after
        # every call, or the next call runs out of horizontal space.
        pdf.multi_cell(0, h, _pdf_safe(text), new_x="LMARGIN", new_y="NEXT")

    def heading(text, size=13):
        pdf.set_font("Helvetica", "B", size)
        pdf.ln(3)
        mc(8, text)
        pdf.set_font("Helvetica", "", 11)

    def body(text):
        mc(6, text)

    def bullet_list(items):
        pdf.set_font("Helvetica", "", 11)
        for item in items:
            mc(6, f"- {item}")

    score = int(result.get("match_score", 0))

    pdf.set_font("Helvetica", "B", 18)
    mc(10, "Resume ATS Report")
    pdf.set_font("Helvetica", "", 12)
    mc(8, f"Match Score: {score}/100")
    mc(8, f"Verdict: {result.get('verdict', '')}")

    heading("Matched Keywords")
    body(", ".join(result.get("matched_keywords", [])) or "None")

    heading("Missing Keywords")
    body(", ".join(result.get("missing_keywords", [])) or "None")

    heading("Strengths")
    bullet_list(result.get("strengths", []))

    heading("Weaknesses")
    bullet_list(result.get("weaknesses", []))

    heading("Suggestions")
    bullet_list(result.get("suggestions", []))

    fmt_issues = result.get("formatting_issues", [])
    if fmt_issues:
        heading("ATS Formatting Risks")
        bullet_list(fmt_issues)

    if bullet_rewrites:
        heading("Suggested Bullet Rewrites")
        for r in bullet_rewrites:
            pdf.set_font("Helvetica", "B", 11)
            mc(6, "Original: " + r.get("original", ""))
            pdf.set_font("Helvetica", "", 11)
            mc(6, "Improved: " + r.get("improved", ""))
            if r.get("reason"):
                pdf.set_font("Helvetica", "I", 10)
                mc(6, "Why: " + r.get("reason", ""))
            pdf.ln(2)

    if grammar_issues:
        heading("Grammar & Spelling Issues")
        for issue in grammar_issues:
            pdf.set_font("Helvetica", "B", 11)
            mc(6, "Original: " + issue.get("original", ""))
            pdf.set_font("Helvetica", "", 11)
            mc(6, "Corrected: " + issue.get("corrected", ""))
            if issue.get("explanation"):
                pdf.set_font("Helvetica", "I", 10)
                mc(6, f"{issue.get('type', '')}: {issue.get('explanation', '')}")
            pdf.ln(2)

    if cover_letter:
        heading("Cover Letter")
        body(cover_letter)

    return bytes(pdf.output())


# Run analysis

if analyze_clicked:
    if not api_key:
        st.error(
            "No Gemini API key found. Add `GEMINI_API_KEY=your-key` to a `.env` "
            "file in the project root, then restart the app."
        )
        st.stop()

    resume_text = resume_text_manual.strip()
    if not resume_text and resume_file is not None:
        try:
            resume_text = extract_text(resume_file)
        except Exception as e:
            st.error(f"Could not read the resume file: {e}")
            st.stop()

    if not resume_text:
        st.error("Please upload a resume file or paste resume text.")
        st.stop()
    if not jd_text.strip():
        st.error("Please paste a job description.")
        st.stop()

    with st.spinner("Analyzing your resume according to the job description..."):
        try:
            result = analyze_resume(api_key, model_name, resume_text, jd_text)
        except Exception as e:
            st.error(
                f"Gemini API call failed: {e}\n\n"
                "If this is a 'model not found' error, set GEMINI_MODEL in your "
                "`.env` file to a different model id (e.g. gemini-2.5-flash) and "
                "restart the app."
            )
            st.stop()

    st.session_state["last_result"] = result
    st.session_state["resume_text"] = resume_text
    st.session_state["jd_text"] = jd_text
    # Clear any previously generated extras from an older resume/JD pair.
    st.session_state.pop("cover_letter", None)
    st.session_state.pop("bullet_rewrites", None)
    st.session_state.pop("grammar_issues", None)


# Render results

result = st.session_state.get("last_result")
if result:
    saved_resume = st.session_state.get("resume_text", "")
    saved_jd = st.session_state.get("jd_text", "")

    st.divider()
    score = int(result.get("match_score", 0))
    fmt_issues = result.get("formatting_issues", [])

    with st.container(border=True):
        top1, top2 = st.columns([1, 3])
        with top1:
            st.markdown(render_score_badge(score), unsafe_allow_html=True)
        with top2:
            st.subheader("Verdict")
            st.write(result.get("verdict", "—"))

    st.write("")
    c1, c2 = st.columns(2)
    with c1:
        with st.container(border=True):
            st.subheader("Matched Keywords")
            st.markdown(render_pills(result.get("matched_keywords", []), "good"), unsafe_allow_html=True)

        st.write("")
        with st.container(border=True):
            st.subheader("Strengths")
            for s in result.get("strengths", []):
                st.markdown(f"- {s}")

    with c2:
        with st.container(border=True):
            st.subheader("Missing Keywords")
            st.markdown(render_pills(result.get("missing_keywords", []), "bad"), unsafe_allow_html=True)

        st.write("")
        with st.container(border=True):
            st.subheader("Weaknesses")
            for w in result.get("weaknesses", []):
                st.markdown(f"- {w}")

    st.write("")
    with st.container(border=True):
        st.subheader("Suggestions to Improve")
        for sug in result.get("suggestions", []):
            st.markdown(f"- {sug}")

    if fmt_issues:
        st.write("")
        with st.container(border=True):
            st.subheader("ATS Formatting Risks")
            for f in fmt_issues:
                st.markdown(f"- {f}")

    # ----------------------------------------------------------------
    # Extra features: cover letter + bullet rewriter
    # ----------------------------------------------------------------
    st.divider()
    st.subheader("More Tools")

    tab_cover, tab_bullets, tab_grammar, tab_export = st.tabs(
        ["Cover Letter", "Bullet Rewrites", "Grammar & Spelling", "Export"]
    )

    with tab_cover:
        if st.button("Generate Cover Letter", use_container_width=True):
            with st.spinner("Writing cover letter..."):
                try:
                    st.session_state["cover_letter"] = generate_cover_letter(
                        api_key, model_name, saved_resume, saved_jd
                    )
                except Exception as e:
                    st.error(f"Cover letter generation failed: {e}")

        cover_letter = st.session_state.get("cover_letter")
        if cover_letter:
            st.text_area("Cover letter", value=cover_letter, height=280, label_visibility="collapsed")
            st.download_button(
                "Download Cover Letter (.txt)",
                data=cover_letter,
                file_name="cover_letter.txt",
                mime="text/plain",
            )
        else:
            st.caption("Click the button to draft a cover letter tailored to this resume + job description.")

    with tab_bullets:
        if st.button("Rewrite Weak Bullets", use_container_width=True):
            with st.spinner("Rewriting weak bullets..."):
                try:
                    st.session_state["bullet_rewrites"] = rewrite_bullets(
                        api_key, model_name, saved_resume, saved_jd
                    )
                except Exception as e:
                    st.error(f"Bullet rewriting failed: {e}")

        bullet_rewrites = st.session_state.get("bullet_rewrites")
        if bullet_rewrites:
            for r in bullet_rewrites:
                with st.container(border=True):
                    st.markdown(f"**Original:** {r.get('original', '')}")
                    st.markdown(f"**Improved:** {r.get('improved', '')}")
                    if r.get("reason"):
                        st.caption(f"Why: {r.get('reason')}")
        else:
            st.caption("Click the button to get stronger rewrites of your weakest resume bullets.")

    with tab_grammar:
        if st.button("Check Grammar & Spelling", use_container_width=True):
            with st.spinner("Proofreading resume..."):
                try:
                    st.session_state["grammar_issues"] = check_grammar(
                        api_key, model_name, saved_resume
                    )
                except Exception as e:
                    st.error(f"Grammar check failed: {e}")

        grammar_issues = st.session_state.get("grammar_issues")
        if grammar_issues is not None:
            if grammar_issues:
                for issue in grammar_issues:
                    with st.container(border=True):
                        st.markdown(f"**Original:** {issue.get('original', '')}")
                        st.markdown(f"**Corrected:** {issue.get('corrected', '')}")
                        issue_type = issue.get("type", "")
                        explanation = issue.get("explanation", "")
                        caption = " · ".join(x for x in [issue_type, explanation] if x)
                        if caption:
                            st.caption(caption)
            else:
                st.caption("No grammar or spelling issues found.")
        else:
            st.caption("Click the button to proofread the resume for grammar, spelling, and punctuation errors.")

    cover_letter = st.session_state.get("cover_letter")
    bullet_rewrites = st.session_state.get("bullet_rewrites")
    grammar_issues = st.session_state.get("grammar_issues")

    with tab_export:
        report_md = f"""# Resume ATS Report

**Match Score:** {score}/100
**Verdict:** {result.get('verdict', '')}

## Matched Keywords
{', '.join(result.get('matched_keywords', [])) or 'None'}

## Missing Keywords
{', '.join(result.get('missing_keywords', [])) or 'None'}

## Strengths
{chr(10).join('- ' + s for s in result.get('strengths', []))}

## Weaknesses
{chr(10).join('- ' + w for w in result.get('weaknesses', []))}

## Suggestions
{chr(10).join('- ' + s for s in result.get('suggestions', []))}

## Formatting Risks
{chr(10).join('- ' + f for f in fmt_issues)}
"""
        if bullet_rewrites:
            report_md += "\n## Suggested Bullet Rewrites\n"
            for r in bullet_rewrites:
                report_md += f"\n- **Original:** {r.get('original', '')}\n  **Improved:** {r.get('improved', '')}\n"
                if r.get("reason"):
                    report_md += f"  *Why:* {r.get('reason')}\n"

        if grammar_issues:
            report_md += "\n## Grammar & Spelling Issues\n"
            for issue in grammar_issues:
                report_md += f"\n- **Original:** {issue.get('original', '')}\n  **Corrected:** {issue.get('corrected', '')}\n"
                if issue.get("explanation"):
                    report_md += f"  *{issue.get('type', '')}:* {issue.get('explanation', '')}\n"

        if cover_letter:
            report_md += f"\n## Cover Letter\n\n{cover_letter}\n"

        st.caption("Download the full analysis — including the cover letter, bullet rewrites, and grammar check above, if generated.")
        ecol1, ecol2 = st.columns(2)
        with ecol1:
            st.download_button(
                "Download Report (Markdown)",
                data=report_md,
                file_name="resume_ats_report.md",
                mime="text/markdown",
                use_container_width=True,
            )
        with ecol2:
            try:
                pdf_bytes = build_pdf_report(
                    result,
                    cover_letter=cover_letter,
                    bullet_rewrites=bullet_rewrites,
                    grammar_issues=grammar_issues,
                )
                st.download_button(
                    "Download Report (PDF)",
                    data=pdf_bytes,
                    file_name="resume_ats_report.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )
            except Exception as e:
                st.error(f"Could not build PDF: {e}")

    with st.expander("Raw JSON response"):
        st.json(result)

<div align="center">

# 📄 Resume ATS Tracker

A Streamlit app that scores a resume against a job description using the Google Gemini API —
get an ATS-style match score, a keyword gap analysis, a tailored cover letter, and AI-rewritten
resume bullets, all in one place.

![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)
![Gemini](https://img.shields.io/badge/Google%20Gemini-8E75B2?style=for-the-badge&logo=google&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-4ADE80?style=for-the-badge)

🔗 **[Try it live](https://track-resume-ats.streamlit.app)**

</div>

---

## ✨ Features

| | |
|---|---|
| 🎯 **Match Score** | 0–100 ATS-style score with a one-line verdict on overall fit |
| 🔑 **Keyword Gap Analysis** | Matched vs. missing keywords pulled straight from the job description |
| 💪 **Strengths & Weaknesses** | Plain-language breakdown of what's working and what's not |
| 🛠️ **Actionable Suggestions** | Concrete edits to improve the resume for the target role |
| 📐 **ATS Formatting Risks** | Flags parsing hazards like tables, columns, or missing sections |
| ✍️ **Cover Letter Generator** | One click drafts a tailored cover letter from the resume + JD |
| 🔁 **Bullet Rewriter** | Rewrites the weakest resume bullets with stronger, keyword-aligned phrasing |
| ✅ **Grammar & Spelling Check** | Flags spelling, grammar, and tense errors, with corrected snippets |
| ⬇️ **Export** | Download the full report as Markdown or PDF |

---

## ⚙️ How It Works

**1. You provide a resume and a job description**

Upload a PDF/DOCX/TXT file or paste the resume text directly, then paste the job posting
you're targeting.

**2. Text extraction**

For uploaded files, `resume_parser.py` pulls out plain text — including table cells, since
resumes often use tables for layout that plain paragraph parsing would miss.

**3. Structured analysis via Gemini**

The resume and job description are sent to the Gemini API with a prompt that requests a
strict JSON response (`response_mime_type="application/json"`): match score, verdict,
matched/missing keywords, strengths, weaknesses, suggestions, and formatting risks. The
response is parsed defensively — the app never assumes it's clean.

**4. Report rendering**

That JSON directly drives the UI: the score ring's color and tier label, the green/red
keyword tags, and the strengths/weaknesses/suggestions cards.

**5. On-demand tools**

The cover letter generator, bullet rewriter, and grammar checker are separate, independent
Gemini calls — they only run when you click their button, each with its own prompt tailored
to that specific task.

**6. Export**

The full report — plus any cover letter, bullet rewrites, or grammar fixes you generated —
can be downloaded as Markdown or as a formatted PDF (built with `fpdf2`).

---

## 📸 Screenshots

<p align="center"><b>Homepage</b> — features overview before you upload anything</p>

![Homepage](docs/screenshots/01-homepage.png)

<p align="center"><b>Analysis results</b> — match score, verdict, and matched/missing keywords</p>

![Analysis results](docs/screenshots/02-results.png)

<p align="center"><b>Suggestions + More Tools</b> — actionable edits, plus cover letter, bullet rewriter, grammar check, and export</p>

![More tools](docs/screenshots/03-more-tools.png)

---

## 🚀 Quick Start

**1. Install dependencies**

```bash
pip install -r requirements.txt
```

**2. Add your Gemini API key**

Get one from [Google AI Studio](https://aistudio.google.com/apikey), then edit the `.env` file
in the project root:

```bash
GEMINI_API_KEY=your-api-key-here
GEMINI_MODEL=gemini-3.6-flash
```

**3. Run the app**

```bash
streamlit run app.py
```

**4. Use it** — upload or paste a resume, paste a job description, and click **Analyze Resume**.

---

## 🧰 Tech Stack

<p align="center">
  <img src="https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white"/>
  <img src="https://img.shields.io/badge/Google%20Gemini-8E75B2?style=for-the-badge&logo=google&logoColor=white"/>
  <img src="https://img.shields.io/badge/pdfplumber-1E293B?style=for-the-badge"/>
  <img src="https://img.shields.io/badge/python--docx-1E293B?style=for-the-badge"/>
  <img src="https://img.shields.io/badge/fpdf2-1E293B?style=for-the-badge"/>
</p>

---

<div align="center">

📄 [MIT License](LICENSE)

</div>

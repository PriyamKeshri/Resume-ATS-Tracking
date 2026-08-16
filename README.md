# Resume ATS Tracker

A Streamlit app that scores a resume against a job description using the Google Gemini API,
reporting an ATS-style match score, matched/missing keywords, strengths, weaknesses, and
concrete suggestions to improve the resume.

## Setup

```bash
pip install -r requirements.txt
```

Get a Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey), then edit
the `.env` file in the project root:

```bash
GEMINI_API_KEY=your-api-key-here
GEMINI_MODEL=gemini-3.6-flash
```

## Run

```bash
streamlit run app.py
```

Then in the app: upload or paste a resume, paste a job description, and click **Analyze Resume**.

## Features

- ATS match score (0-100), verdict, and matched/missing keyword breakdown
- Strengths, weaknesses, actionable suggestions, and ATS formatting-risk detection
- **Cover letter generator** — one click to draft a tailored cover letter from the resume + JD
- **Bullet rewriter** — Gemini rewrites the weakest resume bullets to better match the JD, with a reason for each change

## Files

- `app.py` — Streamlit UI + Gemini call + result rendering
- `resume_parser.py` — PDF/DOCX/TXT text extraction for uploaded resumes
- `requirements.txt` — Python dependencies

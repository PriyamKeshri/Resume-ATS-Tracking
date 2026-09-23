"""Call-level telemetry for the Gemini calls in app.py.

Every model call is appended to telemetry/llm_calls.jsonl with what triggered
it, how many tokens it actually spent, how long it took, and how it ended.

The point is to replace "the model is busy" with numbers: which feature spends
the tokens, whether a failure was our quota (429) or Google's capacity (503),
and whether the response came back fine but failed to parse -- which looks
identical to an API error from the UI today.

Prompt *sizes* are recorded, never prompt *content*: the prompts carry resume
and job-description text.

Read the log back with:  python llm_telemetry.py
"""

from __future__ import annotations

import json
import os
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "telemetry")
LOG_PATH = os.path.join(LOG_DIR, "llm_calls.jsonl")

# Gemini's free tier caps tokens per minute, not just requests per minute, so
# the rolling 60s token total is the number that explains a burst of 429s.
WINDOW_SECONDS = 60


# ---------------------------------------------------------------- classify

def classify_error(exc: BaseException) -> str:
    """Map an exception onto the thing that actually went wrong.

    The google-genai SDK surfaces the HTTP status on `.code`, but not every
    failure path does, so fall back to matching the status names in the text.
    """
    code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    text = f"{type(exc).__name__}: {exc}".upper()

    if code == 429 or "RESOURCE_EXHAUSTED" in text or "429" in text:
        return "rate_limit"        # our quota -- back off, or spend fewer tokens
    if code == 503 or "UNAVAILABLE" in text or "OVERLOADED" in text or "503" in text:
        return "overloaded"        # Google's capacity -- retry sooner
    if code in (401, 403) or "PERMISSION_DENIED" in text or "UNAUTHENTICATED" in text:
        return "auth"
    if code == 404 or "NOT_FOUND" in text:
        return "model_not_found"
    if code is not None and 500 <= int(code) < 600:
        return "server_error"
    if isinstance(exc, (json.JSONDecodeError, ValueError)):
        return "parse_error"
    return "other"


def _session_id() -> str:
    """Stable per-Streamlit-session id, so calls can be grouped by one user run."""
    try:
        import streamlit as st

        if "_telemetry_session" not in st.session_state:
            st.session_state["_telemetry_session"] = uuid.uuid4().hex[:8]
        return st.session_state["_telemetry_session"]
    except Exception:
        return os.environ.setdefault("_TELEMETRY_SESSION", uuid.uuid4().hex[:8])


def _write(row: dict) -> None:
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row) + "\n")
    except Exception:
        # Telemetry must never be the reason a feature fails.
        pass


# ---------------------------------------------------------------- record

class _Call:
    """Handle yielded by `record`, used to separate API failure from parse failure."""

    def __init__(self) -> None:
        self.api_returned = False
        self.prompt_tokens = None
        self.output_tokens = None

    def api_ok(self, response=None) -> None:
        """Mark the API call as returned. Anything that throws after this is ours."""
        self.api_returned = True
        usage = getattr(response, "usage_metadata", None)
        if usage is not None:
            self.prompt_tokens = getattr(usage, "prompt_token_count", None)
            self.output_tokens = getattr(usage, "candidates_token_count", None)


@contextmanager
def record(feature: str, model: str, prompt_chars: int, attempt: int = 1):
    """Wrap one model call and append a row describing how it went.

    `attempt` is the retry number, so the log shows how often a retry rescued a
    call that would previously have been a dead end.
    """
    bump_session_calls()   # count attempts, not successes -- failures cost quota too
    started = time.perf_counter()
    call = _Call()
    outcome = "ok"
    error_type = None
    error_msg = None

    try:
        yield call
    except BaseException as exc:
        # If the API already returned, the failure is in our own parsing.
        outcome = "error"
        error_type = "parse_error" if call.api_returned else classify_error(exc)
        error_msg = f"{type(exc).__name__}: {exc}"[:300]
        raise
    finally:
        _write(
            {
                "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
                "session": _session_id(),
                "feature": feature,
                "attempt": attempt,
                "model": model,
                "outcome": outcome,
                "error_type": error_type,
                "error_msg": error_msg,
                "latency_ms": round((time.perf_counter() - started) * 1000, 1),
                "prompt_chars": prompt_chars,
                # Real counts when the SDK reports them; the /4 estimate is a
                # fallback so a failed call still contributes to the window.
                "prompt_tokens": call.prompt_tokens,
                "output_tokens": call.output_tokens,
                "est_tokens": call.prompt_tokens or round(prompt_chars / 4),
            }
        )


def session_calls() -> int:
    """How many calls this Streamlit session has made. Drives the sidebar counter."""
    try:
        import streamlit as st

        return int(st.session_state.get("_telemetry_count", 0))
    except Exception:
        return 0


def bump_session_calls() -> None:
    try:
        import streamlit as st

        st.session_state["_telemetry_count"] = session_calls() + 1
    except Exception:
        pass


# ---------------------------------------------------------------- report

def _load() -> list:
    if not os.path.exists(LOG_PATH):
        return []
    rows = []
    with open(LOG_PATH, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def _percentile(values: list, pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, int(round((pct / 100) * (len(ordered) - 1))))
    return ordered[idx]


def peak_token_window(rows: list) -> tuple:
    """Highest token total inside any rolling WINDOW_SECONDS, and when it ended.

    This is the number that confirms or kills the tokens-per-minute theory.
    """
    stamped = []
    for r in rows:
        try:
            stamped.append((datetime.fromisoformat(r["ts"]), r.get("est_tokens") or 0))
        except (KeyError, ValueError):
            continue
    stamped.sort()

    peak, peak_at, start = 0, None, 0
    running = 0
    for end in range(len(stamped)):
        running += stamped[end][1]
        while (stamped[end][0] - stamped[start][0]).total_seconds() > WINDOW_SECONDS:
            running -= stamped[start][1]
            start += 1
        if running > peak:
            peak, peak_at = running, stamped[end][0]
    return peak, peak_at


def report() -> str:
    rows = _load()
    if not rows:
        return (
            "No calls recorded yet.\n\n"
            "Run the app, use it the way you normally would -- analyze a resume, "
            "then click through the cover letter, bullet and grammar tabs -- then "
            "run this again."
        )

    out = []
    out.append(f"{len(rows)} calls across {len({r.get('session') for r in rows})} sessions")
    out.append("")

    # Per feature: what each one costs.
    out.append(f"{'feature':<16}{'calls':>7}{'ok':>6}{'fail':>6}{'tokens':>10}{'p50 ms':>9}{'p95 ms':>9}")
    out.append("-" * 63)
    features = sorted({r.get("feature", "?") for r in rows})
    for feat in features:
        fr = [r for r in rows if r.get("feature") == feat]
        ok = sum(1 for r in fr if r.get("outcome") == "ok")
        lat = [r.get("latency_ms", 0) for r in fr if r.get("outcome") == "ok"]
        toks = sum(r.get("est_tokens") or 0 for r in fr)
        out.append(
            f"{feat:<16}{len(fr):>7}{ok:>6}{len(fr) - ok:>6}{toks:>10,}"
            f"{_percentile(lat, 50):>9.0f}{_percentile(lat, 95):>9.0f}"
        )

    # Failures, split by cause -- the split the UI currently collapses into one message.
    failures = [r for r in rows if r.get("outcome") != "ok"]
    out.append("")
    if failures:
        out.append(f"{len(failures)} failures by cause:")
        kinds = {}
        for r in failures:
            kinds[r.get("error_type") or "unknown"] = kinds.get(r.get("error_type") or "unknown", 0) + 1
        for kind, n in sorted(kinds.items(), key=lambda kv: -kv[1]):
            meaning = {
                "rate_limit": "our quota -- we sent too much, too fast",
                "overloaded": "Google's capacity -- retry would likely have worked",
                "parse_error": "API returned fine; the response would not parse",
                "auth": "key or permissions",
                "model_not_found": "bad GEMINI_MODEL value",
            }.get(kind, "")
            out.append(f"  {kind:<18}{n:>4}   {meaning}")
    else:
        out.append("No failures recorded.")

    # Retry effectiveness: of the calls that needed more than one attempt,
    # how many eventually returned?
    retried = [r for r in rows if (r.get("attempt") or 1) > 1]
    if retried:
        rescued = sum(1 for r in retried if r.get("outcome") == "ok")
        out.append("")
        out.append(
            f"Retries: {len(retried)} retry attempts, {rescued} of them succeeded "
            f"-- calls the old code would have dropped."
        )
        by_attempt = {}
        for r in rows:
            a = r.get("attempt") or 1
            by_attempt.setdefault(a, [0, 0])
            by_attempt[a][0] += 1
            if r.get("outcome") == "ok":
                by_attempt[a][1] += 1
        for a in sorted(by_attempt):
            total, ok = by_attempt[a]
            out.append(f"  attempt {a}: {ok}/{total} succeeded")

    peak, peak_at = peak_token_window(rows)
    out.append("")
    out.append(f"Peak tokens in any {WINDOW_SECONDS}s window: {peak:,}")
    if peak_at:
        out.append(f"  window ended {peak_at.isoformat(timespec='seconds')}")
    out.append("")
    out.append(
        "If that peak sits near your tier's tokens-per-minute cap, the 429s are\n"
        "self-inflicted and the fix is fewer/smaller calls, not a longer retry."
    )

    return "\n".join(out)


if __name__ == "__main__":
    print(report())

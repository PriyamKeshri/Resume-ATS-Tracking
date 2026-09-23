"""Retry policy for the Gemini calls.

Measured behaviour that shaped this (see telemetry/llm_calls.jsonl):

  * gemini-3.6-flash returns 503 UNAVAILABLE for roughly half of this app's
    analyze-sized calls, while a trivial one-line prompt to the same model on
    the same key succeeds first try. The failure is capacity shedding, not our
    quota and not a bad model id.
  * A single retry rescued 2 of 5 trials. Before this module the app had no
    retry at all, so every one of those was a dead end for the user.
  * Full jitter -- uniform(0, ceiling) -- is a trap here. It can return ~0, and
    in one trial it produced delays of 0.2s, 0.0s, 0.0s, 0.1s: five attempts
    inside a second, which escalated a 503 into a 429. The delay needs a floor.

So: exponential ceiling, jitter that never collapses to zero, a harder backoff
for 429 than 503, and a wall-clock budget so the UI cannot hang.
"""

from __future__ import annotations

import random
import time

import llm_telemetry

# Worth another attempt. `parse_error` is included because the model's output is
# non-deterministic -- the same prompt can return valid JSON next time. `auth`,
# `model_not_found` and `other` are not: they will fail identically forever.
#
# `rate_limit` is deliberately NOT here, and that is the second thing measurement
# changed. Retrying a 429 was the obvious-looking move and it is wrong: 429 means
# the quota is already spent, so every retry spends more of a budget that has
# nothing left in it. Measured over 36 calls: 28 of them 429, zero of which ever
# succeeded, while a 4-attempt policy turned each user action into 4 more.
# A 503 is Google out of capacity and clears in about a second; a 429 is us out
# of quota and clears when the window rolls over. Only one of those is a retry.
RETRYABLE = {"overloaded", "server_error", "parse_error"}

# What to tell the user, per cause. The old UI printed one generic string and
# guessed "model not found" for everything, which is why a quota problem and a
# capacity problem were indistinguishable from the screen.
ADVICE = {
    "rate_limit": (
        "Out of Gemini quota. Retrying will not help and spends more of it -- "
        "wait for the quota window to reset, or use a key with more headroom."
    ),
    "overloaded": (
        "Gemini is shedding load right now. This usually clears in seconds; "
        "the app already retried before showing you this."
    ),
    "auth": "The API key was rejected. Check GEMINI_API_KEY in your .env file.",
    "model_not_found": (
        "GEMINI_MODEL names a model this key cannot reach. Check the value in .env."
    ),
    "parse_error": (
        "The model replied, but not with JSON this app could parse. "
        "Retrying usually fixes it, since the output is non-deterministic."
    ),
}


def explain(exc: BaseException) -> tuple:
    """(cause, what the user should do about it) for a failed call."""
    kind = llm_telemetry.classify_error(exc)
    return kind, ADVICE.get(kind, "Unexpected failure -- see the message above.")

BASE_DELAY = 0.5
MAX_DELAY = 8.0
MAX_ATTEMPTS = 4
BUDGET_SECONDS = 20.0


def backoff_delay(attempt: int, kind: str, base: float = BASE_DELAY, cap: float = MAX_DELAY) -> float:
    """Seconds to wait before `attempt` + 1.

    Jitter spans [ceiling/2, ceiling] rather than [0, ceiling]: it still breaks
    up synchronised retries, but it cannot collapse into a retry storm.
    """
    ceiling = min(cap, base * (2 ** (attempt - 1)))
    if kind == "rate_limit":
        # 429 means we are the problem. Give the window real time to roll over.
        ceiling = min(cap, ceiling * 2)
    return random.uniform(ceiling * 0.5, ceiling)


def call_with_retry(
    do_call,
    *,
    feature: str,
    model_name: str,
    prompt_chars: int,
    max_attempts: int = MAX_ATTEMPTS,
    budget_seconds: float = BUDGET_SECONDS,
):
    """Run `do_call(call)` with backoff, recording every attempt.

    `do_call` receives the telemetry handle and must invoke `call.api_ok(resp)`
    once the API has returned, so a parsing failure is not blamed on the API.
    """
    started = time.monotonic()
    last_exc = None

    for attempt in range(1, max_attempts + 1):
        try:
            with llm_telemetry.record(feature, model_name, prompt_chars, attempt=attempt) as call:
                return do_call(call)
        except BaseException as exc:  # noqa: BLE001 - classified and re-raised below
            last_exc = exc
            kind = llm_telemetry.classify_error(exc)

            if kind not in RETRYABLE or attempt == max_attempts:
                raise

            delay = backoff_delay(attempt, kind)
            if time.monotonic() - started + delay > budget_seconds:
                raise
            time.sleep(delay)

    raise last_exc  # unreachable; keeps the contract explicit

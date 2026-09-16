"""Shared helpers for the Citere metrics pipeline.

Every step module imports from here instead of re-implementing:
  - config loading                 (load_config, load_configs, load_raw_corpus, load_answers, load_citations)
  - brand matching / classification (BrandDictionary)
  - position extraction            (BrandDictionary.positions, our_position, competitor_positions)
  - tail cleaning + exclusion      (clean_tail, ends_terminal, chip_on_cut, exclusion_reason)
  - domain handling                (url_host, registrable_domain, match_domain_list)
  - aggregation helpers            (aggregate_bottom_up, share_with_ci)
  - Wilson CI                      (wilson_ci)

Python 3.9 compatible: no match statements, no `X | Y` unions, no parenthesised context managers.
"""
import json
import math
import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import urlsplit

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
DATA_DIR = ROOT / "data"
RAW_CORPUS = DATA_DIR / "raw" / "corpus_master.json"
NORMALIZED_DIR = DATA_DIR / "normalized"
METRICS_DIR = DATA_DIR / "metrics" / "cycle_01"
REGISTRY_DIR = DATA_DIR / "registry"
AUDIT_DIR = ROOT / "audit"

SEED = 42
CONFIG_NAMES = ("brands", "models", "domains", "thresholds")


# --------------------------------------------------------------------------- #
# Config / data loading
# --------------------------------------------------------------------------- #
def load_config(name: str) -> dict:
    """Load config/<name>.yaml. Stops with a clear error if the file is missing."""
    path = CONFIG_DIR / "{}.yaml".format(name)
    if not path.exists():
        raise FileNotFoundError("Missing config file: {} (see normalization_spec.md §1)".format(path))
    with open(path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ValueError("Config {} did not parse to a mapping".format(path))
    return data


def load_configs() -> Dict[str, dict]:
    """Load all four configs; raises if any is missing."""
    return {name: load_config(name) for name in CONFIG_NAMES}


def load_raw_corpus(path: Optional[Path] = None) -> dict:
    with open(path or RAW_CORPUS, "r", encoding="utf-8") as fh:
        return json.load(fh)


def load_answers() -> pd.DataFrame:
    return pd.read_parquet(NORMALIZED_DIR / "answers.parquet")


def load_citations() -> pd.DataFrame:
    return pd.read_parquet(NORMALIZED_DIR / "citations.parquet")


# --------------------------------------------------------------------------- #
# Model families / surfaces
# --------------------------------------------------------------------------- #
def model_maps(models_cfg: dict) -> Tuple[Dict[str, str], Dict[str, str], set]:
    """Return (model -> family, model -> surface_type, set of models to drop)."""
    family = {}
    for fam, versions in models_cfg["families"].items():
        for v in versions:
            family[v] = fam
    surface = {}
    for stype, versions in models_cfg["surface_type"].items():
        for v in versions:
            surface[v] = stype
    drop = set(models_cfg.get("drop") or [])
    return family, surface, drop


# --------------------------------------------------------------------------- #
# Brand matching
# --------------------------------------------------------------------------- #
def _word_pattern(aliases: Sequence[str]) -> "re.Pattern":
    alts = "|".join(re.escape(a) for a in sorted(aliases, key=len, reverse=True))
    return re.compile(r"(?<![A-Za-z0-9])(?:{})(?![A-Za-z0-9])".format(alts), re.IGNORECASE)


class BrandDictionary:
    """Trade-name matching with word boundaries, case-insensitive.

    INN (semaglutide etc.) is never a brand match; it only feeds `inn_only`.
    """

    def __init__(self, brands_cfg: dict):
        self.our_name: str = brands_cfg["our_brand"][0]
        self.our_aliases: List[str] = list(brands_cfg["our_brand"])
        self.our_inn: List[str] = list(brands_cfg.get("our_inn") or [])
        self.competitors: Dict[str, List[str]] = {k: list(v) for k, v in brands_cfg["competitors"].items()}
        self.competitor_inn: Dict[str, List[str]] = {k: list(v) for k, v in (brands_cfg.get("competitor_inn") or {}).items()}

        self._our_re = _word_pattern(self.our_aliases)
        self._inn_re = _word_pattern(self.our_inn) if self.our_inn else None
        self._comp_re: Dict[str, "re.Pattern"] = {name: _word_pattern(al) for name, al in self.competitors.items()}
        self._all_re: Dict[str, "re.Pattern"] = dict(self._comp_re)
        self._all_re[self.our_name] = self._our_re

    # -- presence -----------------------------------------------------------
    def we_present(self, text: str) -> bool:
        return bool(text) and self._our_re.search(text) is not None

    def inn_present(self, text: str) -> bool:
        return bool(text) and self._inn_re is not None and self._inn_re.search(text) is not None

    def competitors_present(self, text: str) -> List[str]:
        if not text:
            return []
        return [name for name, rx in self._comp_re.items() if rx.search(text)]

    def brands_present(self, text: str) -> List[str]:
        """All dictionary brands (ours + competitors) present, in order of first appearance."""
        pos = self.first_offsets(text)
        return [b for b, _ in sorted(pos.items(), key=lambda kv: kv[1])]

    # -- classification -----------------------------------------------------
    def classify_prompt(self, text: str) -> str:
        """C1 unbranded / C2 own-branded / C3 comp-branded / C4 compare — trade names only."""
        ours = self.we_present(text)
        comps = bool(self.competitors_present(text))
        if not ours and not comps:
            return "C1"
        if ours and not comps:
            return "C2"
        if comps and not ours:
            return "C3"
        return "C4"

    # -- positions ----------------------------------------------------------
    def first_offsets(self, text: str) -> Dict[str, int]:
        """Brand -> character offset of first appearance (only brands present)."""
        out = {}
        if not text:
            return out
        for name, rx in self._all_re.items():
            m = rx.search(text)
            if m:
                out[name] = m.start()
        return out

    def positions(self, text: str) -> Dict[str, int]:
        """Brand -> 1-based ordinal by order of first appearance among all dictionary brands."""
        offsets = self.first_offsets(text)
        ordered = sorted(offsets.items(), key=lambda kv: kv[1])
        return {name: i + 1 for i, (name, _) in enumerate(ordered)}

    def our_position(self, text: str) -> Optional[int]:
        return self.positions(text).get(self.our_name)

    def competitor_positions(self, text: str) -> Dict[str, int]:
        pos = self.positions(text)
        return {b: p for b, p in pos.items() if b != self.our_name}


def expected_classes_for_status(status: str) -> set:
    """Which text-derived classes agree with the stored `status` field.

    own -> C2 (question about us), comp -> C3 (question about a competitor),
    mixed -> C1 or C4 (unbranded, or both sides named).
    """
    return {"own": {"C2"}, "comp": {"C3"}, "mixed": {"C1", "C4"}}.get(status, set())


# --------------------------------------------------------------------------- #
# Tail cleaning and exclusion
# --------------------------------------------------------------------------- #
# Source-name chip (cycle-1 DQ decision): a single bare token right after a terminal character at the very end —
# a capitalized word of 2–20 letters (`MotherToBaby`, `CDC`) or a bare domain (`ozempic.com`).
NAME_CHIP_RE = re.compile(r'(?<=[.!?)\u201d"])\s+(?:[A-Z][A-Za-z]{1,19}|[a-z0-9-]+(?:\.[a-z0-9-]+)+)$')
CHIP_PATTERNS = [
    re.compile(r"\s*FDA Access Data\s*\+\d+$"),                    # FDA Access Data +1 (chip with a count)
    re.compile(r"\s*\[?[a-z0-9.-]+\]?\s*\+\d+$", re.IGNORECASE),  # accessdata.fda +1 / [pmc.ncbi.nlm.nih] +2
    re.compile(r"\s*FDA Access Data$"),                            # FDA Access Data
    re.compile(r"\s*\[[a-z0-9.-]+\]$", re.IGNORECASE),             # [accessdata.fda]
    NAME_CHIP_RE,                                                  # ". MotherToBaby" / ". CDC" / ". ozempic.com"
]
_EMOJI_CLASS = (
    "\U0001F000-\U0001FAFF"   # pictographs, emoticons, transport, supplemental symbols
    "\U00002600-\U000027BF"   # misc symbols, dingbats
    "\U00002300-\U000023FF"   # misc technical (⏰ …)
    "\U00002B00-\U00002BFF"   # arrows / stars
    "\U0001F1E6-\U0001F1FF"   # flags
    "‍️︎"      # ZWJ, variation selectors
)
EMOJI_RE = re.compile("[{}]".format(_EMOJI_CLASS))
TRAILING_EMOJI_WS_RE = re.compile("(?:[{}]|\\s)+$".format(_EMOJI_CLASS))
TERMINAL_CHARS = '.!?)»"\u201d\u2019'  # spec set + typographic closing quotes ” ’ (cycle-1 DQ decision)
CHIP_WINDOW = 60


def clean_tail(text: str) -> Tuple[str, bool, bool]:
    """Strip trailing citation chips, emoji and whitespace, repeatedly.

    Returns (clean_text, tail_cleaned, chip_stripped).
      tail_cleaned  — anything at all was stripped (chips, emoji or trailing whitespace beyond a plain rstrip)
      chip_stripped — at least one chip pattern was removed
    Plain trailing whitespace alone does not count as a cleaned tail.
    """
    if text is None:
        return "", False, False
    original = text.rstrip()
    s = original
    chip_stripped = False
    while True:
        before = s
        for rx in CHIP_PATTERNS:
            new = rx.sub("", s)
            if new != s:
                chip_stripped = True
                s = new
        s2 = TRAILING_EMOJI_WS_RE.sub("", s)
        s = s2
        if s == before:
            break
    return s, s != original, chip_stripped


def ends_terminal(text: str) -> bool:
    return bool(text) and text[-1] in TERMINAL_CHARS


def chip_on_cut(raw: str, window: int = CHIP_WINDOW) -> bool:
    """True if a chip pattern in the last `window` chars is glued to a non-terminal character.

    Implementation: strip chips/emoji/whitespace from the end; if a chip was removed, the chip stack
    started within the last `window` characters of the raw text, and the character it follows is
    non-terminal, the chip sits on a cut sentence (e.g. `is contraind FDA Access Data`).
    """
    if not raw:
        return False
    clean, _, chip_stripped = clean_tail(raw)
    if not chip_stripped:
        return False
    # the chip stack starts where the cleaned text ends; it must begin inside the last `window` chars
    if len(raw.rstrip()) - len(clean) > window:
        return False
    return not ends_terminal(clean)


def exclusion_reason(answer_clean: str, answer_raw: str, min_chars: int) -> Optional[str]:
    """Return `too_short` / `chip_on_cut` / `truncated` or None. Precedence in that order."""
    if len(answer_clean) < min_chars:
        return "too_short"
    if chip_on_cut(answer_raw):
        return "chip_on_cut"
    if not ends_terminal(answer_clean):
        return "truncated"
    return None


# --------------------------------------------------------------------------- #
# Domains
# --------------------------------------------------------------------------- #
_SECOND_LEVEL = {"co", "com", "org", "net", "gov", "ac", "edu", "or", "ne", "gob", "gouv", "ltd", "plc", "sch"}  # nhs.uk is itself registrable


def url_host(url: str) -> str:
    """Lower-cased hostname with a leading `www.` removed. Bare domains without a scheme are accepted."""
    if not isinstance(url, str) or not url.strip():
        return ""
    u = url.strip()
    parts = urlsplit(u if "://" in u else "//" + u)
    host = (parts.hostname or "").lower().strip(".")
    if host.startswith("www."):
        host = host[4:]
    return host


def registrable_domain(host: str) -> str:
    """Approximate public-suffix reduction: `sub.mayoclinic.org` -> `mayoclinic.org`, `x.nhs.uk` -> `nhs.uk`,
    `foo.bbc.co.uk` -> `bbc.co.uk`. Good enough for aggregation; no external suffix list."""
    if not host:
        return ""
    labels = host.split(".")
    if len(labels) <= 2:
        return host
    if len(labels[-1]) == 2 and labels[-2] in _SECOND_LEVEL:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


def match_domain_list(host: str, entries: Iterable[str]) -> Optional[str]:
    """Longest-suffix match of `host` against config entries (exact host or a sub-domain of it)."""
    best = None
    for e in entries:
        e = e.lower()
        if host == e or host.endswith("." + e):
            if best is None or len(e) > len(best):
                best = e
    return best


# --------------------------------------------------------------------------- #
# Wilson CI and aggregation
# --------------------------------------------------------------------------- #
def wilson_ci(k: float, n: float, z: float = 1.959964) -> Tuple[float, float]:
    """Wilson score interval for a proportion k/n. Returns (nan, nan) when n == 0."""
    if n is None or n <= 0 or k is None or (isinstance(k, float) and math.isnan(k)):
        return (float("nan"), float("nan"))
    p = k / n
    if p < 0 or p > 1 or math.isnan(p):  # not a proportion (e.g. a mean position): CI undefined
        return (float("nan"), float("nan"))
    denom = 1.0 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    lo, hi = max(0.0, centre - half), min(1.0, centre + half)
    return (round(lo, 12), round(hi, 12))


def share_with_ci(values: Iterable[float]) -> Dict[str, float]:
    """Mean of 0/1 values with a Wilson 95% CI (n = number of values)."""
    vals = [v for v in values if v is not None and not (isinstance(v, float) and math.isnan(v))]
    n = len(vals)
    k = float(sum(vals))
    lo, hi = wilson_ci(k, n)
    return {"share": (k / n) if n else float("nan"), "n": n, "ci_lo": lo, "ci_hi": hi}


def aggregate_bottom_up(
    df: pd.DataFrame,
    value: str,
    by: Sequence[str] = (),
    family_col: str = "model_family",
    model_col: str = "model",
    prompt_keys: Sequence[str] = ("pid", "run"),
    family_weights: Optional[Dict[str, float]] = None,
    dropna: bool = True,
    ci_basis: str = "groups",
) -> Dict[str, pd.DataFrame]:
    """Runbook aggregation: repeats -> prompt×model -> model family -> overall, equal family weights.

    `value` is a numeric column (0/1 for shares). Returns three frames:
      pm      — one row per (by, prompt_keys, model): mean over repeats, n_repeats
      family  — one row per (by, family): mean over prompt×model groups (all versions pooled), n_groups, ci_lo/ci_hi
      overall — one row per (by): equal-weight (or `family_weights`) mean over families, n_groups, ci_lo/ci_hi
    Wilson CIs use k = share × n with n = number of prompt×model groups (`ci_basis="groups"`, runbook default)
    or n = number of underlying answers (`ci_basis="answers"`, visibility_score_spec §7); meaningful for 0/1 values.
    """
    if ci_basis not in ("groups", "answers"):
        raise ValueError("ci_basis must be 'groups' or 'answers'")
    by = list(by)
    d = df if not dropna else df.dropna(subset=[value])
    keys = []
    for k in by + list(prompt_keys) + [model_col, family_col]:
        if k not in keys:
            keys.append(k)  # family_col may equal model_col (per-version aggregation)
    pm = (
        d.groupby(keys, dropna=False)[value]
        .agg(["mean", "size"])
        .rename(columns={"mean": value, "size": "n_repeats"})
        .reset_index()
    )
    fam = pm.groupby(by + [family_col], dropna=False).agg(**{value: (value, "mean"), "n_groups": (value, "size"), "n_answers": ("n_repeats", "sum")}).reset_index()
    n_col = "n_groups" if ci_basis == "groups" else "n_answers"
    fam[["ci_lo", "ci_hi"]] = fam.apply(lambda r: pd.Series(wilson_ci(r[value] * r[n_col], r[n_col])), axis=1)

    def _overall(g: pd.DataFrame) -> pd.Series:
        if family_weights:
            w = g[family_col].map(lambda f: family_weights.get(f, 0.0)).astype(float)
            m = float((g[value] * w).sum() / w.sum()) if w.sum() > 0 else float("nan")
        else:
            m = float(g[value].mean())
        n = int(g[n_col].sum())
        lo, hi = wilson_ci(m * n, n)
        return pd.Series({value: m, "n_groups": int(g["n_groups"].sum()), "n_answers": int(g["n_answers"].sum()),
                          "n_families": len(g), "ci_lo": lo, "ci_hi": hi})

    if by:
        overall = fam.groupby(by, dropna=False).apply(_overall).reset_index()
    else:
        overall = _overall(fam).to_frame().T
    return {"pm": pm, "family": fam, "overall": overall}


def to_float_or_none(x) -> Optional[float]:
    if x is None:
        return None
    if isinstance(x, (int, float)):
        return float(x) if not (isinstance(x, float) and math.isnan(x)) else None
    s = str(x).strip()
    if s == "":
        return None
    try:
        return float(s)
    except ValueError:
        return None


# --------------------------------------------------------------------------- #
# Topic groups (diagnosis_prioritization_spec §2)
# --------------------------------------------------------------------------- #
def topic_group(topic: str, subtopic: Optional[str], zone: str) -> Tuple[str, str]:
    """(group_id, kind): `topic × subtopic` when subtopic is populated and != "Other", else `topic × zone`."""
    if subtopic and str(subtopic).strip() and str(subtopic).strip() != "Other":
        return ("{} × {}".format(topic, subtopic), "topic×subtopic")
    return ("{} × {}".format(topic, zone), "topic×zone")


# --------------------------------------------------------------------------- #
# Position weight (visibility_score_spec §4.3)
# --------------------------------------------------------------------------- #
def position_weight(position: Optional[float], decay: float) -> float:
    """Evertune weight: 100 × decay^(pos − 1); absent (None/NaN/<1) → 0."""
    if position is None or (isinstance(position, float) and math.isnan(position)) or position < 1:
        return 0.0
    return 100.0 * (decay ** (float(position) - 1.0))

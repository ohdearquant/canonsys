"""Jurisdiction and holiday loader for policies/ repo."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path


@dataclass(frozen=True, slots=True)
class CalendarConfig:
    uses_federal_holidays: bool
    has_custom_holidays: bool


@dataclass(frozen=True, slots=True)
class JurisdictionConfig:
    code: str
    name: str
    country: str
    parent: str | None
    calendar: CalendarConfig
    aliases: frozenset[str]


def _norm_code(s: str) -> str:
    """Uppercase with hyphens."""
    return s.strip().upper().replace("_", "-")


def _norm_alias(s: str) -> str:
    """Lowercase, collapsed whitespace."""
    s = s.strip().lower().replace("_", " ").replace("-", " ")
    return " ".join(s.split())


def _apply_observance(holiday: date) -> date:
    """Saturday -> Friday, Sunday -> Monday."""
    weekday = holiday.weekday()
    if weekday == 5:
        return holiday - timedelta(days=1)
    elif weekday == 6:
        return holiday + timedelta(days=1)
    return holiday


class JurisdictionRegistry:
    """Registry of jurisdiction configs loaded from policies/ repo."""

    def __init__(
        self,
        *,
        root: Path,
        configs: dict[str, JurisdictionConfig],
        code_to_dir: dict[str, Path],
        alias_to_code: dict[str, str],
        strict: bool,
    ) -> None:
        self._root = root
        self._configs = configs
        self._code_to_dir = code_to_dir
        self._alias_to_code = alias_to_code
        self._strict = strict
        self._holidays_cache: dict[tuple[str, int], frozenset[date]] = {}

    @property
    def codes(self) -> frozenset[str]:
        return frozenset(self._configs.keys())

    def get(self, code: str) -> JurisdictionConfig | None:
        return self._configs.get(_norm_code(code))

    def require(self, code: str) -> JurisdictionConfig:
        cfg = self.get(code)
        if cfg is None:
            raise KeyError(f"Unknown jurisdiction: {code!r}")
        return cfg

    def normalize(self, value: str) -> str | None:
        """Normalize to canonical code. Returns None if unknown."""
        if not value:
            return None
        code = _norm_code(value)
        if code in self._configs:
            return code
        return self._alias_to_code.get(_norm_alias(value))

    def normalize_required(self, value: str) -> str:
        code = self.normalize(value)
        if code is None:
            raise ValueError(f"Unknown jurisdiction: {value!r}")
        return code

    def hierarchy(self, code: str) -> tuple[str, ...]:
        """Get hierarchy most-specific-first: ('US-NYC', 'US-NY', 'US-FEDERAL')."""
        code = _norm_code(code)
        out: list[str] = []
        cur: str | None = code
        while cur is not None:
            out.append(cur)
            cfg = self._configs.get(cur)
            cur = cfg.parent if cfg else None
        return tuple(out)

    def get_holidays(self, code: str, year: int) -> frozenset[date]:
        """Get observed holidays for jurisdiction and year (cached)."""
        code = _norm_code(code)
        key = (code, year)
        if key in self._holidays_cache:
            return self._holidays_cache[key]

        cfg = self.require(code)
        holidays: set[date] = set()

        if cfg.calendar.uses_federal_holidays and code != "US-FEDERAL":
            holidays |= set(self.get_holidays("US-FEDERAL", year))

        if cfg.calendar.has_custom_holidays:
            holidays |= set(self._load_holidays(code, year))

        # Check next year for holidays observed in this year
        try:
            for d in self._load_holidays_raw(code, year + 1):
                obs = _apply_observance(d)
                if obs.year == year:
                    holidays.add(obs)
        except FileNotFoundError:
            pass

        result = frozenset(holidays)
        self._holidays_cache[key] = result
        return result

    def _load_holidays(self, code: str, year: int) -> frozenset[date]:
        raw = self._load_holidays_raw(code, year)
        return frozenset(_apply_observance(d) for d in raw if _apply_observance(d).year == year)

    def _load_holidays_raw(self, code: str, year: int) -> frozenset[date]:
        jdir = self._code_to_dir.get(code)
        if jdir is None:
            if self._strict:
                raise FileNotFoundError(f"No directory for: {code}")
            return frozenset()

        path = jdir / "holidays" / f"{year}.toml"
        if not path.exists():
            if self._strict:
                raise FileNotFoundError(f"No holiday file: {path}")
            return frozenset()

        data = tomllib.loads(path.read_text())
        dates: set[date] = set()
        for section, values in data.items():
            if section == "metadata" or not isinstance(values, dict):
                continue
            for v in values.values():
                if isinstance(v, str):
                    try:
                        dates.add(date.fromisoformat(v))
                    except ValueError:
                        pass
        return frozenset(dates)


def load_jurisdictions(root: str | Path, *, strict: bool = True) -> JurisdictionRegistry:
    """Load registry from policies/jurisdictions/ directory."""
    root = Path(root)
    configs: dict[str, JurisdictionConfig] = {}
    code_to_dir: dict[str, Path] = {}
    alias_to_code: dict[str, str] = {}

    for jdir in sorted(root.iterdir()):
        if not jdir.is_dir():
            continue
        cfg_path = jdir / "config.toml"
        if not cfg_path.exists():
            continue

        raw = tomllib.loads(cfg_path.read_text())
        j = raw.get("jurisdiction", {})
        cal = raw.get("calendar", {})
        aliases = raw.get("aliases", {}).get("values", [])
        code = _norm_code(j["code"])

        jc = JurisdictionConfig(
            code=code,
            name=j["name"],
            country=j["country"],
            parent=_norm_code(j["parent"]) if j.get("parent") else None,
            calendar=CalendarConfig(
                uses_federal_holidays=bool(cal.get("uses_federal_holidays", False)),
                has_custom_holidays=bool(cal.get("has_custom_holidays", False)),
            ),
            aliases=frozenset(str(a) for a in aliases),
        )

        if code in configs and strict:
            raise ValueError(f"Duplicate code {code} in {cfg_path}")
        configs[code] = jc
        code_to_dir[code] = jdir

    # Build alias index
    for code, jc in configs.items():
        for a in list(jc.aliases) + [code]:
            key = _norm_alias(a)
            prev = alias_to_code.get(key)
            if prev is not None and prev != code and strict:
                raise ValueError(f"Alias collision: {a!r} -> {prev} and {code}")
            alias_to_code[key] = code

    # Validate parents
    if strict:
        for code, jc in configs.items():
            if jc.parent and jc.parent not in configs:
                raise ValueError(f"{code} has unknown parent {jc.parent}")

    return JurisdictionRegistry(
        root=root,
        configs=configs,
        code_to_dir=code_to_dir,
        alias_to_code=alias_to_code,
        strict=strict,
    )

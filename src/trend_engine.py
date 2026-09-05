"""今日「誰向けに・何を」投稿するかを毎回決めるエンジン。

固定ジャンルにせず、以下を毎回組み合わせて決める。
  1. カレンダー（セール・季節・ギフト行事）
  2. 曜日・時間帯・日付（5と0のつく日 など）
  3. 楽天ランキング（年代×性別のリアルタイム上位 = 今売れている物）
  4. 直近の投稿履歴（同じペルソナ・ジャンルの連続を避ける）
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

from .config import CALENDAR_FILE, GENRES, PERSONAS, Persona

SLOTS = {
    "morning": ("朝（通勤・家事前）", "サッと読める。今日1日ラクになる系・セール告知"),
    "noon": ("昼（休憩中）", "休憩中の気晴らし。自分へのご褒美・便利グッズ"),
    "night": ("夜（購買のピーク）", "楽天は21〜24時が最も売れる。じっくり系・高単価もOK"),
}


@dataclass
class Theme:
    persona: Persona
    title: str                     # 例: 「敬老の日ギフト × 30代女性」
    reason: str                    # なぜ今日これか（投稿文の材料）
    keywords: list[str] = field(default_factory=list)
    genres: list[int] = field(default_factory=list)
    hooks: list[str] = field(default_factory=list)   # セール・記念日などの一言
    event_type: str = "baseline"   # sale / gift / season / baseline
    slot: str = "night"

    def describe(self) -> str:
        g = ", ".join(GENRES.get(x, str(x)) for x in self.genres) or "ランキング総合"
        return (f"テーマ: {self.title}\n  誰向け: {self.persona.label}\n  理由: {self.reason}\n"
                f"  ジャンル: {g}\n  検索語: {', '.join(self.keywords) or '-'}\n"
                f"  フック: {' / '.join(self.hooks) or '-'}")


def _load_calendar() -> dict[str, Any]:
    with open(CALENDAR_FILE, encoding="utf-8") as f:
        return json.load(f)


def _d(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def active_events(today: date, cal: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for ev in cal["events"]:
        start, end = _d(ev["start"]), _d(ev["end"])
        lead = int(ev.get("lead_days", 0))
        if start - timedelta(days=lead) <= today <= end:
            e = dict(ev)
            e["days_to_start"] = (start - today).days
            e["in_progress"] = start <= today <= end
            out.append(e)
    return out


def recurring_hooks(today: date, cal: dict[str, Any]) -> list[str]:
    hooks = []
    for r in cal.get("recurring", []):
        if today.day in r.get("days_of_month", []):
            hooks.append(f"{r['name']}：{r['hook']}")
    wd = cal.get("weekday_hooks", {}).get(str(today.weekday()), "")
    if wd:
        hooks.append(wd)
    return hooks


def _event_score(e: dict[str, Any]) -> float:
    """イベントの「今日出す価値」。"""
    t = e.get("type", "season")
    base = {"sale": 3.0, "gift": 2.5, "season": 1.5}.get(t, 1.0)
    if e["in_progress"]:
        return base + 1.0
    # 開始前: 近いほど高い（ギフトは2〜10日前がピーク）
    d = e["days_to_start"]
    if t == "gift":
        return base + (1.0 if 2 <= d <= 10 else 0.4)
    return base + max(0.0, 1.0 - d / 10)


def _pick_persona(candidates: list[str], history: list[dict[str, Any]], today: date, slot: str) -> Persona:
    """候補の中から、直近で使っていないペルソナを優先して選ぶ。"""
    keys = [k for k in candidates if k in PERSONAS] or list(PERSONAS)
    # 「全年代向け」のイベント（セール等）でも、投稿は誰か一人に向けて書いた方が反応が良い。
    # そのため 'all' は「全ペルソナからローテーション」と解釈する。
    keys = [k for k in keys if k != "all"] or [k for k in PERSONAS if k != "all"]
    recent = [h.get("persona") for h in history[-6:]]
    fresh = [k for k in keys if k not in recent]
    pool = fresh or keys
    idx = (today.toordinal() + {"morning": 0, "noon": 1, "night": 2}.get(slot, 0)) % len(pool)
    return PERSONAS[pool[idx]]


def decide_theme(today: date, slot: str, history: list[dict[str, Any]]) -> Theme:
    cal = _load_calendar()
    events = active_events(today, cal)
    hooks = recurring_hooks(today, cal)
    slot_label, slot_hint = SLOTS.get(slot, SLOTS["night"])

    # 同じイベントを直近3投稿で使っていたら少し下げる（飽き防止）
    recent_titles = [h.get("theme", "") for h in history[-3:]]
    scored = []
    for e in events:
        s = _event_score(e)
        if any(e["name"] in t for t in recent_titles):
            s -= 1.2
        scored.append((s, e))
    scored.sort(key=lambda x: -x[0])

    # ベースライン（イベント無し）のスコアは 2.0。イベントがそれを超えたら採用
    if scored and scored[0][0] >= 2.0:
        s, e = scored[0]
        persona = _pick_persona(e.get("targets", ["all"]), history, today, slot)
        genres = e.get("genres") or persona.genres[:3]
        when = "開催中" if e["in_progress"] else f"{e['days_to_start']}日後"
        ev_hooks = [h for h in [e.get("hook", "")] if h]
        return Theme(
            persona=persona,
            title=f"{e['name']}（{when}） × {persona.label}",
            reason=f"{e['name']}が{when}。{slot_label}の投稿なので「{slot_hint}」。",
            keywords=list(e.get("keywords", [])),
            genres=list(genres),
            hooks=ev_hooks + hooks,
            event_type=e.get("type", "season"),
            slot=slot,
        )

    # イベントが無い日: ペルソナをローテーションし、そのペルソナのリアルタイムランキングから拾う
    persona = _pick_persona([k for k in PERSONAS if k != "all"], history, today, slot)
    # ジャンルもローテーション（同じペルソナでも毎回違うジャンル）
    gi = (today.toordinal() + len(history)) % max(1, len(persona.genres))
    genres = [persona.genres[gi]] + [g for g in persona.genres if g != persona.genres[gi]][:1]
    return Theme(
        persona=persona,
        title=f"今売れている物 × {persona.label}",
        reason=f"特定イベント無し。{persona.label}のリアルタイムランキング上位から、{slot_label}に合うものを選ぶ。{slot_hint}",
        keywords=[],
        genres=genres,
        hooks=hooks,
        event_type="baseline",
        slot=slot,
    )

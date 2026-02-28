#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import random
import time
from dataclasses import dataclass
from typing import Dict, List, Set

from flask import Flask, render_template, request, redirect, url_for, session

app = Flask(__name__)
app.secret_key = "troque-esta-chave-para-algo-seu"  # ok local


# ----------------------------
# Modelo
# ----------------------------
@dataclass
class Question:
    id: str
    topic: str
    question: str
    choices: Dict[str, str]
    correct: List[str]
    explanation: str
    choice_explanations: Dict[str, str]
    tags: List[str]


BANK_DIR_DEFAULT = os.environ.get("QUIZ_BANK_DIR", "banks")
BANK_PATH_DEFAULT = os.environ.get(
    "QUIZ_BANK",
    os.path.join(BANK_DIR_DEFAULT, "aws_saa_c03.json")
)


def list_banks(bank_dir: str) -> List[str]:
    if not os.path.isdir(bank_dir):
        return []
    items = [n for n in os.listdir(bank_dir) if n.lower().endswith(".json")]
    items.sort(key=lambda s: s.lower())
    return items


def safe_join_bank_path(bank_dir: str, filename: str) -> str:
    filename = (filename or "").strip().lstrip("/").replace("\\", "/")
    if not filename:
        raise ValueError("Selecione um banco.")
    if "/" in filename or ".." in filename:
        raise ValueError("Nome de arquivo inválido.")
    return os.path.join(bank_dir, filename)


def load_bank(path: str) -> List[Question]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    qs: List[Question] = []
    for q in data.get("questions", []):
        choices = dict(q["choices"])
        ce = dict(q.get("choice_explanations", {}))
        for k in choices.keys():
            ce.setdefault(k, "")

        qs.append(
            Question(
                id=str(q["id"]),
                topic=str(q.get("topic", "geral")),
                question=str(q["question"]).strip(),
                choices=choices,
                correct=[c.upper() for c in q["correct"]],
                explanation=str(q.get("explanation", "")).strip(),
                choice_explanations=ce,
                tags=list(q.get("tags", [])),
            )
        )
    return qs


def get_bank_dir() -> str:
    return session.get("bank_dir", BANK_DIR_DEFAULT)


def get_bank_path() -> str:
    return session.get("bank_path", BANK_PATH_DEFAULT)


def get_question_by_id(qs: List[Question], qid: str) -> Question:
    for q in qs:
        if q.id == qid:
            return q
    raise KeyError(qid)


def _now() -> int:
    return int(time.time())


def _ensure_session_defaults():
    session.setdefault("q_ids", [])
    session.setdefault("idx", 0)
    session.setdefault("score", 0)
    session.setdefault("wrong", [])
    session.setdefault("answers", {})
    session.setdefault("last_feedback", None)
    session.setdefault("exam_mode", False)
    session.setdefault("exam_duration_sec", 0)
    session.setdefault("exam_started_at", 0)


def _compute_timer():
    """Retorna (enabled, remaining_sec, elapsed_sec)."""
    exam_mode = bool(session.get("exam_mode", False))
    dur = int(session.get("exam_duration_sec", 0) or 0)
    started = int(session.get("exam_started_at", 0) or 0)

    if not exam_mode or dur <= 0 or started <= 0:
        return (False, 0, 0)

    elapsed = max(0, _now() - started)
    remaining = max(0, dur - elapsed)
    return (True, remaining, elapsed)


# ----------------------------
# Rotas
# ----------------------------
@app.get("/")
def home():
    _ensure_session_defaults()

    bank_dir = get_bank_dir()
    banks = list_banks(bank_dir)

    current_path = get_bank_path()
    current_file = os.path.basename(current_path) if current_path else ""
    if current_file not in banks:
        current_file = banks[0] if banks else ""

    return render_template(
        "home.html",
        bank_dir=bank_dir,
        banks=banks,
        current_file=current_file,
        current_path=current_path,
        error=None,
    )


@app.post("/start")
def start():
    _ensure_session_defaults()
    try:
        bank_dir = get_bank_dir()
        banks = list_banks(bank_dir)

        selected_bank = request.form.get("bank_select", "")
        manual_path = (request.form.get("bank_path_manual") or "").strip()

        if manual_path:
            if not os.path.isfile(manual_path):
                raise FileNotFoundError(f"Arquivo não encontrado: {manual_path}")
            bank_path = manual_path
        else:
            bank_path = safe_join_bank_path(bank_dir, selected_bank)
            if not os.path.isfile(bank_path):
                raise FileNotFoundError(f"Banco não encontrado: {bank_path}")

        session["bank_path"] = bank_path

        questions = load_bank(bank_path)

        topic = (request.form.get("topic") or "").strip().lower()
        tags_str = (request.form.get("tags") or "").strip().lower()
        tags_any: Set[str] = set([t.strip() for t in tags_str.split(",") if t.strip()])

        if topic:
            questions = [q for q in questions if q.topic.lower() == topic]
        if tags_any:
            questions = [q for q in questions if any(t.lower() in tags_any for t in q.tags)]

        shuffle = request.form.get("shuffle") == "on"
        if shuffle:
            random.shuffle(questions)

        n = int(request.form.get("n") or 20)
        questions = questions[: min(n, len(questions))]

        # modo prova
        exam_mode = request.form.get("exam_mode") == "on"
        session["exam_mode"] = exam_mode

        if exam_mode:
            minutes = int(request.form.get("exam_minutes") or 0)
            minutes = max(1, minutes)
            session["exam_duration_sec"] = minutes * 60
            session["exam_started_at"] = _now()
        else:
            session["exam_duration_sec"] = 0
            session["exam_started_at"] = 0

        session["q_ids"] = [q.id for q in questions]
        session["idx"] = 0
        session["score"] = 0
        session["wrong"] = []
        session["answers"] = {}
        session["last_feedback"] = None

        return redirect(url_for("question"))

    except Exception as e:
        bank_dir = get_bank_dir()
        banks = list_banks(bank_dir)
        current_path = get_bank_path()
        current_file = os.path.basename(current_path) if current_path else ""
        if current_file not in banks:
            current_file = banks[0] if banks else ""

        return render_template(
            "home.html",
            bank_dir=bank_dir,
            banks=banks,
            current_file=current_file,
            current_path=current_path,
            error=str(e),
        ), 400


@app.get("/q")
def question():
    _ensure_session_defaults()

    bank_path = get_bank_path()
    if not os.path.isfile(bank_path):
        return redirect(url_for("home"))

    q_ids: List[str] = session.get("q_ids", [])
    idx = int(session.get("idx", 0))

    if not q_ids:
        return redirect(url_for("home"))

    # timer: se acabou, encerra prova
    timer_enabled, remaining, elapsed = _compute_timer()
    if timer_enabled and remaining <= 0:
        return redirect(url_for("result"))

    if idx >= len(q_ids):
        return redirect(url_for("result"))

    qs = load_bank(bank_path)
    q = get_question_by_id(qs, q_ids[idx])

    multi = len(q.correct) > 1
    input_type = "checkbox" if multi else "radio"
    keys = sorted(q.choices.keys())

    return render_template(
        "question.html",
        bank_path=bank_path,
        q=q,
        idx=idx,
        total=len(q_ids),
        keys=keys,
        input_type=input_type,
        timer_enabled=timer_enabled,
        timer_remaining=remaining,
        timer_elapsed=elapsed,
        exam_mode=bool(session.get("exam_mode", False)),
    )


@app.post("/answer")
def answer():
    _ensure_session_defaults()

    bank_path = get_bank_path()
    if not os.path.isfile(bank_path):
        return redirect(url_for("home"))

    q_ids: List[str] = session.get("q_ids", [])
    idx = int(session.get("idx", 0))
    if idx >= len(q_ids):
        return redirect(url_for("result"))

    qs = load_bank(bank_path)
    q = get_question_by_id(qs, q_ids[idx])

    selected = request.form.getlist("ans")
    selected = sorted([s.upper() for s in selected])

    correct = sorted(q.correct)
    ok = selected == correct

    answers = session.get("answers", {})
    answers[q.id] = selected
    session["answers"] = answers

    if ok:
        session["score"] = int(session.get("score", 0)) + 1
    else:
        wrong = session.get("wrong", [])
        wrong.append(q.id)
        session["wrong"] = wrong

    session["last_feedback"] = {
        "qid": q.id,
        "selected": selected,
        "ok": ok,
    }

    session["idx"] = idx + 1

    # modo prova: sem feedback
    if bool(session.get("exam_mode", False)):
        return redirect(url_for("question"))

    return redirect(url_for("feedback"))


@app.get("/feedback")
def feedback():
    _ensure_session_defaults()

    if bool(session.get("exam_mode", False)):
        return redirect(url_for("question"))

    bank_path = get_bank_path()
    if not os.path.isfile(bank_path):
        return redirect(url_for("home"))

    fb = session.get("last_feedback")
    if not fb:
        return redirect(url_for("question"))

    qs = load_bank(bank_path)
    q = get_question_by_id(qs, fb["qid"])

    selected_list = list(fb["selected"])
    correct_list = list(q.correct)
    ok = bool(fb["ok"])

    selected_str = ", ".join(sorted(selected_list)) if selected_list else "(vazia)"
    correct_str = ", ".join(sorted(correct_list))
    keys = sorted(q.choices.keys())

    return render_template(
        "feedback.html",
        bank_path=bank_path,
        q=q,
        ok=ok,
        selected_str=selected_str,
        correct_str=correct_str,
        selected_set=set(selected_list),
        correct_set=set(correct_list),
        keys=keys,
    )


@app.get("/result")
def result():
    _ensure_session_defaults()

    bank_path = get_bank_path()
    q_ids: List[str] = session.get("q_ids", [])
    score = int(session.get("score", 0))
    wrong: List[str] = session.get("wrong", [])
    total = len(q_ids) if q_ids else 0
    pct = (score / total * 100.0) if total else 0.0

    timer_enabled, remaining, elapsed = _compute_timer()
    exam_mode = bool(session.get("exam_mode", False))

    stats = {
        "total": total,
        "score": score,
        "pct": pct,
        "wrong_count": len(wrong),
        "elapsed_sec": elapsed if exam_mode else 0,
        "remaining_sec": remaining if exam_mode else 0,
        "exam_mode": exam_mode,
    }

    return render_template(
        "result.html",
        bank_path=bank_path,
        q_ids=q_ids,
        wrong=wrong,
        stats=stats,
    )


@app.get("/review")
def review():
    _ensure_session_defaults()

    bank_path = get_bank_path()
    if not os.path.isfile(bank_path):
        return redirect(url_for("home"))

    wrong_ids = session.get("wrong", [])
    if not wrong_ids:
        return redirect(url_for("result"))

    qs = load_bank(bank_path)
    by_id = {q.id: q for q in qs}
    wrong_questions = [by_id[qid] for qid in wrong_ids if qid in by_id]

    # keys padrão para render
    keys = sorted(wrong_questions[0].choices.keys()) if wrong_questions else ["A", "B", "C", "D"]

    return render_template(
        "review.html",
        bank_path=bank_path,
        wrong_questions=wrong_questions,
        keys=keys,
    )


@app.get("/explanations")
def explanations():
    _ensure_session_defaults()

    bank_path = get_bank_path()
    if not os.path.isfile(bank_path):
        return redirect(url_for("home"))

    q_ids: List[str] = session.get("q_ids", [])
    if not q_ids:
        return redirect(url_for("home"))

    qs = load_bank(bank_path)
    by_id = {q.id: q for q in qs}
    session_questions = [by_id[qid] for qid in q_ids if qid in by_id]
    keys = sorted(session_questions[0].choices.keys()) if session_questions else ["A", "B", "C", "D"]

    return render_template(
        "explanations.html",
        bank_path=bank_path,
        session_questions=session_questions,
        keys=keys,
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
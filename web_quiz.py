#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import random
import time
from dataclasses import dataclass
from typing import Dict, List, Set, Tuple

from flask import Flask, render_template, request, redirect, url_for, session

app = Flask(__name__)
app.secret_key = "troque-esta-chave-para-algo-seu"  # ok local/offline

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


# ----------------------------
# Config
# ----------------------------
ALL_BANKS_SENTINEL = "__ALL__"

PROJECT_DIR = os.path.abspath(os.path.dirname(__file__))
BANK_DIR_DEFAULT = os.environ.get("QUIZ_BANK_DIR", os.path.join(PROJECT_DIR, "banks"))
BANK_PATH_DEFAULT = os.environ.get("QUIZ_BANK", os.path.join(BANK_DIR_DEFAULT, "aws_saa_c03.json"))


# ----------------------------
# Helpers bancos
# ----------------------------
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


def load_all_banks(bank_dir: str) -> List[Question]:
    qs: List[Question] = []
    for name in list_banks(bank_dir):
        path = os.path.join(bank_dir, name)
        try:
            qs.extend(load_bank(path))
        except Exception:
            # se algum json estiver ruim, a gente não derruba o app
            continue
    # remove duplicadas por id (mantém a primeira)
    seen = set()
    uniq: List[Question] = []
    for q in qs:
        if q.id in seen:
            continue
        seen.add(q.id)
        uniq.append(q)
    return uniq


def get_question_by_id(qs: List[Question], qid: str) -> Question:
    for q in qs:
        if q.id == qid:
            return q
    raise KeyError(qid)


# ----------------------------
# Sessão / Timer
# ----------------------------
def _now() -> int:
    return int(time.time())


def _ensure_session_defaults():
    session.setdefault("q_ids", [])
    session.setdefault("idx", 0)
    session.setdefault("score", 0)
    session.setdefault("wrong", [])
    session.setdefault("answers", {})
    session.setdefault("last_feedback", None)

    session.setdefault("bank_dir", BANK_DIR_DEFAULT)
    session.setdefault("bank_path", BANK_PATH_DEFAULT)
    session.setdefault("bank_select", os.path.basename(BANK_PATH_DEFAULT))

    session.setdefault("exam_mode", False)
    session.setdefault("exam_duration_sec", 0)
    session.setdefault("exam_started_at", 0)

    session.setdefault("session_mode", "normal")  # normal | weighted65
    session.setdefault("weighted65_enabled", False)


def _compute_timer() -> Tuple[bool, int, int]:
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
# Sorteio ponderado 65 (simples e efetivo)
# ----------------------------
def _pick_weighted_65(all_qs: List[Question]) -> List[Question]:
    """
    Sorteio 65 com cotas por 'macro-temas' (aproximação do que mais cai na SAA):
    - networking/vpc/dns/route53
    - s3/storage/cloudfront/edge
    - iam/security/kms
    - compute/ec2/elb/scaling
    - databases (rds/aurora/dynamodb)
    - serverless/event-driven
    - observability/monitoring/cloudwatch/cloudtrail
    - hadr/backup/dr-pattern/resilience
    - cost/optimization/performance
    """

    def bucket(q: Question) -> str:
        t = (q.topic or "").lower()
        tags = set([x.lower() for x in (q.tags or [])])

        # networking
        if t in {"vpc", "networking", "dns", "route53", "routing", "connectivity"} or (
            {"vpc", "route53", "dns", "hybrid", "dx", "vpn", "tgw"} & tags
        ):
            return "networking"

        # edge/s3
        if t in {"s3", "storage", "edge", "cloudfront"} or ({"s3", "cloudfront", "edge"} & tags):
            return "edge_storage"

        # security/iam/kms
        if t in {"iam", "security", "kms", "sts", "organizations", "governance"} or (
            {"iam", "security", "kms", "sts", "scp", "organizations"} & tags
        ):
            return "security"

        # databases
        if t in {"rds", "aurora", "dynamodb", "databases"} or ({"rds", "aurora", "dynamodb"} & tags):
            return "databases"

        # compute
        if t in {"ec2", "elb", "scaling", "compute", "containers"} or (
            {"ec2", "alb", "nlb", "autoscaling", "ecs", "eks"} & tags
        ):
            return "compute"

        # serverless/event-driven
        if t in {"serverless", "lambda", "event-driven", "messaging", "sqs", "eventbridge", "apigw"} or (
            {"lambda", "sqs", "eventbridge", "apigw"} & tags
        ):
            return "serverless"

        # observability
        if t in {"observability", "monitoring", "cloudwatch", "cloudtrail"} or (
            {"cloudwatch", "cloudtrail", "monitoring"} & tags
        ):
            return "observability"

        # hadr/backup
        if t in {"hadr", "ha-dr", "backup", "backup-restore", "dr-pattern", "resilience"} or (
            {"dr", "backup", "resilience", "multi-region"} & tags
        ):
            return "hadr"

        # cost/perf
        if t in {"cost", "performance"} or ({"cost", "performance"} & tags):
            return "cost_perf"

        return "misc"

    buckets: Dict[str, List[Question]] = {}
    for q in all_qs:
        buckets.setdefault(bucket(q), []).append(q)

    # cotas (somam 65)
    quotas = {
        "networking": 14,
        "edge_storage": 10,
        "security": 10,
        "compute": 9,
        "databases": 8,
        "serverless": 6,
        "observability": 3,
        "hadr": 3,
        "cost_perf": 2,
    }

    picked: List[Question] = []
    used_ids: Set[str] = set()

    # helper: sorteia sem repetir
    def sample_from(lst: List[Question], k: int):
        random.shuffle(lst)
        for q in lst:
            if len(picked) >= 65:
                return
            if q.id in used_ids:
                continue
            picked.append(q)
            used_ids.add(q.id)
            k -= 1
            if k <= 0:
                return

    # aplica cotas
    for b, k in quotas.items():
        sample_from(buckets.get(b, []), k)

    # completa até 65 com o que sobrar (prioriza buckets mais “quentes”)
    fill_order = ["networking", "edge_storage", "security", "compute", "databases", "serverless", "observability", "hadr", "cost_perf", "misc"]
    i = 0
    while len(picked) < 65 and i < len(fill_order):
        sample_from(buckets.get(fill_order[i], []), 9999)
        i += 1

    # fallback se banco for pequeno
    if len(picked) < 65:
        pool = [q for q in all_qs if q.id not in used_ids]
        random.shuffle(pool)
        for q in pool:
            picked.append(q)
            if len(picked) >= 65:
                break

    # embaralha a prova final
    random.shuffle(picked)
    return picked[:65]


# ----------------------------
# Rotas
# ----------------------------
@app.get("/")
def home():
    _ensure_session_defaults()

    bank_dir = session.get("bank_dir", BANK_DIR_DEFAULT)
    banks = list_banks(bank_dir)

    current_path = session.get("bank_path", BANK_PATH_DEFAULT)
    current_file = os.path.basename(current_path) if current_path else ""
    if current_file not in banks:
        current_file = banks[0] if banks else ""

    return render_template(
        "home.html",
        banks=banks,
        current_file=current_file,
        current_path=current_path,
        ALL_BANKS_SENTINEL=ALL_BANKS_SENTINEL,
        error=None,
        session_mode=session.get("session_mode", "normal"),
    )


@app.post("/start")
def start():
    _ensure_session_defaults()

    try:
        bank_dir = session.get("bank_dir", BANK_DIR_DEFAULT)

        selected_bank = request.form.get("bank_select", "")
        manual_path = (request.form.get("bank_path_manual") or "").strip()

        weighted_65 = request.form.get("weighted_65") == "on"
        exam_mode = request.form.get("exam_mode") == "on"

        # ✅ Força timer no modo 65 ponderada
        exam_mode = exam_mode or weighted_65

        # flags na sessão (pra selo no template)
        session["weighted65_enabled"] = bool(weighted_65)

        # ----------------------------
        # 1) Seleciona o pool de questões
        # ----------------------------
        if weighted_65:
            # Prova real 65 ponderada: ignora banco individual e usa TODOS os bancos
            all_qs = load_all_banks(bank_dir)
            if not all_qs:
                raise RuntimeError(f"Nenhum banco válido em {bank_dir}")

            questions = _pick_weighted_65(all_qs)
            session["session_mode"] = "weighted65"
            session["bank_path"] = os.path.join(bank_dir, "(ALL)")
            session["bank_select"] = ALL_BANKS_SENTINEL

        else:
            # ---- MODO ESTUDO / NORMAL ----
            # Se digitou caminho manual: usa ele
            if manual_path:
                if not os.path.isfile(manual_path):
                    raise FileNotFoundError(f"Arquivo não encontrado: {manual_path}")
                questions = load_bank(manual_path)
                session["bank_path"] = manual_path
                session["bank_select"] = os.path.basename(manual_path)
                session["session_mode"] = "study"

            else:
                # Se escolheu "TODOS (banks/)" no dropdown: carrega todos os bancos em modo estudo
                if selected_bank == ALL_BANKS_SENTINEL:
                    questions = load_all_banks(bank_dir)
                    if not questions:
                        raise RuntimeError(f"Nenhum banco válido em {bank_dir}")
                    session["bank_path"] = os.path.join(bank_dir, "(ALL)")
                    session["bank_select"] = ALL_BANKS_SENTINEL
                    session["session_mode"] = "allbanks_study"

                else:
                    # Banco único normal
                    bank_path = safe_join_bank_path(bank_dir, selected_bank)
                    if not os.path.isfile(bank_path):
                        raise FileNotFoundError(f"Banco não encontrado: {bank_path}")

                    questions = load_bank(bank_path)
                    session["bank_path"] = bank_path
                    session["bank_select"] = os.path.basename(bank_path)
                    session["session_mode"] = "study"

            # filtros (modo estudo/normal e também "allbanks_study")
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

        if not questions:
            raise RuntimeError("Nenhuma questão selecionada (após filtros/sorteio).")

        # ----------------------------
        # 2) Timer / Modo prova (vale para QUALQUER modo)
        # ----------------------------
        session["exam_mode"] = bool(exam_mode)

        if exam_mode:
            minutes = int(request.form.get("exam_minutes") or 65)
            minutes = max(1, minutes)
            session["exam_duration_sec"] = minutes * 60
            session["exam_started_at"] = _now()
        else:
            session["exam_duration_sec"] = 0
            session["exam_started_at"] = 0

        # ----------------------------
        # 3) Reset sessão e ids
        # ----------------------------
        session["q_ids"] = [q.id for q in questions]
        session["idx"] = 0
        session["score"] = 0
        session["wrong"] = []
        session["answers"] = {}
        session["last_feedback"] = None

        return redirect(url_for("question"))

    except Exception as e:
        bank_dir = session.get("bank_dir", BANK_DIR_DEFAULT)
        banks = list_banks(bank_dir)

        current_path = session.get("bank_path", BANK_PATH_DEFAULT)
        current_file = os.path.basename(current_path) if current_path else ""
        if current_file not in banks:
            current_file = banks[0] if banks else ""

        return render_template(
            "home.html",
            banks=banks,
            current_file=current_file,
            current_path=current_path,
            ALL_BANKS_SENTINEL=ALL_BANKS_SENTINEL,
            error=str(e),
            session_mode=session.get("session_mode", "normal"),
        ), 400


@app.get("/q")
def question():
    _ensure_session_defaults()

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

    # carrega pool conforme modo
    bank_dir = session.get("bank_dir", BANK_DIR_DEFAULT)
    if session.get("bank_select") == ALL_BANKS_SENTINEL or session.get("session_mode") == "weighted65":
        qs = load_all_banks(bank_dir)
    else:
        bank_path = session.get("bank_path", BANK_PATH_DEFAULT)
        qs = load_bank(bank_path)

    q = get_question_by_id(qs, q_ids[idx])

    multi = len(q.correct) > 1
    input_type = "checkbox" if multi else "radio"
    keys = sorted(q.choices.keys())

    return render_template(
        "question.html",
        q=q,
        idx=idx,
        total=len(q_ids),
        keys=keys,
        input_type=input_type,
        timer_enabled=timer_enabled,
        timer_remaining=remaining,
        timer_elapsed=elapsed,
        exam_mode=bool(session.get("exam_mode", False)),
        session_mode=session.get("session_mode", "normal"),
    )


@app.post("/answer")
def answer():
    _ensure_session_defaults()

    q_ids: List[str] = session.get("q_ids", [])
    idx = int(session.get("idx", 0))
    if idx >= len(q_ids):
        return redirect(url_for("result"))

    bank_dir = session.get("bank_dir", BANK_DIR_DEFAULT)
    if session.get("bank_select") == ALL_BANKS_SENTINEL or session.get("session_mode") == "weighted65":
        qs = load_all_banks(bank_dir)
    else:
        bank_path = session.get("bank_path", BANK_PATH_DEFAULT)
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

    fb = session.get("last_feedback")
    if not fb:
        return redirect(url_for("question"))

    bank_dir = session.get("bank_dir", BANK_DIR_DEFAULT)
    if session.get("bank_select") == ALL_BANKS_SENTINEL or session.get("session_mode") == "weighted65":
        qs = load_all_banks(bank_dir)
    else:
        bank_path = session.get("bank_path", BANK_PATH_DEFAULT)
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
        q=q,
        ok=ok,
        selected_str=selected_str,
        correct_str=correct_str,
        selected_set=set(selected_list),
        correct_set=set(correct_list),
        keys=keys,
        session_mode=session.get("session_mode", "normal"),
    )


@app.get("/result")
def result():
    _ensure_session_defaults()

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
        "mode": session.get("session_mode", "normal"),
    }

    return render_template(
        "result.html",
        wrong=wrong,
        stats=stats,
        session_mode=session.get("session_mode", "normal"),
    )


@app.get("/review")
def review():
    _ensure_session_defaults()

    wrong_ids = session.get("wrong", [])
    if not wrong_ids:
        return redirect(url_for("result"))

    bank_dir = session.get("bank_dir", BANK_DIR_DEFAULT)
    if session.get("bank_select") == ALL_BANKS_SENTINEL or session.get("session_mode") == "weighted65":
        qs = load_all_banks(bank_dir)
    else:
        bank_path = session.get("bank_path", BANK_PATH_DEFAULT)
        qs = load_bank(bank_path)

    by_id = {q.id: q for q in qs}
    wrong_questions = [by_id[qid] for qid in wrong_ids if qid in by_id]

    keys = sorted(wrong_questions[0].choices.keys()) if wrong_questions else ["A", "B", "C", "D"]

    return render_template(
        "review.html",
        wrong_questions=wrong_questions,
        keys=keys,
        session_mode=session.get("session_mode", "normal"),
    )


@app.get("/explanations")
def explanations():
    _ensure_session_defaults()

    q_ids: List[str] = session.get("q_ids", [])
    if not q_ids:
        return redirect(url_for("home"))

    bank_dir = session.get("bank_dir", BANK_DIR_DEFAULT)
    if session.get("bank_select") == ALL_BANKS_SENTINEL or session.get("session_mode") == "weighted65":
        qs = load_all_banks(bank_dir)
    else:
        bank_path = session.get("bank_path", BANK_PATH_DEFAULT)
        qs = load_bank(bank_path)

    by_id = {q.id: q for q in qs}
    session_questions = [by_id[qid] for qid in q_ids if qid in by_id]
    keys = sorted(session_questions[0].choices.keys()) if session_questions else ["A", "B", "C", "D"]

    return render_template(
        "explanations.html",
        session_questions=session_questions,
        keys=keys,
        session_mode=session.get("session_mode", "normal"),
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
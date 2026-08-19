import subprocess
import sys

from unslopify import audit_text, apply_safe_fixes, build_brief, profile_from_sample
from unslopify.phrasebank import commit, cross_check

CLEAN = (
    "The parser bug is in the tokenizer, not the grammar. Fixing it means "
    "changing how escape characters are consumed. The fix ships Tuesday.\n"
)

SLOPPY = (
    "In today's fast-paced digital world, this is not just a parser fix. "
    "Experts agree it marks a pivotal moment for the project, ensuring a "
    "seamless experience across the board.\n"
)


def test_clean_text_passes():
    report = audit_text(CLEAN, source="clean")
    assert report.verdict == "pass"
    assert report.findings == []


def test_sloppy_text_fails_with_named_types():
    report = audit_text(SLOPPY, source="sloppy")
    assert report.verdict == "fail"
    ids = {f.type_id for f in report.findings}
    assert "scene-setting" in ids
    assert "inflated-contrast" in ids
    assert "fake-authority" in ids
    assert "significance-inflation" in ids
    assert "tacked-on-benefit" in ids


def test_findings_carry_line_and_span():
    report = audit_text("First line is fine.\nExperts agree this works.\n")
    f = next(f for f in report.findings if f.type_id == "fake-authority")
    assert f.line == 2
    assert f.span.lower() == "experts agree"


def test_dashes_and_curly_quotes_fail():
    report = audit_text("The fix—which shipped—works. “Done.”")
    checks = {m.check for m in report.mechanics}
    assert "dash" in checks
    assert "curly-quotes" in checks
    assert report.verdict == "fail"


def test_long_sentence_feeds_verbosity():
    words = " ".join(["word"] * 40) + "."
    report = audit_text(words + " " + words)
    assert any(m.check == "sentence-length" for m in report.mechanics)
    assert report.verdict == "fail"


def test_repeated_ngram_within_doc_fails():
    text = "the launch plan needs work today. later, the launch plan needs work again."
    report = audit_text(text)
    assert any(m.check == "repeated-ngram" for m in report.mechanics)


def test_code_blocks_are_skipped():
    text = "The change is small.\n```\nexperts agree // not prose\n```\n"
    report = audit_text(text)
    assert report.findings == []


def test_ignore_quoted_spans():
    text = 'The draft says "experts agree" and that phrase has to go.'
    assert audit_text(text).verdict == "fail"
    assert audit_text(text, ignore_quoted=True).verdict == "pass"


def test_soft_types_respect_threshold():
    one = "The team will leverage the new cache."
    assert audit_text(one).verdict == "pass"  # ai-vocab threshold is 2
    two = one + " We also leverage the queue."
    assert audit_text(two).verdict == "fail"


def test_safe_fixes():
    fixed, events = apply_safe_fixes(
        "We did this in order to ship—fast. I hope this helps."
    )
    assert "—" not in fixed
    assert "in order to" not in fixed.lower()
    assert "hope this helps" not in fixed.lower()
    ids = {e.rule_id for e in events}
    assert "dash-to-comma" in ids
    assert "in-order-to" in ids
    assert all(e.line == 1 and e.before != e.after for e in events)


def test_safe_fixes_preserve_quoted_spans():
    text = 'The memo says "in order to comply" and uses in order to twice in order to pad.'
    fixed, events = apply_safe_fixes(text)
    assert '"in order to comply"' in fixed
    assert fixed.count("in order to") == 1  # only the quoted one survives
    assert events


def test_mechanical_rewrite_reports_word_counts():
    from unslopify import mechanical_rewrite, Draft

    rw = mechanical_rewrite(Draft(text="We met in order to decide—quickly."))
    assert rw.words_before > rw.words_after or rw.words_before == rw.words_after
    assert rw.events
    assert rw.policy.preserve_quotes


def test_brief_names_each_finding():
    brief = build_brief(audit_text(SLOPPY))
    assert "Fake authority" in brief
    assert "direction:" in brief


def test_voice_profile():
    prof = profile_from_sample(
        "I shipped it. I'm not sure it's right. We'll see what breaks. "
        "Short and plain works for me."
    )
    assert prof.avg_sentence_words > 0
    assert prof.contraction_rate > 0


def test_phrase_bank_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("UNSLOPIFY_HOME", str(tmp_path))
    doc = "the quarterly report covers revenue by region and headcount by team"
    commit(doc, "doc-1")
    assert cross_check(doc, doc_id="doc-1") == []  # self is skipped
    assert cross_check(doc, doc_id="doc-2")  # another doc reusing it fails
    assert cross_check("completely different words in every position here", "doc-3") == []


def test_cli_exit_codes(tmp_path, monkeypatch):
    monkeypatch.setenv("UNSLOPIFY_HOME", str(tmp_path))
    clean = tmp_path / "clean.md"
    clean.write_text(CLEAN)
    sloppy = tmp_path / "sloppy.md"
    sloppy.write_text(SLOPPY)
    env_run = lambda *args: subprocess.run(
        [sys.executable, "-m", "unslopify.cli", *args],
        capture_output=True,
        text=True,
    )
    assert env_run(str(clean)).returncode == 0
    r = env_run(str(sloppy))
    assert r.returncode == 1
    assert "fake-authority" in r.stdout
    assert env_run(str(sloppy), "--json").returncode == 1
    assert env_run("types").returncode == 0


def test_matches_across_hard_wraps():
    text = "The new tooling consolidates metrics,\nensuring better outcomes for everyone.\n"
    report = audit_text(text)
    assert any(f.type_id == "tacked-on-benefit" for f in report.findings)


def test_wrap_pass_does_not_double_count():
    text = "We leverage the cache, ensuring speed.\n"
    report = audit_text(text)
    assert sum(1 for f in report.findings if f.type_id == "tacked-on-benefit") == 1


def test_long_sentence_across_hard_wraps():
    words = ["word"] * 45
    wrapped = " ".join(words[:15]) + "\n" + " ".join(words[15:30]) + "\n" + " ".join(words[30:]) + "."
    report = audit_text(wrapped)
    assert any(m.check == "sentence-length" for m in report.mechanics)


def test_cli_multiple_files_and_aggregate_exit(tmp_path, monkeypatch):
    monkeypatch.setenv("UNSLOPIFY_HOME", str(tmp_path))
    a = tmp_path / "a.md"
    a.write_text(CLEAN)
    b = tmp_path / "b.md"
    b.write_text(SLOPPY)
    run = lambda *args: subprocess.run(
        [sys.executable, "-m", "unslopify.cli", *args],
        capture_output=True,
        text=True,
    )
    r = run(str(a), str(b))
    assert r.returncode == 1
    assert "a.md" in r.stdout and "b.md" in r.stdout  # nothing silently skipped
    assert "2 files checked: fail" in r.stdout
    assert run(str(a), str(a)).returncode == 0


def test_cli_directory_recursion(tmp_path, monkeypatch):
    monkeypatch.setenv("UNSLOPIFY_HOME", str(tmp_path))
    sub = tmp_path / "docs" / "inner"
    sub.mkdir(parents=True)
    (sub / "x.md").write_text(SLOPPY)
    (tmp_path / "docs" / "skip.py").write_text("experts agree = 1\n")
    r = subprocess.run(
        [sys.executable, "-m", "unslopify.cli", str(tmp_path / "docs")],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 1
    assert "x.md" in r.stdout
    assert "skip.py" not in r.stdout  # non-text files stay out


def test_cli_piped_stdin_without_dash(tmp_path, monkeypatch):
    monkeypatch.setenv("UNSLOPIFY_HOME", str(tmp_path))
    r = subprocess.run(
        [sys.executable, "-m", "unslopify.cli"],
        input="Experts agree this works.\n",
        capture_output=True,
        text=True,
    )
    assert r.returncode == 1
    assert "fake-authority" in r.stdout


def test_cli_fix_write_in_place(tmp_path, monkeypatch):
    monkeypatch.setenv("UNSLOPIFY_HOME", str(tmp_path))
    f = tmp_path / "f.md"
    f.write_text("We met in order to decide.\n")
    r = subprocess.run(
        [sys.executable, "-m", "unslopify.cli", str(f), "--fix", "-w"],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0
    assert "in order to" not in f.read_text()
    assert "fixed" in r.stderr


def test_urls_and_link_targets_are_not_prose():
    text = (
        "[![test](https://github.com/u/r/actions/workflows/test.yml/badge.svg)](https://github.com/u/r/actions)\n"
        "[![pypi](https://img.shields.io/pypi/v/x)](https://pypi.org/project/x/)\n"
        "See https://example.com/experts-agree for details.\n"
    )
    report = audit_text(text)
    assert report.verdict == "pass"
    assert not any(m.check == "repeated-ngram" for m in report.mechanics)

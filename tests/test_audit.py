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


def test_terse_prose_is_not_a_slogan():
    assert audit_text("Use Postgres. The team knows it. Migration is easy.").verdict == "pass"
    assert audit_text("it works. tests pass. ship it.").verdict == "pass"


def test_slogan_fragment_still_catches_taglines():
    text = "One Team. One Vision. Zero Excuses.\n\nOne Pipeline. Zero Friction. Pure Speed.\n"
    report = audit_text(text)
    assert sum(1 for f in report.findings if f.type_id == "slogan-fragment") >= 2
    assert report.verdict == "fail"


def test_serves_as_maps_to_exactly_one_type():
    report = audit_text("The library serves as the core dependency.")
    ids = [f.type_id for f in report.findings]
    assert ids == ["copula-avoidance"]
    assert report.verdict == "pass"  # soft, one hit, threshold 2


def test_soft_thresholds_scale_with_length():
    filler = ("The report covers region five. " * 40 + "\n\n") * 18  # ~4300 words, but repetitive
    doc = filler.replace("region five", "each region once")  # avoid ngram noise
    # two "leverage" in a ~4000-word doc is under the scaled threshold
    long_doc = ("word " * 200 + ". ") * 20 + " We leverage caching. We leverage queues."
    report = audit_text(long_doc, disable={"repeated-ngram", "sentence-length"})
    assert not any("AI vocabulary" in r for r in report.fail_reasons)


def test_hedge_stack_is_soft_now():
    assert audit_text("It could possibly rain.").verdict == "pass"
    assert audit_text("It could possibly rain. We might perhaps stay.").verdict == "fail"


def test_bullets_are_not_one_long_sentence():
    bullets = "\n".join(f"- item number {i} does a thing" for i in range(8))
    report = audit_text(bullets, disable={"repeated-ngram"})
    assert not any(m.check == "sentence-length" for m in report.mechanics)


def test_frontmatter_and_tables_are_skipped():
    text = "---\ntitle: experts agree\n---\n\n| col | experts agree |\n| --- | --- |\n\nPlain body.\n"
    assert audit_text(text).findings == []


def test_pragma_disable_file():
    text = "<!-- unslopify:disable -->\nExperts agree this works.\n"
    assert audit_text(text).verdict == "pass"


def test_pragma_disable_types_and_line():
    by_type = "<!-- unslopify:disable=fake-authority -->\nExperts agree this works.\n"
    assert audit_text(by_type).verdict == "pass"
    by_line = "Experts agree this works. <!-- unslopify:disable-line -->\nExperts agree again.\n"
    report = audit_text(by_line)
    assert all(f.line != 1 for f in report.findings)
    assert any(f.line == 2 for f in report.findings)


def test_pragma_in_code_fence_is_documentation():
    text = "Use this pragma:\n\n```\n<!-- unslopify:disable -->\n```\n\nExperts agree this works.\n"
    assert audit_text(text).verdict == "fail"


def test_ngram_allowance_scales():
    from unslopify.audit import _ngram_allowance

    assert _ngram_allowance(300) == 1
    assert _ngram_allowance(6000) == 5


def test_bank_ignores_shared_quotations(tmp_path, monkeypatch):
    monkeypatch.setenv("UNSLOPIFY_HOME", str(tmp_path))
    quote = '"the seating chart has two owners and the venue task has no date"'
    commit(f"first doc cites {quote} as evidence for one claim here", "d1")
    assert cross_check(f"second doc also cites {quote} in its own words", "d2") == []


def test_voice_possessives_are_not_contractions():
    prof = profile_from_sample(
        "The team's plan met the board's goal. The quarter's numbers held. "
        "The vendor's contract and the client's budget aligned well."
    )
    assert prof.contraction_rate == 0


def test_cli_types_shadowing(tmp_path, monkeypatch):
    monkeypatch.setenv("UNSLOPIFY_HOME", str(tmp_path))
    (tmp_path / "types").write_text(SLOPPY)
    r = subprocess.run(
        [sys.executable, "-m", "unslopify.cli", "types"],
        capture_output=True, text=True, cwd=tmp_path,
    )
    assert r.returncode == 1  # audits the file, does not print the rubric
    assert "fake-authority" in r.stdout


def test_cli_non_utf8_is_exit_2(tmp_path, monkeypatch):
    monkeypatch.setenv("UNSLOPIFY_HOME", str(tmp_path))
    bad = tmp_path / "bad.md"
    bad.write_bytes(b"\xff\xfe not utf8 \x9c")
    r = subprocess.run(
        [sys.executable, "-m", "unslopify.cli", str(bad)],
        capture_output=True, text=True,
    )
    assert r.returncode == 2
    assert "not valid UTF-8" in r.stderr


def test_cli_multi_file_json_is_an_array(tmp_path, monkeypatch):
    import json as jsonlib

    monkeypatch.setenv("UNSLOPIFY_HOME", str(tmp_path))
    a = tmp_path / "a.md"
    a.write_text(CLEAN)
    b = tmp_path / "b.md"
    b.write_text(SLOPPY)
    r = subprocess.run(
        [sys.executable, "-m", "unslopify.cli", str(a), str(b), "--json"],
        capture_output=True, text=True,
    )
    data = jsonlib.loads(r.stdout)
    assert isinstance(data, list) and len(data) == 2


def test_cli_config_disable_and_exclude(tmp_path, monkeypatch):
    monkeypatch.setenv("UNSLOPIFY_HOME", str(tmp_path))
    (tmp_path / "pyproject.toml").write_text(
        '[tool.unslopify]\ndisable = ["fake-authority"]\nexclude = ["skip-*.md"]\n'
    )
    doc = tmp_path / "doc.md"
    doc.write_text("Experts agree this works.\n")
    skipped = tmp_path / "skip-me.md"
    skipped.write_text(SLOPPY)
    r = subprocess.run(
        [sys.executable, "-m", "unslopify.cli", "doc.md", "skip-me.md"],
        capture_output=True, text=True, cwd=tmp_path,
    )
    assert r.returncode == 0
    assert "skip-me" not in r.stdout

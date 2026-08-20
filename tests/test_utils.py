"""Test cho utils: filename, hashing, robots."""

from __future__ import annotations

import os

from utils.filename import sanitize_filename, unique_path
from utils.hashing import sha256_bytes, sha256_file, sha256_text
from utils.robots import RobotsPolicy

ROBOTS_SAMPLE = """
User-agent: Yandex
Disallow: /

User-agent: *
Disallow: /*/search*
Disallow: /*/code/viewcode/*
Disallow: /*/code/download/*/
Disallow: /*/users/*/publications
Allow: /en/users/*/publications
Crawl-delay: 1
"""


def test_sanitize_filename_replaces_invalid_chars():
    assert sanitize_filename("Gold Scalping EA: XAU/USD.mq5") == "Gold_Scalping_EA_XAU_USD.mq5"
    assert sanitize_filename("   ") == "source"
    assert sanitize_filename("a" * 200 + ".mq5").endswith(".mq5")


def test_unique_path_adds_counter(tmp_path):
    first = unique_path(str(tmp_path), "EA.mq5")
    open(first, "w").close()
    second = unique_path(str(tmp_path), "EA.mq5")
    assert os.path.basename(second) == "EA_001.mq5"
    open(second, "w").close()
    assert os.path.basename(unique_path(str(tmp_path), "EA.mq5")) == "EA_002.mq5"


def test_hashing(tmp_path):
    assert sha256_bytes(b"abc") == sha256_text("abc")
    path = tmp_path / "f.mq5"
    path.write_bytes(b"abc")
    assert sha256_file(str(path)) == sha256_bytes(b"abc")


def test_robots_policy_wildcards():
    policy = RobotsPolicy(ROBOTS_SAMPLE)
    assert policy.can_fetch("https://www.mql5.com/en/code/mt5/experts")
    assert policy.can_fetch("https://www.mql5.com/en/code/12345")
    assert policy.can_fetch("https://www.mql5.com/en/code/download/12345.zip")
    assert not policy.can_fetch("https://www.mql5.com/en/code/download/12345/EA.mq5")
    assert not policy.can_fetch("https://www.mql5.com/en/code/viewcode/12345/1/EA.mq5")
    assert not policy.can_fetch("https://www.mql5.com/en/search?keyword=gold")
    # Allow cu the hon thang Disallow
    assert policy.can_fetch("https://www.mql5.com/en/users/tester/publications")
    assert not policy.can_fetch("https://www.mql5.com/ru/users/tester/publications")
    assert policy.crawl_delay == 1


def test_robots_policy_empty_allows_all():
    policy = RobotsPolicy()
    assert policy.can_fetch("https://www.mql5.com/en/anything")

"""Core data types shared across the pipeline."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum


class Category(str, Enum):
    PRODUCT_BUG = "PRODUCT_BUG"   # the application under test is wrong
    TEST_BUG = "TEST_BUG"         # the test code / locator / expected value is wrong
    ENVIRONMENT = "ENVIRONMENT"   # infra, downstream service, test data, config
    FLAKY = "FLAKY"               # non-deterministic; passes on rerun with no change

    @classmethod
    def values(cls) -> list[str]:
        return [c.value for c in cls]


@dataclass
class Failure:
    """One failed test case, normalised from JUnit / TestNG XML."""
    test_id: str                      # e.g. com.bank.payments.TransferTest.testSameDayTransfer
    message: str = ""
    exception_type: str = ""
    stacktrace: str = ""
    log_excerpt: str = ""             # system-out / system-err tail
    duration_s: float = 0.0
    suite: str = ""
    history: str = ""                 # last N results, oldest->newest, e.g. "PPPFPPFPPF"
    source_file: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Verdict:
    """Classification for one cluster of failures."""
    category: str
    confidence: float                 # 0..1, self-reported by the model or rule
    reason: str
    suggested_owner: str = ""         # e.g. "dev:payments", "qa:automation", "platform/devops"
    evidence: list[str] = field(default_factory=list)
    needs_human_review: bool = False
    jira_summary: str = ""
    jira_description: str = ""
    engine: str = ""                  # "claude:<model>" or "rules"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Cluster:
    """Failures that share the same normalised failure signature."""
    cluster_id: str
    signature: str
    failures: list[Failure]
    verdict: Verdict | None = None

    @property
    def representative(self) -> Failure:
        return self.failures[0]

    @property
    def test_ids(self) -> list[str]:
        return [f.test_id for f in self.failures]

"""db/optimizer/rules.py

Catalog of offline SQL optimization rules and anti-pattern detectors.
Evaluates queries without external network dependencies.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class OptimizationFinding:
    severity: str  # "HIGH", "MEDIUM", "INFO"
    category: str  # "INDEX", "PREDICATE", "PROJECTION", "JOIN", "SAFETY", "STRUCTURE"
    rule_id: str
    title: str
    description: str
    suggestion: str
    line_no: Optional[int] = None


# Rule Identifiers
RULE_SELECT_STAR = "OPT-001"
RULE_LEADING_WILDCARD = "OPT-002"
RULE_NONSARGABLE_FUNCTION = "OPT-003"
RULE_IN_SUBQUERY = "OPT-004"
RULE_NOT_IN_SUBQUERY = "OPT-005"
RULE_COMMA_JOIN = "OPT-006"
RULE_REDUNDANT_DISTINCT = "OPT-007"
RULE_COUNT_EXISTENCE = "OPT-008"
RULE_UNCONSTRAINED_MUTATION = "OPT-009"
RULE_OR_ACROSS_COLUMNS = "OPT-010"
RULE_PAGINATION_WITHOUT_ORDER = "OPT-011"
RULE_LIMIT_WITHOUT_ORDER = RULE_PAGINATION_WITHOUT_ORDER
RULE_HAVING_WITHOUT_AGGREGATE = "OPT-012"

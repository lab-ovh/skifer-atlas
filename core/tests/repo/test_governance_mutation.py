"""Contrats précis des règles et de la sérialisation de gouvernance."""

import pytest

from skifer_atlas.governance.codeowners import OwnedDocument, _body, generate, has_drifted
from skifer_atlas.governance.model import (
    Domain,
    Governance,
    Member,
    MemberRole,
    ValidatorsRequired,
    _duplicates,
    account_from_name,
    check_governance,
    domain_approvers,
    domain_referents,
    dump_governance,
    member_domains,
    parse_governance,
    rename_account,
    role_of,
    validate_governance,
)
from skifer_atlas.governance.rules import (
    CANONICAL_MENTION,
    NO_REVIEW_MENTION,
    Decision,
    Requirement,
    Review,
    decide,
    requirement,
)
from skifer_atlas.model.errors import Issue


def member(account, role=None, domains=None):
    return Member(account=account, name=account, roles=[MemberRole(role=role, domains=domains or [])]
                  if role else [])


def test_decision_serialization():
    decision = Decision(1, 2, ["alice"], ["bob"], False, "reviewed", "mention", "explication")
    assert decision.to_dict() == {
        "approvals": {"obtained": 1, "required": 2}, "approvers": ["alice"],
        "changes_requested_by": ["bob"], "ready_to_merge": False, "merge_mode": "reviewed",
        "mention": "mention", "explanation": "explication",
    }


def test_access_points_requires_space_referent():
    gov = Governance(members=[member("alice", "referent"), member("bob", "referent", ["ventes"])])
    assert requirement(gov, "access_points", "ventes") == Requirement(1, frozenset({"alice"}))


@pytest.mark.parametrize("nature", ["undeclared", "from_scratch"])
def test_comment_does_not_replace_approval_and_mention_survives(nature):
    gov = Governance(members=[member("alice", "referent"), member("bob", "validateur")])
    reviews = [Review("bob", "approved", "head"), Review("bob", "commented", "head")]
    assert decide(gov, nature, None, "alice", reviews, "head") == Decision(
        1, 1, ["bob"], ready_to_merge=True, mention=CANONICAL_MENTION)


def test_decision_explanations_and_boundary():
    alone = Governance(members=[member("alice", "referent")])
    assert decide(alone, "governance", None, "alice", [], "h") == Decision(
        0, 1, ready_to_merge=True, merge_mode="no_other_eligible", mention=NO_REVIEW_MENTION,
        explanation="Aucun autre compte n'est habilité à approuver.")
    assert decide(Governance(), "new_version", None, "alice", [], "h") == Decision(
        0, 1, explanation="Aucun compte n'est habilité à approuver dans ce domaine.")
    gov = Governance(validators_required=ValidatorsRequired(canonical=2),
                     members=[member("alice", "referent"), member("a", "validateur"),
                              member("b", "validateur")])
    reviews = [Review("b", "changes_requested", "h"), Review("a", "changes_requested", "h")]
    assert decide(gov, "new_version", None, "alice", reviews, "h") == Decision(
        0, 2, changes_requested_by=["a", "b"], explanation="Changements demandés par a, b.")
    assert decide(gov, "new_version", None, "alice", [], "h") == Decision(
        0, 2, explanation="0 validation(s) sur 2.")


def test_effective_roles_and_domains():
    gov = Governance(domains=[Domain(id="ventes", label="Ventes", referents=["listed"],
                                     validators=["validator"]),
                              Domain(id="finance", label="Finance", validators=["reader"])],
                     members=[member("listed"), member("validator"), member("reader", "lecteur"),
                              member("scoped", "referent", ["ventes"]),
                              member("scopedval", "validateur", ["ventes"]),
                              member("global", "validateur"), member("empty")])
    assert domain_approvers(gov, "ventes") == {"listed", "validator", "scoped", "scopedval", "global"}
    assert domain_approvers(gov, None) == {"global"}
    assert domain_referents(gov, "ventes") == {"listed", "scoped"}
    assert domain_referents(gov, "absent") == set()
    assert member_domains(gov, "reader") == {"finance"}
    assert member_domains(gov, "scoped") == {"ventes"}
    assert member_domains(gov, "global") == {"ventes", "finance"}
    assert role_of(gov, "empty") == "lecteur"


def test_rename_only_old_account_in_domain_lists():
    gov = Governance(members=[member("old"), member("other")],
                     domains=[Domain(id="ventes", label="Ventes", referents=["old", "other"],
                                     validators=["other", "old"])])
    renamed = rename_account(gov, "old", "new")
    assert renamed.domains[0].referents == ["new", "other"]
    assert renamed.domains[0].validators == ["other", "new"]
    assert [m.account for m in renamed.members] == ["new", "other"]


def test_account_names_and_duplicates():
    assert account_from_name("Xavier X") == "xavier-x"
    assert account_from_name("x") == "x"
    assert account_from_name("a" * 39) == "a" * 39
    assert account_from_name("a" * 40) == "a" * 39
    assert account_from_name("...") == "referent"
    assert _duplicates(["a", "b", "a", "a", "b"]) == ["a", "b"]


def test_governance_issues_are_precise():
    gov = Governance(domains=[Domain(id="aa", label="Alpha", validators=["missing"]),
                              Domain(id="aa", label="Beta")],
                     members=[member("bob", "validateur", ["unknown"]), member("bob")])
    assert check_governance(gov) == [
        Issue("/domains", None, "duplicate_domain", "Domaine « aa » répété."),
        Issue("/members", None, "duplicate_member", "Membre « bob » répété."),
        Issue("/domains/0/validators", None, "unknown_member",
              "« missing » n'est pas membre de l'espace."),
        Issue("/members/0/roles/0/domains", None, "unknown_domain", "Domaine « unknown » inconnu."),
        Issue("/members", None, "no_referent", "L'espace doit avoir au moins un référent "
              "(rôle referent sans restriction de domaine)."),
        Issue("/domains/0", None, "domain_without_referent",
              "Le domaine « Alpha » n'a pas de référent.", "warning"),
        Issue("/domains/1", None, "domain_without_referent",
              "Le domaine « Beta » n'a pas de référent.", "warning"),
    ]


def test_validation_and_parsing_issues():
    assert validate_governance([]) == (None, [Issue(
        "", None, "invalid_value", "governance.yaml doit être un mapping.")])
    assert validate_governance({"schema_version": 2}) == (None, [Issue(
        "/schema_version", None, "invalid_value",
        "Valeur « 2 » non admise pour « schema_version ». Valeurs admises : 1. "
        "Mettre la valeur entre guillemets.")])
    model, issues = parse_governance("[")
    assert model is None
    assert [(i.path, i.node_id, i.code) for i in issues] == [("", None, "invalid_yaml")]
    assert issues[0].message.startswith("YAML illisible : while parsing a flow node")
    assert parse_governance("") == validate_governance({})


def test_dump_governance_exact_yaml():
    gov = Governance(members=[Member(account="alice", name="Élodie " + "mot " * 23 + "fin",
                                     roles=[MemberRole(role="referent")])])
    assert dump_governance(gov) == (
        "schema_version: 1\nvalidators_required:\n  canonical: 1\n  variants: 1\n"
        "domains: []\nmembers:\n- account: alice\n"
        "  name: Élodie mot mot mot mot mot mot mot mot mot mot mot mot mot mot mot mot mot mot "
        "mot mot mot mot\n    mot fin\n  roles:\n  - role: referent\n    domains: []\n"
        "allowed_platforms: []\n")


def test_codeowners_defaults_and_nested_document():
    gov = Governance(domains=[Domain(id="aa", label="A", validators=["domain"])],
                     members=[member("space", "validateur")])
    assert _body(gov, [OwnedDocument("kpis/deep/revenu.yaml", "kpi", "aa")]) == (
        "/concepts/ @domain @space\n/kpis/ @domain @space\n/variants/ @domain @space\n"
        "/kpis/deep/revenu.yaml @domain @space\n/variants/revenu/ @domain @space\n")
    assert _body(gov, [OwnedDocument("revenu.yaml", "kpi", "aa")]).endswith(
        "/revenu.yaml @domain @space\n/variants/revenu/ @domain @space\n")


def test_codeowners_drift_detects_leading_whitespace():
    gov = Governance(members=[member("space", "referent")])
    generated = generate(gov, [])
    assert not has_drifted(generated)
    assert has_drifted(generated.replace("\n\n/concepts/", "\n\n /concepts/"))
    assert has_drifted(generated.replace("\n\n/concepts/", "\n\nX/concepts/"))


def test_dump_wraps_at_width_100():
    gov = Governance(members=[Member(account="a", name="é" * 89 + " fin suite")])
    assert dump_governance(gov) == (
        "schema_version: 1\nvalidators_required:\n  canonical: 1\n  variants: 1\n"
        "domains: []\nmembers:\n- account: a\n  name: " + "é" * 89 +
        " fin\n    suite\n  roles: []\nallowed_platforms: []\n")

"""Charter DSL recursive descent parser.

Consumes a token stream (with INDENT/DEDENT) and produces an AST.

Grammar summary:
    charter    ::= header schemas? packages? policies? workflow+ situations? roles?
    header     ::= CHARTER STRING VERSION
    schemas    ::= SCHEMAS COLON catalog_ref NEWLINE
                 | SCHEMAS COLON NEWLINE INDENT ("-" catalog_ref NEWLINE)+ DEDENT
    packages   ::= PACKAGES COLON NEWLINE INDENT ("-" IDENT NEWLINE)+ DEDENT
    policies   ::= POLICIES COLON NEWLINE INDENT ("-" policy_id NEWLINE)+ DEDENT
    workflow   ::= WORKFLOW IDENT COLON NEWLINE INDENT phase+ DEDENT
    phase      ::= PHASE IDENT COLON NEWLINE INDENT phase_stmt+ DEDENT
    ...

Usage:
    from canon.dsl.parser import Parser
    from canon.dsl.lexer import Lexer

    tokens = Lexer(source).tokenize()
    ast = Parser(tokens).parse()
"""

from __future__ import annotations

from .ast import (
    ActionNode,
    ArgNode,
    AwaitNode,
    AwaitRefNode,
    BuiltinRefNode,
    CertifyNode,
    CharterNode,
    EvidenceNode,
    FeatureCallNode,
    GrantNode,
    OutputNode,
    PackageRefNode,
    PhaseNode,
    PhaseRefNode,
    PolicyNode,
    PredicateNode,
    RequireNode,
    RoleNode,
    SchemaRefNode,
    SituationNode,
    TriggerNode,
    WaitingPeriodNode,
    WhenBlockNode,
    WorkflowNode,
)
from .errors import ParseError
from .tokens import KEYWORDS, Token, TokenType

__all__ = ("Parser", "parse_charter")

# Comparator token types
_COMPARATORS = frozenset(
    {
        TokenType.EQ,
        TokenType.NEQ,
        TokenType.GT,
        TokenType.GTE,
        TokenType.LT,
        TokenType.LTE,
    }
)


class Parser:
    """Recursive descent parser for Charter DSL."""

    def __init__(self, tokens: list[Token]) -> None:
        self.tokens = tokens
        self.pos = 0

    # -----------------------------------------------------------------
    # Navigation
    # -----------------------------------------------------------------

    def current_token(self) -> Token:
        if self.pos >= len(self.tokens):
            return self.tokens[-1]  # EOF
        return self.tokens[self.pos]

    def peek_token(self, offset: int = 1) -> Token:
        peek_pos = self.pos + offset
        if peek_pos >= len(self.tokens):
            return self.tokens[-1]
        return self.tokens[peek_pos]

    def advance(self) -> Token:
        """Consume and return current token."""
        token = self.current_token()
        if self.pos < len(self.tokens) - 1:
            self.pos += 1
        return token

    def expect(self, token_type: TokenType) -> Token:
        """Consume token of expected type or raise ParseError."""
        token = self.current_token()
        if token.type != token_type:
            raise ParseError(
                f"Expected {token_type.name}, got {token.type.name} ({token.value!r})",
                token,
            )
        return self.advance()

    def match(self, *token_types: TokenType) -> bool:
        """Check if current token matches any of the given types."""
        return self.current_token().type in token_types

    def skip_newlines(self) -> None:
        """Skip NEWLINE tokens."""
        while self.match(TokenType.NEWLINE):
            self.advance()

    def skip_docstrings(self) -> None:
        """Skip DOCSTRING tokens (triple-quoted documentation)."""
        while self.match(TokenType.DOCSTRING):
            self.advance()
            self.skip_newlines()

    def _error(self, message: str) -> ParseError:
        return ParseError(message, self.current_token())

    # -----------------------------------------------------------------
    # Top-level
    # -----------------------------------------------------------------

    def parse(self) -> CharterNode:
        """Parse a complete charter document."""
        self.skip_newlines()

        # Header: charter "Name" vX.Y
        name, version = self._parse_header()
        self.skip_newlines()

        # Optional sections (track seen to detect duplicates)
        schemas: list[SchemaRefNode] = []
        packages: list[PackageRefNode] = []
        policies: list[PolicyNode] = []
        triggers: list[TriggerNode] = []
        workflows: list[WorkflowNode] = []
        situations: list[SituationNode] = []
        roles: list[RoleNode] = []
        seen_sections: set[str] = set()

        while not self.match(TokenType.EOF):
            self.skip_newlines()
            if self.match(TokenType.EOF):
                break

            if self.match(TokenType.SCHEMAS):
                if "schemas" in seen_sections:
                    raise self._error("Duplicate 'schemas' section")
                seen_sections.add("schemas")
                schemas = self._parse_schemas()
            elif self.match(TokenType.PACKAGES):
                if "packages" in seen_sections:
                    raise self._error("Duplicate 'packages' section")
                seen_sections.add("packages")
                packages = self._parse_packages()
            elif self.match(TokenType.POLICIES):
                if "policies" in seen_sections:
                    raise self._error("Duplicate 'policies' section")
                seen_sections.add("policies")
                policies = self._parse_policies()
            elif self.match(TokenType.TRIGGERS):
                if "triggers" in seen_sections:
                    raise self._error("Duplicate 'triggers' section")
                seen_sections.add("triggers")
                triggers = self._parse_triggers()
            elif self.match(TokenType.WORKFLOW):
                workflows.append(self._parse_workflow())
            elif self.match(TokenType.SITUATIONS):
                if "situations" in seen_sections:
                    raise self._error("Duplicate 'situations' section")
                seen_sections.add("situations")
                situations = self._parse_situations()
            elif self.match(TokenType.ROLES):
                if "roles" in seen_sections:
                    raise self._error("Duplicate 'roles' section")
                seen_sections.add("roles")
                roles = self._parse_roles()
            else:
                raise self._error(
                    f"Expected section keyword (schemas, packages, policies, "
                    f"triggers, workflow, situations, roles), "
                    f"got {self.current_token().type.name}"
                )

            self.skip_newlines()

        return CharterNode(
            name=name,
            version=version,
            schemas=tuple(schemas),
            packages=tuple(packages),
            policies=tuple(policies),
            triggers=tuple(triggers),
            workflows=tuple(workflows),
            situations=tuple(situations),
            roles=tuple(roles),
        )

    # -----------------------------------------------------------------
    # Header
    # -----------------------------------------------------------------

    def _parse_header(self) -> tuple[str, str]:
        """Parse: charter "Name" vX.Y

        Version may tokenize as IDENT("v1") DOT INT("0") for "v1.0",
        or as a single IDENT if it contains no dot.
        """
        self.expect(TokenType.CHARTER)
        name_token = self.expect(TokenType.STRING)

        # Version: starts as IDENT, may have .INT suffix
        version_start = self.expect(TokenType.IDENT).value
        if self.match(TokenType.DOT):
            self.advance()
            minor = self.expect(TokenType.INT).value
            return name_token.value, f"{version_start}.{minor}"
        return name_token.value, version_start

    # -----------------------------------------------------------------
    # Schemas
    # -----------------------------------------------------------------

    def _parse_schemas(self) -> list[SchemaRefNode]:
        """Parse schemas section (inline or block).

        Inline:  schemas: namespace@version
        Block:   schemas:
                     - namespace@version
                     - namespace@version
        """
        self.expect(TokenType.SCHEMAS)
        self.expect(TokenType.COLON)

        # Disambiguate: NEWLINE → block list, otherwise inline single
        if self.match(TokenType.NEWLINE):
            self.skip_newlines()
            self.expect(TokenType.INDENT)

            schemas: list[SchemaRefNode] = []
            while not self.match(TokenType.DEDENT, TokenType.EOF):
                self.skip_newlines()
                if self.match(TokenType.DEDENT, TokenType.EOF):
                    break
                self.expect(TokenType.DASH)
                schemas.append(self._parse_schema_ref())
                self.skip_newlines()

            if self.match(TokenType.DEDENT):
                self.advance()

            return schemas

        # Inline single schema
        ref = self._parse_schema_ref()
        self.skip_newlines()
        return [ref]

    def _parse_schema_ref(self) -> SchemaRefNode:
        """Parse: namespace(.sub)*@version"""
        namespace = self._parse_dotted_name()
        self.expect(TokenType.AT)
        version = self._read_version_string()
        return SchemaRefNode(namespace=namespace, version=version)

    # -----------------------------------------------------------------
    # Packages
    # -----------------------------------------------------------------

    def _parse_packages(self) -> list[PackageRefNode]:
        """Parse: packages: INDENT (- name NEWLINE)+ DEDENT

        Package names may collide with DSL keywords (e.g., evidence,
        workflow, charter), so we accept any identifier-like token.
        """
        self.expect(TokenType.PACKAGES)
        self.expect(TokenType.COLON)
        self.skip_newlines()
        self.expect(TokenType.INDENT)

        packages: list[PackageRefNode] = []
        while not self.match(TokenType.DEDENT, TokenType.EOF):
            self.skip_newlines()
            if self.match(TokenType.DEDENT, TokenType.EOF):
                break
            self.expect(TokenType.DASH)
            name = self._parse_package_name()
            packages.append(PackageRefNode(name=name))
            self.skip_newlines()

        if self.match(TokenType.DEDENT):
            self.advance()

        return packages

    def _parse_package_name(self) -> str:
        """Parse a package name (IDENT or keyword used as name)."""
        token = self.current_token()
        # Accept IDENT or any keyword token as a package name
        if self.match(TokenType.IDENT) or token.value in KEYWORDS:
            return self.advance().value
        raise self._error(f"Expected package name, got {token.type.name}")

    # -----------------------------------------------------------------
    # Policies
    # -----------------------------------------------------------------

    def _parse_policies(self) -> list[PolicyNode]:
        """Parse: policies: INDENT (- policy.id NEWLINE)+ DEDENT"""
        self.expect(TokenType.POLICIES)
        self.expect(TokenType.COLON)
        self.skip_newlines()
        self.expect(TokenType.INDENT)

        policies: list[PolicyNode] = []
        while not self.match(TokenType.DEDENT, TokenType.EOF):
            self.skip_newlines()
            if self.match(TokenType.DEDENT, TokenType.EOF):
                break
            self.expect(TokenType.DASH)
            policy_id = self._parse_dotted_name()
            policies.append(PolicyNode(policy_id=policy_id))
            self.skip_newlines()

        if self.match(TokenType.DEDENT):
            self.advance()

        return policies

    # -----------------------------------------------------------------
    # Triggers
    # -----------------------------------------------------------------

    def _parse_triggers(self) -> list[TriggerNode]:
        """Parse: triggers: INDENT (trigger_name NEWLINE)+ DEDENT

        Triggers are external events that can activate phases via `require await`.
        """
        self.expect(TokenType.TRIGGERS)
        self.expect(TokenType.COLON)
        self.skip_newlines()
        self.expect(TokenType.INDENT)

        triggers: list[TriggerNode] = []
        while not self.match(TokenType.DEDENT, TokenType.EOF):
            self.skip_newlines()
            if self.match(TokenType.DEDENT, TokenType.EOF):
                break
            name = self.expect(TokenType.IDENT).value
            triggers.append(TriggerNode(name=name))
            self.skip_newlines()

        if self.match(TokenType.DEDENT):
            self.advance()

        return triggers

    # -----------------------------------------------------------------
    # Workflow
    # -----------------------------------------------------------------

    def _parse_workflow(self) -> WorkflowNode:
        """Parse: workflow name: INDENT [docstring] phase+ DEDENT"""
        self.expect(TokenType.WORKFLOW)
        name = self.expect(TokenType.IDENT).value
        self.expect(TokenType.COLON)
        self.skip_newlines()
        self.expect(TokenType.INDENT)

        # Skip optional docstring at start of workflow
        self.skip_newlines()
        self.skip_docstrings()

        phases: list[PhaseNode] = []
        while not self.match(TokenType.DEDENT, TokenType.EOF):
            self.skip_newlines()
            self.skip_docstrings()
            if self.match(TokenType.DEDENT, TokenType.EOF):
                break
            phases.append(self._parse_phase())
            self.skip_newlines()

        if self.match(TokenType.DEDENT):
            self.advance()

        if not phases:
            raise self._error(f"Workflow '{name}' must contain at least one phase")

        return WorkflowNode(name=name, phases=tuple(phases))

    # -----------------------------------------------------------------
    # Phase
    # -----------------------------------------------------------------

    def _parse_phase(self) -> PhaseNode:
        """Parse: phase name: INDENT [docstring] stmt+ DEDENT

        Statements can include inline `when` blocks for conditional logic,
        `await` for event triggers, and `grants` for JIT document access.
        """
        self.expect(TokenType.PHASE)
        name = self.expect(TokenType.IDENT).value
        self.expect(TokenType.COLON)
        self.skip_newlines()
        self.expect(TokenType.INDENT)

        # Skip optional docstring at start of phase
        self.skip_newlines()
        self.skip_docstrings()

        requires: list[RequireNode] = []
        grants: list[GrantNode] = []
        actions: list[ActionNode] = []
        outputs: list[OutputNode] = []
        when_blocks: list[WhenBlockNode] = []
        awaits: list[AwaitNode] = []
        certify: CertifyNode | None = None
        evidence: EvidenceNode | None = None

        while not self.match(TokenType.DEDENT, TokenType.EOF):
            self.skip_newlines()
            self.skip_docstrings()
            if self.match(TokenType.DEDENT, TokenType.EOF):
                break

            if self.match(TokenType.REQUIRE):
                requires.append(self._parse_require())
            elif self.match(TokenType.GRANTS):
                grants.append(self._parse_grant())
            elif self.match(TokenType.ACTION):
                actions.append(self._parse_action())
            elif self.match(TokenType.OUTPUT):
                outputs.append(self._parse_output())
            elif self.match(TokenType.CERTIFY):
                if certify is not None:
                    raise self._error(f"Duplicate 'certify' in phase '{name}'")
                certify = self._parse_certify()
            elif self.match(TokenType.EVIDENCE):
                if evidence is not None:
                    raise self._error(f"Duplicate 'evidence' in phase '{name}'")
                evidence = self._parse_evidence()
            elif self.match(TokenType.WHEN):
                when_blocks.append(self._parse_when_block())
            elif self.match(TokenType.AWAIT):
                awaits.append(self._parse_await())
            else:
                raise self._error(
                    f"Expected phase statement (require, grants, action, output, "
                    f"certify, evidence, when, await), got {self.current_token().type.name}"
                )
            self.skip_newlines()

        if self.match(TokenType.DEDENT):
            self.advance()

        return PhaseNode(
            name=name,
            requires=tuple(requires),
            actions=tuple(actions),
            outputs=tuple(outputs),
            grants=tuple(grants),
            certify=certify,
            evidence=evidence,
            when_blocks=tuple(when_blocks),
            awaits=tuple(awaits),
        )

    # -----------------------------------------------------------------
    # Phase statements
    # -----------------------------------------------------------------

    def _parse_require(self) -> RequireNode:
        """Parse require: disambiguate feature_call vs phase_ref vs builtin vs await.

        Disambiguation:
            - AWAIT IDENT   -> await_ref (e.g., require await event_name)
            - IDENT LPAREN  -> feature_call
            - IDENT DOT     -> phase_ref (e.g., eligibility.passed)
            - IDENT (bare)  -> builtin_ref (e.g., all_phases_passed)
        """
        self.expect(TokenType.REQUIRE)

        # Check for `require await event_name`
        if self.match(TokenType.AWAIT):
            self.advance()  # consume 'await'
            trigger_name = self.expect(TokenType.IDENT).value
            return RequireNode(ref=AwaitRefNode(trigger=trigger_name))

        # Read the identifier
        ident_token = self.current_token()
        if not self.match(TokenType.IDENT) and ident_token.type not in KEYWORDS:
            # Allow keyword-named features (e.g., require output_exists)
            if not (ident_token.type == TokenType.IDENT):
                raise self._error(
                    f"Expected identifier after 'require', got {ident_token.type.name}"
                )

        ident = self.advance().value

        # Check what follows
        if self.match(TokenType.LPAREN):
            # Feature call: ident(args)
            args = self._parse_args()
            return RequireNode(ref=FeatureCallNode(name=ident, args=args))

        if self.match(TokenType.DOT):
            # Phase ref: ident.passed or ident.complete
            self.advance()  # consume dot
            condition_token = self.current_token()
            if self.match(TokenType.PASSED):
                self.advance()
                return RequireNode(ref=PhaseRefNode(phase=ident, condition="passed"))
            elif self.match(TokenType.COMPLETE):
                self.advance()
                return RequireNode(ref=PhaseRefNode(phase=ident, condition="complete"))
            elif self.match(TokenType.IDENT):
                condition = self.advance().value
                return RequireNode(ref=PhaseRefNode(phase=ident, condition=condition))
            else:
                raise ParseError(
                    f"Expected 'passed' or 'complete' after '{ident}.', "
                    f"got {condition_token.type.name}",
                    condition_token,
                )

        # Builtin reference (bare identifier)
        return RequireNode(ref=BuiltinRefNode(name=ident))

    def _parse_action(self) -> ActionNode:
        """Parse: action feature_name(args)"""
        self.expect(TokenType.ACTION)
        call = self._parse_feature_call()
        return ActionNode(call=call)

    def _parse_output(self) -> OutputNode:
        """Parse: output TypeName"""
        self.expect(TokenType.OUTPUT)
        type_name = self.expect(TokenType.IDENT).value
        return OutputNode(type_name=type_name)

    def _parse_certify(self) -> CertifyNode:
        """Parse: certify immutable"""
        self.expect(TokenType.CERTIFY)
        if self.match(TokenType.IMMUTABLE) or self.match(TokenType.IDENT):
            qualifier = self.advance().value
        else:
            raise self._error("Expected qualifier after 'certify'")
        return CertifyNode(qualifier=qualifier)

    def _parse_evidence(self) -> EvidenceNode:
        """Parse: evidence evidence_type"""
        self.expect(TokenType.EVIDENCE)
        evidence_type = self.expect(TokenType.IDENT).value
        return EvidenceNode(evidence_type=evidence_type)

    def _parse_grant(self) -> GrantNode:
        """Parse: grants <document_type> [for <number>m]

        Examples:
            grants resume          # Phase-scoped (access while phase pending)
            grants resume for 5m   # Time-scoped (explicit TTL)

        Phase-scoped (no TTL) is the default and preferred pattern.
        """
        self.expect(TokenType.GRANTS)
        document_type = self.expect(TokenType.IDENT).value

        # Optional: for <TTL>m
        ttl_minutes: int | None = None
        if self.match(TokenType.FOR):
            self.advance()
            ttl_token = self.expect(TokenType.INT)
            ttl_minutes = int(ttl_token.value)

            # Consume 'm' suffix (minutes)
            if self.match(TokenType.IDENT) and self.current_token().value == "m":
                self.advance()

        return GrantNode(document_type=document_type, ttl_minutes=ttl_minutes)

    def _parse_await(self) -> AwaitNode:
        """Parse: await trigger_name"""
        self.expect(TokenType.AWAIT)
        trigger_name = self.expect(TokenType.IDENT).value
        return AwaitNode(trigger=trigger_name)

    def _parse_when_block(self) -> WhenBlockNode:
        """Parse inline when block within a phase.

        when predicate:
            await ...
            require ...
            action ...
        """
        self.expect(TokenType.WHEN)
        predicate = self._parse_predicate()
        self.expect(TokenType.COLON)
        self.skip_newlines()
        self.expect(TokenType.INDENT)

        requires: list[RequireNode] = []
        actions: list[ActionNode] = []
        awaits: list[AwaitNode] = []

        while not self.match(TokenType.DEDENT, TokenType.EOF):
            self.skip_newlines()
            if self.match(TokenType.DEDENT, TokenType.EOF):
                break

            if self.match(TokenType.REQUIRE):
                requires.append(self._parse_require())
            elif self.match(TokenType.ACTION):
                actions.append(self._parse_action())
            elif self.match(TokenType.AWAIT):
                awaits.append(self._parse_await())
            else:
                raise self._error(
                    f"Expected 'require', 'action', or 'await' in when block, "
                    f"got {self.current_token().type.name}"
                )
            self.skip_newlines()

        if self.match(TokenType.DEDENT):
            self.advance()

        return WhenBlockNode(
            predicate=predicate,
            requires=tuple(requires),
            actions=tuple(actions),
            awaits=tuple(awaits),
        )

    # -----------------------------------------------------------------
    # Feature calls and arguments
    # -----------------------------------------------------------------

    def _parse_feature_call(self) -> FeatureCallNode:
        """Parse: feature_name(arg1, arg2, key=val)"""
        name = self.expect(TokenType.IDENT).value
        args = self._parse_args()
        return FeatureCallNode(name=name, args=args)

    def _parse_args(self) -> tuple[ArgNode, ...]:
        """Parse: (arg1, arg2, key=val)"""
        self.expect(TokenType.LPAREN)

        args: list[ArgNode] = []
        while not self.match(TokenType.RPAREN, TokenType.EOF):
            if args:
                self.expect(TokenType.COMMA)

            # Read value or name=value
            token = self.current_token()
            if self.match(TokenType.IDENT):
                ident = self.advance().value
                if self.match(TokenType.EQ):
                    # keyword argument: name=value
                    self.advance()
                    value = self._parse_arg_value()
                    args.append(ArgNode(name=ident, value=value))
                else:
                    # positional argument (identifier as value)
                    args.append(ArgNode(name=None, value=ident))
            elif self.match(TokenType.STRING):
                value = self.advance().value
                args.append(ArgNode(name=None, value=value))
            elif self.match(TokenType.INT):
                value = int(self.advance().value)
                args.append(ArgNode(name=None, value=value))
            elif self.match(TokenType.FLOAT):
                value = float(self.advance().value)
                args.append(ArgNode(name=None, value=value))
            elif self.match(TokenType.TRUE):
                self.advance()
                args.append(ArgNode(name=None, value=True))
            elif self.match(TokenType.FALSE):
                self.advance()
                args.append(ArgNode(name=None, value=False))
            else:
                raise ParseError(
                    f"Expected argument, got {token.type.name}",
                    token,
                )

        self.expect(TokenType.RPAREN)
        return tuple(args)

    def _parse_arg_value(self) -> str | int | float | bool:
        """Parse a single argument value."""
        if self.match(TokenType.STRING):
            return self.advance().value
        if self.match(TokenType.INT):
            return int(self.advance().value)
        if self.match(TokenType.FLOAT):
            return float(self.advance().value)
        if self.match(TokenType.TRUE):
            self.advance()
            return True
        if self.match(TokenType.FALSE):
            self.advance()
            return False
        if self.match(TokenType.IDENT):
            return self.advance().value
        raise self._error(f"Expected value, got {self.current_token().type.name}")

    # -----------------------------------------------------------------
    # Situations
    # -----------------------------------------------------------------

    def _parse_situations(self) -> list[SituationNode]:
        """Parse: situations: INDENT situation+ DEDENT"""
        self.expect(TokenType.SITUATIONS)
        self.expect(TokenType.COLON)
        self.skip_newlines()
        self.expect(TokenType.INDENT)

        situations: list[SituationNode] = []
        while not self.match(TokenType.DEDENT, TokenType.EOF):
            self.skip_newlines()
            if self.match(TokenType.DEDENT, TokenType.EOF):
                break
            situations.append(self._parse_situation())
            self.skip_newlines()

        if self.match(TokenType.DEDENT):
            self.advance()

        return situations

    def _parse_situation(self) -> SituationNode:
        """Parse: when predicate: INDENT body DEDENT"""
        self.expect(TokenType.WHEN)
        predicate = self._parse_predicate()
        self.expect(TokenType.COLON)
        self.skip_newlines()
        self.expect(TokenType.INDENT)

        requires: list[RequireNode] = []
        waiting_period: WaitingPeriodNode | None = None

        while not self.match(TokenType.DEDENT, TokenType.EOF):
            self.skip_newlines()
            if self.match(TokenType.DEDENT, TokenType.EOF):
                break

            if self.match(TokenType.WAITING_PERIOD):
                waiting_period = self._parse_waiting_period()
            elif self.match(TokenType.REQUIRE):
                requires.append(self._parse_require())
            else:
                raise self._error(
                    f"Expected 'waiting_period' or 'require' in situation, "
                    f"got {self.current_token().type.name}"
                )
            self.skip_newlines()

        if self.match(TokenType.DEDENT):
            self.advance()

        return SituationNode(
            predicate=predicate,
            waiting_period=waiting_period,
            requires=tuple(requires),
        )

    def _parse_predicate(self) -> PredicateNode:
        """Parse: field.path comparator value"""
        field = self._parse_dotted_name()

        # Comparator
        if not self.match(*_COMPARATORS):
            raise self._error(
                f"Expected comparator (==, !=, >, <, >=, <=), got {self.current_token().type.name}"
            )
        op_token = self.advance()

        # Value
        value = self._parse_arg_value()

        return PredicateNode(field=field, operator=op_token.value, value=value)

    def _parse_waiting_period(self) -> WaitingPeriodNode:
        """Parse: waiting_period 30..90 days"""
        self.expect(TokenType.WAITING_PERIOD)
        min_token = self.expect(TokenType.INT)
        self.expect(TokenType.DOTDOT)
        max_token = self.expect(TokenType.INT)

        # Unit
        if self.match(TokenType.DAYS) or self.match(TokenType.HOURS) or self.match(TokenType.IDENT):
            unit = self.advance().value
        else:
            raise self._error("Expected time unit (days, hours) after range")

        return WaitingPeriodNode(
            min_value=int(min_token.value),
            max_value=int(max_token.value),
            unit=unit,
        )

    # -----------------------------------------------------------------
    # Roles
    # -----------------------------------------------------------------

    def _parse_roles(self) -> list[RoleNode]:
        """Parse: roles: INDENT role+ DEDENT"""
        self.expect(TokenType.ROLES)
        self.expect(TokenType.COLON)
        self.skip_newlines()
        self.expect(TokenType.INDENT)

        roles: list[RoleNode] = []
        while not self.match(TokenType.DEDENT, TokenType.EOF):
            self.skip_newlines()
            if self.match(TokenType.DEDENT, TokenType.EOF):
                break
            roles.append(self._parse_role())
            self.skip_newlines()

        if self.match(TokenType.DEDENT):
            self.advance()

        return roles

    def _parse_role(self) -> RoleNode:
        """Parse: role_name: INDENT props DEDENT"""
        name = self.expect(TokenType.IDENT).value
        self.expect(TokenType.COLON)
        self.skip_newlines()
        self.expect(TokenType.INDENT)

        actions: tuple[str, ...] = ()
        break_glass = False
        requires_mfa = True

        while not self.match(TokenType.DEDENT, TokenType.EOF):
            self.skip_newlines()
            if self.match(TokenType.DEDENT, TokenType.EOF):
                break

            if self.match(TokenType.ACTIONS):
                self.advance()
                self.expect(TokenType.COLON)
                actions = self._parse_ident_list()
            elif self.match(TokenType.BREAK_GLASS):
                self.advance()
                self.expect(TokenType.COLON)
                break_glass = self._parse_bool()
            elif self.match(TokenType.REQUIRES_MFA):
                self.advance()
                self.expect(TokenType.COLON)
                requires_mfa = self._parse_bool()
            else:
                raise self._error(
                    f"Expected role property (actions, break_glass, requires_mfa), "
                    f"got {self.current_token().type.name}"
                )
            self.skip_newlines()

        if self.match(TokenType.DEDENT):
            self.advance()

        return RoleNode(
            name=name,
            actions=actions,
            break_glass=break_glass,
            requires_mfa=requires_mfa,
        )

    # -----------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------

    def _parse_dotted_name(self) -> str:
        """Parse: ident(.ident)* -> dotted string."""
        parts = [self.expect(TokenType.IDENT).value]
        while self.match(TokenType.DOT):
            self.advance()
            parts.append(self.expect(TokenType.IDENT).value)
        return ".".join(parts)

    def _parse_ident_list(self) -> tuple[str, ...]:
        """Parse: [ident, ident, ...]"""
        self.expect(TokenType.LBRACKET)
        items: list[str] = []
        while not self.match(TokenType.RBRACKET, TokenType.EOF):
            if items:
                self.expect(TokenType.COMMA)
            items.append(self.expect(TokenType.IDENT).value)
        self.expect(TokenType.RBRACKET)
        return tuple(items)

    def _parse_bool(self) -> bool:
        """Parse: true | false"""
        if self.match(TokenType.TRUE):
            self.advance()
            return True
        if self.match(TokenType.FALSE):
            self.advance()
            return False
        raise self._error(f"Expected true/false, got {self.current_token().type.name}")

    def _read_version_string(self) -> str:
        """Read version: could be IDENT (2026.01) or INT.INT."""
        # Version might be tokenized as INT DOT INT (e.g., 2026.01)
        # or as a FLOAT (2026.01) or as IDENT
        if self.match(TokenType.INT):
            major = self.advance().value
            if self.match(TokenType.DOT):
                self.advance()
                minor = self.expect(TokenType.INT).value
                return f"{major}.{minor}"
            return major
        if self.match(TokenType.FLOAT):
            return self.advance().value
        if self.match(TokenType.IDENT):
            return self.advance().value
        raise self._error("Expected version string")


def parse_charter(source: str) -> CharterNode:
    """Convenience: lex + parse source text to AST.

    Args:
        source: Charter DSL source text.

    Returns:
        CharterNode AST.
    """
    from .lexer import Lexer

    tokens = Lexer(source).tokenize()
    return Parser(tokens).parse()

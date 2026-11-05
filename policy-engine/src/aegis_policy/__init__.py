"""Immutable local policies; authorization is distinct from authentication."""

from dataclasses import dataclass
import json
import re

REASONS = frozenset({'explicit_allow','explicit_deny','no_match','identity_missing',
                     'permission_missing','policy_unavailable','policy_error','explicit_require_approval'})


def identifier(value):
    if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,127}',value):
        raise ValueError('invalid policy identifier')
    return value


def _members(value):
    if type(value) is not tuple or not 1 <= len(value) <= 128:
        raise ValueError('invalid policy members')
    for item in value: identifier(item)
    if len(set(value)) != len(value): raise ValueError('duplicate policy member')


@dataclass(frozen=True, slots=True)
class Rule:
    id: str
    effect: str
    subjects: tuple[str,...]
    tools: tuple[str,...]
    permissions: tuple[str,...]

    def __post_init__(self):
        identifier(self.id)
        if self.effect not in ('allow','deny','require_approval'): raise ValueError('unsupported policy effect')
        for members in (self.subjects,self.tools,self.permissions): _members(members)

    def matches(self, subject, tool, permission):
        return subject in self.subjects and tool in self.tools and permission in self.permissions


@dataclass(frozen=True, slots=True)
class Decision:
    effect: str
    reason: str
    policy_revision: str | None = None
    rule_id: str | None = None

    def __post_init__(self):
        if type(self.reason) is not str or type(self.effect) is not str or self.reason not in REASONS or self.effect not in ('allow','deny','require_approval'):
            raise ValueError('invalid policy decision')
        if (self.effect=='allow') != (self.reason=='explicit_allow') or (self.effect=='require_approval') != (self.reason=='explicit_require_approval'):
            raise ValueError('inconsistent policy decision')
        explicit=self.reason in ('explicit_allow','explicit_deny','explicit_require_approval')
        if explicit != (self.rule_id is not None): raise ValueError('inconsistent decision rule')
        if explicit and self.policy_revision is None: raise ValueError('missing policy revision')
        for value in (self.policy_revision,self.rule_id):
            if value is not None: identifier(value)


@dataclass(frozen=True, slots=True)
class Policy:
    revision: str
    rules: tuple[Rule,...]
    schema_version: str = 'aegis.policy.v1'

    def __post_init__(self):
        identifier(self.revision)
        if self.schema_version not in ('aegis.policy.v1','aegis.policy.v2'): raise ValueError('invalid policy version')
        if type(self.rules) is not tuple or len(self.rules)>128 or any(type(rule) is not Rule for rule in self.rules):
            raise ValueError('invalid policy rules')
        if self.schema_version=='aegis.policy.v1' and any(rule.effect=='require_approval' for rule in self.rules): raise ValueError('v2 required')
        if len({rule.id for rule in self.rules})!=len(self.rules): raise ValueError('duplicate policy rule')

    @classmethod
    def from_dict(cls, document):
        if type(document) is not dict or set(document)!={'schema_version','revision','rules'} or document['schema_version'] not in ('aegis.policy.v1','aegis.policy.v2'):
            raise ValueError('invalid policy document')
        if type(document['rules']) is not list or len(document['rules'])>128: raise ValueError('invalid policy rules')
        rules=[]
        for value in document['rules']:
            if type(value) is not dict or set(value)!={'id','effect','subjects','tools','permissions'}:
                raise ValueError('invalid policy rule')
            if any(type(value[key]) is not list for key in ('subjects','tools','permissions')):
                raise ValueError('invalid policy members')
            rules.append(Rule(value['id'],value['effect'],tuple(value['subjects']),tuple(value['tools']),tuple(value['permissions'])))
        return cls(document['revision'],tuple(rules),document['schema_version'])

    @classmethod
    def from_json(cls, content):
        def unique(pairs):
            result={}
            for key,value in pairs:
                if key in result: raise ValueError('duplicate policy key')
                result[key]=value
            return result
        try:
            return cls.from_dict(json.loads(content,object_pairs_hook=unique))
        except (TypeError,ValueError,RecursionError):
            raise ValueError('invalid policy document') from None

    def evaluate(self, *, subject, tool, permission):
        identifier(tool)
        if subject is None: return Decision('deny','identity_missing',self.revision)
        identifier(subject)
        if permission is None: return Decision('deny','permission_missing',self.revision)
        identifier(permission)
        matched=sorted((rule for rule in self.rules if rule.matches(subject,tool,permission)),key=lambda rule:(effect_rank(rule.effect),rule.id))
        if not matched: return Decision('deny','no_match',self.revision)
        rule=matched[0]
        return Decision(rule.effect,'explicit_'+rule.effect,self.revision,rule.id)


def effect_rank(effect):
    return {'deny':0,'require_approval':1,'allow':2}[effect]

__all__=['Policy','Rule','Decision']

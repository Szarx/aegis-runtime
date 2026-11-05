"""Explicit configuration and owned tracing lifecycle for an Agent host."""
from contextlib import contextmanager
from dataclasses import asdict,dataclass
from functools import wraps
from importlib import metadata
import inspect
import json
import os
from pathlib import Path
import re
from threading import RLock
from urllib.parse import urlsplit
import aegis
from aegis_policy import Policy,identifier
from aegis_policy.workbench import fingerprint,load_policy
from . import Runtime


def _require(condition):
    if not condition:raise ValueError('invalid application configuration')


@dataclass(frozen=True,slots=True)
class GraphBinding:
    id:str
    revision:str
    node:str
    def __post_init__(self):
        identifier(self.id);identifier(self.revision);identifier(self.node)


@dataclass(frozen=True,slots=True)
class ToolBinding:
    name:str
    permission:str
    execution:str='direct'
    tool_revision:str|None=None
    graph:GraphBinding|None=None
    def __post_init__(self):
        identifier(self.name);identifier(self.permission)
        _require(self.execution in ('direct','reviewed','reviewed_graph','policy'))
        if self.execution!='direct':identifier(self.tool_revision)
        else:_require(self.tool_revision is None)
        _require(type(self.graph) is GraphBinding if self.execution=='reviewed_graph' else self.graph is None)


@dataclass(frozen=True,slots=True)
class Telemetry:
    mode:str
    output_path:Path|None=None
    endpoint:str|None=None
    token_env:str|None=None
    timeout_millis:int=3000
    def __post_init__(self):
        _require(type(self.timeout_millis) is int and 1<=self.timeout_millis<=30000)
        if self.mode=='jsonl':
            _require(isinstance(self.output_path,Path) and self.endpoint is None and self.token_env is None)
        else:
            _require(self.mode=='otlp' and self.output_path is None and type(self.endpoint) is str)
            try:target=urlsplit(self.endpoint);port=target.port
            except ValueError:raise ValueError('invalid application configuration') from None
            _require(target.scheme in ('http','https') and target.hostname and target.username is None and target.password is None and
                not target.query and not target.fragment and target.path=='/v1/traces' and port!=0)
            _require(target.scheme=='https' or target.hostname in ('localhost','127.0.0.1','::1'))
            _require(self.token_env is None or type(self.token_env) is str and re.fullmatch(r'[A-Z_][A-Z0-9_]{0,127}',self.token_env))


@dataclass(frozen=True,slots=True)
class ApplicationConfig:
    service_name:str
    policy:Policy
    tools:tuple[ToolBinding,...]
    telemetry:Telemetry
    schema_version:str='aegis.application.v1'
    def __post_init__(self):
        identifier(self.service_name)
        _require(type(self.policy) is Policy and type(self.telemetry) is Telemetry)
        _require(type(self.tools) is tuple and 1<=len(self.tools)<=128 and all(type(t) is ToolBinding for t in self.tools))
        _require(len({t.name for t in self.tools})==len(self.tools))
        _require(self.schema_version in ('aegis.application.v1','aegis.application.v2','aegis.application.v3','aegis.application.v4'))
        if self.schema_version!='aegis.application.v4':
            _require(self.policy.schema_version=='aegis.policy.v1' and all(t.execution!='policy' for t in self.tools))
        if self.schema_version=='aegis.application.v1':_require(all(t.execution=='direct' for t in self.tools))
        if self.schema_version=='aegis.application.v2':_require(all(t.execution!='reviewed_graph' for t in self.tools))


def load_application(path):
    def unique(pairs):
        value={}
        for key,item in pairs:_require(key not in value);value[key]=item
        return value
    def file(value,base):
        _require(type(value) is str and 1<=len(value)<=4096 and '\x00' not in value)
        target=Path(value);return (base/target).resolve() if not target.is_absolute() else target.resolve()
    try:
        source=Path(path).resolve()
        with source.open('rb') as stream:raw=stream.read(65537)
        _require(len(raw)<=65536)
        doc=json.loads(raw.decode('utf-8'),object_pairs_hook=unique)
        _require(type(doc) is dict and set(doc)=={'schema_version','service_name','policy_file','tools','telemetry'} and doc['schema_version'] in ('aegis.application.v1','aegis.application.v2','aegis.application.v3','aegis.application.v4'))
        _require(type(doc['tools']) is list and 1<=len(doc['tools'])<=128)
        bindings=[]
        for item in doc['tools']:
            keys={'name','permission'} if doc['schema_version']=='aegis.application.v1' else {'name','permission','execution','tool_revision'}
            if doc['schema_version'] in ('aegis.application.v3','aegis.application.v4'):keys=keys|{'graph'}
            _require(type(item) is dict and set(item)==keys)
            if item.get('graph') is not None:
                _require(type(item['graph']) is dict and set(item['graph'])=={'id','revision','node'})
                item={**item,'graph':GraphBinding(**item['graph'])}
            bindings.append(ToolBinding(**item))
        data=doc['telemetry'];_require(type(data) is dict)
        if data.get('mode')=='jsonl':
            _require(set(data)=={'mode','path'})
            telemetry=Telemetry('jsonl',output_path=file(data['path'],source.parent))
        else:
            _require({'mode','endpoint','token_env'}<=set(data)<={'mode','endpoint','token_env','timeout_millis'})
            telemetry=Telemetry(**data)
        return ApplicationConfig(doc['service_name'],load_policy(file(doc['policy_file'],source.parent)),tuple(bindings),telemetry,doc['schema_version'])
    except Exception:raise ValueError('invalid or unreadable application configuration') from None


def _headers(telemetry,environment):
    if telemetry.token_env is None:return {}
    value=environment.get(telemetry.token_env)
    _require(type(value) is str and 1<=len(value)<=4096 and all(33<=ord(c)<=126 for c in value))
    return {'Authorization':'Bearer '+value}


def inspect_application(config, *, subject, environment=None):
    _require(type(config) is ApplicationConfig);identifier(subject)
    telemetry=config.telemetry
    try:_headers(telemetry,os.environ if environment is None else environment);token='valid' if telemetry.token_env else 'not_required'
    except ValueError:token='invalid'
    dependency='not_required'
    if telemetry.mode=='otlp':
        try:metadata.version('opentelemetry-exporter-otlp-proto-http');dependency='installed'
        except metadata.PackageNotFoundError:dependency='missing'
    report=dict(schema_version='aegis.application-inspection.v1',status='blocked' if token=='invalid' or dependency=='missing' else 'valid',
        service_name=config.service_name,subject=subject,policy_revision=config.policy.revision,policy_fingerprint=fingerprint(config.policy),
        telemetry_mode=telemetry.mode,checks=dict(token=token,otlp_package=dependency),
        tools=[dict(name=t.name,permission=t.permission,decision=asdict(config.policy.evaluate(subject=subject,tool=t.name,permission=t.permission))) for t in config.tools],
        not_checked=['Collector connectivity','module/native dependency imports','Agent execution','host authentication','unwrapped tools'])
    if config.schema_version!='aegis.application.v1':
        report['schema_version']='aegis.application-inspection.'+config.schema_version.rsplit('.',1)[1]
        report['not_checked'].append('approval clients, server roles and decisions')
        for row,binding in zip(report['tools'],config.tools):
            row.update(execution=binding.execution,tool_revision=binding.tool_revision,requires_review=binding.execution in ('reviewed','reviewed_graph') or row['decision']['effect']=='require_approval')
            if config.schema_version in ('aegis.application.v3','aegis.application.v4'):row['graph']=asdict(binding.graph) if binding.graph else None
        if config.schema_version in ('aegis.application.v3','aegis.application.v4'):report['not_checked'].append('graph/checkpoint compatibility and optional graph dependency imports')
    return report


class Application:
    def __init__(self,config,*,subject):
        _require(type(config) is ApplicationConfig);identifier(subject)
        self._config=config;self._runtime=Runtime(config.policy,subject=subject)
        self._lock=RLock();self._state='created';self._calls=0;self._bound={};self._sdk=None
        self._flushed=None;self._stopped=None

    def __enter__(self):
        with self._lock:
            if self._state!='created':raise RuntimeError('Application is single use')
            try:
                telemetry=self._config.telemetry
                options=dict(output_path=telemetry.output_path) if telemetry.mode=='jsonl' else dict(
                    endpoint=telemetry.endpoint,headers=_headers(telemetry,os.environ),export_timeout_millis=telemetry.timeout_millis)
                self._sdk=aegis.init(self._config.service_name,**options)
                self._state='active';return self
            except Exception:
                self._state='failed';raise RuntimeError('Application startup failed') from None

    def __exit__(self,*args):self.close();return False

    @contextmanager
    def _lease(self):
        with self._lock:
            if self._state!='active':raise RuntimeError('Application is not active')
            self._calls+=1
        try:yield
        finally:
            with self._lock:self._calls-=1

    def _guard(self,function):
        if inspect.iscoroutinefunction(function):
            @wraps(function)
            async def asynchronous(*args,**kwargs):
                with self._lease():return await function(*args,**kwargs)
            return asynchronous
        @wraps(function)
        def synchronous(*args,**kwargs):
            with self._lease():return function(*args,**kwargs)
        return synchronous

    def tool(self,function=None,*,name=None):
        def bind(fn):
            with self._lock:
                if self._state!='active':raise RuntimeError('Application is not active')
                label=identifier(name if name is not None else fn.__name__)
                permissions={t.name:t.permission for t in self._config.tools if t.execution=='direct'}
                if label not in permissions or label in self._bound:raise ValueError('Tool is unconfigured or already bound')
                wrapped=self._guard(self._runtime.tool(fn,name=label,permission=permissions[label]))
                self._bound[label]=wrapped;return wrapped
        return bind(function) if function is not None else bind

    def policy_tool(self,function=None,*,client,name=None,disclose_arguments=False):
        from .policy_tool import bind_policy
        def bind(fn):return bind_policy(self,fn,client=client,name=name,disclose_arguments=disclose_arguments)
        return bind(function) if function is not None else bind

    def reviewed_tool(self,function=None,*,client,name=None,disclose_arguments=False):
        from .managed_reviewed import bind_reviewed
        def bind(fn):return bind_reviewed(self,fn,client=client,name=name,disclose_arguments=disclose_arguments)
        return bind(function) if function is not None else bind

    def reviewed_graph_tool(self,function=None,*,client,name=None,disclose_arguments=False):
        from .managed_graph import bind_reviewed_graph
        def bind(fn):return bind_reviewed_graph(self,fn,client=client,name=name,disclose_arguments=disclose_arguments)
        return bind(function) if function is not None else bind

    def agent(self,function=None,*,name=None):
        def bind(fn):
            with self._lock:
                if self._state!='active':raise RuntimeError('Application is not active')
                return self._guard(aegis.observe(fn,name=name))
        return bind(function) if function is not None else bind

    def graph(self,graph,*,name=None):
        with self._lock:
            if self._state!='active':raise RuntimeError('Application is not active')
            from .managed_agent_graph import ManagedGraph
            from aegis.langgraph import observe_graph
            return ManagedGraph(self,observe_graph(graph,name=name))

    def close(self):
        with self._lock:
            if self._state=='closed' and self._flushed is not False and self._stopped is not False:return True
            if self._calls or self._state=='closing':raise RuntimeError('Application has unfinished work; await or join before close')
            self._state='closing';sdk=self._sdk
        try:
            try:self._flushed=True if sdk is None else sdk.flush()
            except Exception:self._flushed=False
            finally:
                try:self._stopped=True if sdk is None else sdk.shutdown()
                except Exception:self._stopped=False
        finally:
            with self._lock:self._state='closed'
        return self._flushed and self._stopped

    def status(self):
        with self._lock:
            report=dict(schema_version='aegis.application-status.v1',state=self._state,active_calls=self._calls,
                service_name=self._config.service_name,policy_revision=self._config.policy.revision,
                configured_tools=sorted(t.name for t in self._config.tools),bound_tools=sorted(self._bound),
                unbound_tools=sorted({t.name for t in self._config.tools}-self._bound.keys()),
                flush=self._flushed,shutdown=self._stopped,diagnostics=self._sdk.diagnostics() if self._sdk is not None else None)
            if self._config.schema_version!='aegis.application.v1':
                report['schema_version']='aegis.application-status.'+self._config.schema_version.rsplit('.',1)[1]
                report['tool_modes']={t.name:dict(execution=t.execution,tool_revision=t.tool_revision) for t in self._config.tools}
                if self._config.schema_version in ('aegis.application.v3','aegis.application.v4'):
                    for binding in self._config.tools:report['tool_modes'][binding.name]['graph']=asdict(binding.graph) if binding.graph else None
            return report

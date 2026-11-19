"""Dependency-free MCP stdio server. Calculations run independently in the background."""
import base64
from concurrent.futures import ThreadPoolExecutor
import json
import math
import sys
import threading
from . import __version__, catalogue, data, environments
from . import jobs, signals


def schema(properties=None, required=None):
    return {'type':'object','properties':properties or {},'required':required or [],'additionalProperties':False}


def guides():
    """Topic -> Markdown file: each Skill under its name and each of its references under the file name."""
    found = {}
    for skill in sorted((catalogue.resources()/'skills').iterdir()):
        if (skill/'SKILL.md').is_file():
            found[skill.name] = skill/'SKILL.md'
    for skill in list(found.values()):
        for file in sorted((skill.parent/'references').glob('*.md')):
            found[file.stem] = file
    return found


def guide(topic):
    text = guides()[topic].read_text(encoding='utf-8')
    # Skill front matter addresses Skill loaders, not readers.
    return text.split('---', 2)[2].lstrip() if text.startswith('---') else text


STRING = {'type':'string'}
DOMAINS = [row[0] for row in json.loads((catalogue.resources()/'data'/'domains.en.json').read_text(encoding='utf-8'))]
# Units in which a wavelength can be given: vacuum wavelength, frequency, wavenumber or photon energy.
SPECTRAL_UNITS = [unit for kind in ('length', 'frequency', 'angular frequency', 'wavenumber', 'energy') for unit in data.UNITS[kind]]
TOOLS = [
    ('read_guide', 'Read operating guidance as Markdown. optical-computation: how to connect software, submit programs and read results. optical-research: how to choose a physical model and software. The other topics are the references those two link to, by link name.', schema({'topic':{'enum':list(guides())}},['topic'])),
    ('software_search', 'Find optical software and packaged programs by physical problem, method or name, in English or Chinese; filter by domain and license. Names of one concept match each other (PSF, point spread function, 点扩散函数). Best matches first, and among equal matches software with packaged programs; program names the packaged program that fits the query, ready for submit_calculation(tool, action=program); an item lists the query terms it lacks in missing. install is pip or conda when prepare_environment can install the tool, manual when it needs its own installer.', schema({'query':STRING,'domain':{'enum':DOMAINS},'license_group':{'enum':['open','paid','limited']},'offset':{'type':'integer','minimum':0},'limit':{'type':'integer','minimum':1,'maximum':100},'language':{'enum':['zh','en']}})),
    ('software_details', 'Read one software: native interfaces, installation recipe, upstream MCP/Skills and its packaged programs, each with title, inputs (default and meaning), results and checks. program returns one packaged program with its physics and conventions and its source, to read or adapt and submit as source.', schema({'tool':STRING,'program':STRING,'language':{'enum':['zh','en']}},['tool'])),
    ('materials', 'Refractive index n and extinction coefficient k from the refractiveindex.info database (3576 n,k pages, CC0) with references and conditions. material is a page ID shelf/book/page such as main/Si/Green-2008, or a common name such as SiO2, Si, Au or N-BK7; with wavelength (a number or list in unit, nm by default) the reply gives n and k, without it the page\'s range and references. dispersion adds the group index, the group velocity dispersion in fs^2/mm and D in ps/(nm km) from the page\'s dispersion formula. query searches book and page names; no arguments lists the common names. Pages other than the common ones are downloaded once.', schema({'material':STRING,'query':STRING,'dispersion':{'type':'boolean'},'wavelength':{'anyOf':[{'type':'number','exclusiveMinimum':0},{'type':'array','items':{'type':'number','exclusiveMinimum':0},'minItems':1,'maxItems':10000}]},'unit':{'enum':SPECTRAL_UNITS},'limit':{'type':'integer','minimum':1,'maximum':100}})),
    ('register_software', 'Register a local research library, solver or executable that is not in the published catalogue. Provide its identity, module/distribution names and documentation sources; then use bind_environment. pip, conda (conda-forge packages), python (version specifier) and platforms form an installation recipe, so that prepare_environment and submissions install it. Registration does not download or execute it.', schema({'tool':STRING,'name':STRING,'description':STRING,'kind':{'enum':['python','command']},'modules':{'type':'array','items':STRING},'distributions':{'type':'array','items':STRING},'sources':{'type':'array','items':STRING},'pip':{'type':'array','items':STRING},'conda':{'type':'array','items':STRING},'python':STRING,'platforms':{'type':'array','items':{'enum':list(environments.PLATFORMS)}}},['tool','name','description'])),
    ('registered_software', 'List locally registered research tools beyond the published software catalogue.', schema()),
    ('environments', 'Read a short page of configured software. refresh=true checks only this page’s installed programs; tool selects one connection.', schema({'tool':STRING,'offset':{'type':'integer','minimum':0},'limit':{'type':'integer','minimum':1,'maximum':100},'refresh':{'type':'boolean'}})),
    ('discover_native_software', 'Find local Lumerical, COMSOL, OpticStudio and CST installation paths; inspect adapter requirements and native program examples. Does not launch a licensed solver.', schema({'roots':{'type':'array','items':STRING}})),
    ('bind_native_software', 'Connect an installed commercial solver SDK to its own Python environment. Each calculation owns a software session with full native API, project load/save and data export.', schema({'tool':STRING,'python':STRING,'sdk_path':STRING,'options':{'type':'object'},'threads':{'type':'integer','minimum':1},'concurrency':{'type':'integer','minimum':1},'requirements':{'type':'object','additionalProperties':{'type':'integer','minimum':1}},'env':{'type':'object','additionalProperties':STRING}},['tool'])),
    ('prepare_environment', 'Install a tool from its recipe (pip, or conda-forge for software without wheels) into an environment of its own, in the background; returns a run ID. Submissions do this by themselves for a tool without an environment. packages adds requirements such as scipy or h5py to the tool\'s environment; python selects the base interpreter.', schema({'tool':STRING,'packages':{'type':'array','items':STRING},'python':STRING,'request_id':STRING},['tool'])),
    ('bind_environment', 'Connect an existing scientific Python environment or an explicit native executable; installs nothing. Without tool, binds every catalogue or registered tool whose modules the python interpreter has, and keeps tools already connected.', schema({'tool':STRING,'python':STRING,'command':{'type':'array','items':STRING,'minItems':1},'threads':{'type':'integer','minimum':1},'concurrency':{'type':'integer','minimum':1},'cwd':STRING,'requirements':{'type':'object','additionalProperties':{'type':'integer','minimum':1}},'env':{'type':'object','additionalProperties':STRING}})),
    ('compute_resources', 'Read or update shared CPU and named resource capacities (GPU, solver license, memory slots). Requirements are acquired together across all runs; adapters select the actual hardware or license.', schema({'cpu':{'type':'integer','minimum':1},'pools':{'type':'object','additionalProperties':{'type':'integer','minimum':1}}})),
    ('submit_calculation', 'Start an independent background calculation and return its run ID; with wait (up to 25 seconds) also its state then, and, for one calculation that has finished, its RESULT, files and output folder or its error. action runs a packaged program listed by software_details, with inputs replacing its defaults; source runs a complete native Python program with INPUTS, OUTPUT_DIR and RESULT. sweep maps inputs (name, or name.0 for one element of a list input) to lists of values or {start, stop, points, scale}: every combination (pairing product) or the lists in step (zip) runs as a point point-N; points are computed in groups, one process each, about four groups per CPU slot unless chunk sets the points per process; sweep_results tabulates them. optimize {variables: {input: [low, high]}, minimize or maximize: dotted RESULT path, method, evaluations} searches the variables inside one process (differential evolution, or nelder-mead from the current inputs) and keeps the best evaluation\'s files. run_id appends to an earlier run. A tool without an environment is first installed from its recipe, as step prepare.TOOL. Reuse request_id when retrying.', schema({'tool':STRING,'inputs':{'type':'object'},'action':STRING,'source':STRING,'sweep':{'type':'object'},'pairing':{'enum':['product','zip']},'chunk':{'type':'integer','minimum':1},'optimize':{'type':'object'},'run_id':STRING,'name':STRING,'request_id':STRING,'timeout':{'type':'number','exclusiveMinimum':0},'wait':{'type':'number','minimum':0,'maximum':25}},['tool'])),
    ('sweep_results', 'Tabulate the points of a sweep: each point\'s swept inputs, state and the RESULT values named in values (dotted paths such as checks.energy_error or R.0). minimize or maximize one value to get the best point. save writes sweep.npz/.json in the run folder, gridded over the swept inputs for a full product, for read_array.', schema({'run_id':STRING,'values':{'type':'array','items':STRING},'minimize':STRING,'maximize':STRING,'save':{'type':'boolean'},'offset':{'type':'integer','minimum':0},'limit':{'type':'integer','minimum':1,'maximum':1000}},['run_id'])),
    ('sample_episodes', 'Collect complete episodes for learning in parallel worker processes. source defines make_env() with Gymnasium-style reset/step/close and make_policy(seed) returning an action function; task and policy need id and version. Each worker writes samples/trajectory.jsonl, samples/index.jsonl (one line per completed episode) and typed arrays. continue_from lists earlier runs whose completed episodes are not collected again. Details: read_guide episodes.', schema({'tool':STRING, 'source':STRING, 'task':{'type':'object'}, 'policy':{'type':'object'}, 'episodes':{'type':'integer','minimum':1}, 'workers':{'type':'integer','minimum':1}, 'max_steps':{'type':'integer','minimum':1}, 'seed':{'type':'integer','minimum':0}, 'inputs':{'type':'object'}, 'options':{'type':'object'}, 'continue_from':{'type':'array','items':STRING}, 'on_error':{'enum':['stop','continue']}, 'request_id':STRING, 'timeout':{'type':'number','exclusiveMinimum':0}}, ['tool','source','task','policy','episodes'])),
    ('submit_workflow', 'Submit dependent or independent calculation steps in one request. Each step has id, tool, action (a packaged program) or source, inputs, after, optional timeout and bindings. A binding {input_name: {step, path: [keys]}} copies a value from a predecessor result; {input_name: {step, file: "relative/path"}} gives the location of a file or folder that predecessor wrote, for large data. Supply run_id to append a batch to an existing research run.', schema({'steps':{'type':'array','items':{'type':'object'},'minItems':1},'name':STRING,'request_id':STRING,'run_id':STRING},['steps'])),
    ('run_status', 'Read compact execution state. wait (0–25 seconds) waits for completion without repeated calls. Results stay in files by default; include_results returns step values. Calculations continue after disconnection.', schema({'run_id':STRING,'offset':{'type':'integer','minimum':0},'limit':{'type':'integer','minimum':1,'maximum':200},'include_results':{'type':'boolean'},'wait':{'type':'number','minimum':0,'maximum':25}},['run_id'])),
    ('cancel_run', 'Cancel a research run and its active calculations.', schema({'run_id':STRING},['run_id'])),
    ('result_files', 'List files written so far by a research run, including running calculations. prefix such as "solve/attempt-1/" limits the listing to one step or folder. NPY/NPZ entries include dtype and shape, and the quantity, unit and axis names a program saved with them.', schema({'run_id':STRING,'prefix':STRING,'offset':{'type':'integer','minimum':0},'limit':{'type':'integer','minimum':1,'maximum':500}},['run_id'])),
    ('read_array', 'Read part of an NPY array or NPZ member without loading the whole file. index has one entry per leading axis: an integer selects a position and drops the axis; [start, stop, step] keeps it (Python slice rules, null for open ends); null keeps the whole axis. Beyond max_elements long axes are thinned by uniform steps while short axes (ports, components) stay whole; selection reports the steps used. Complex data returns real and imag; non-finite values are "nan", "inf", "-inf". When the program described the array, the reply adds description (quantity, unit, conventions), axes (coordinates and units of the returned values) and at (the position of each axis fixed by an integer). image draws a one- or two-dimensional selection as a PNG (auto: lines for one axis or a short second one, otherwise a map with a color bar; line; map) and returns the extremes and their positions instead of the values; part draws abs, real, imag, phase or power of complex values and scale log draws log10.', schema({'run_id':STRING,'file':STRING,'member':STRING,'index':{'type':'array','items':{'anyOf':[{'type':'integer'},{'type':'null'},{'type':'array','items':{'type':['integer','null']},'minItems':1,'maxItems':3}]}},'max_elements':{'type':'integer','minimum':1,'maximum':100000},'image':{'enum':['auto','line','map']},'part':{'enum':['abs','real','imag','phase','power']},'scale':{'enum':['linear','log']}},['run_id','file'])),
    ('download_result', 'Copy a result file to a new destination on the MCP host computer. From another computer, read its content with read_result or read_array.', schema({'run_id':STRING,'file':STRING,'destination':STRING},['run_id','file','destination'])),
    ('read_result', 'Read a bounded byte range of a result or log. Text returns UTF-8; binary returns base64. Use read_array for NPY/NPZ data.', schema({'run_id':STRING,'file':STRING,'offset':{'type':'integer','minimum':0},'limit':{'type':'integer','minimum':1,'maximum':65536}},['run_id','file'])),
    ('list_runs', 'Find previous and active research runs after reconnecting.', schema({'state':STRING,'offset':{'type':'integer','minimum':0},'limit':{'type':'integer','minimum':1,'maximum':200}})),
    ('resume_run', 'Rerun unfinished steps of a stopped research run, keeping completed steps and previous output files.', schema({'run_id':STRING},['run_id'])),
]


def invoke(name, args, cancellation=None):
    if name == 'read_guide': return guide(args['topic'])
    if name == 'software_search': return catalogue.search(**args)
    if name == 'materials':
        from . import materials
        return materials.lookup(**args)
    if name == 'software_details': return environments.details(**args)
    if name == 'register_software': return environments.register(**args)
    if name == 'registered_software': return {'software': environments.registered()}
    if name == 'environments': return environments.page(**args)
    if name in ('discover_native_software','bind_native_software'):
        from . import native
        return native.discover(**args) if name == 'discover_native_software' else native.bind(**args)
    if name == 'bind_environment': return environments.bind(**args)
    if name == 'prepare_environment': return jobs.prepare(**args)
    if name == 'compute_resources': return jobs.resources(**args)
    if name == 'submit_calculation':
        from . import studies
        return studies.submit(**{'name': 'Optics research', **args}, cancel=cancellation)
    if name == 'sweep_results':
        from . import studies
        return studies.table(**args)
    if name == 'sample_episodes':
        from . import sampling
        return sampling.submit(**args)
    if name == 'submit_workflow': return jobs.submit(**args)
    if name == 'run_status': return jobs.status(**{'include_results':False, **args}, cancel=cancellation)
    if name == 'cancel_run': return jobs.cancel(**args)
    if name == 'result_files': return jobs.files(**args)
    if name == 'download_result': return jobs.download(**args)
    if name == 'read_result': return jobs.read_result(**args)
    if name == 'read_array': return jobs.read_array(**args)
    if name == 'resume_run': return jobs.resume(**args)
    if name == 'list_runs': return jobs.list_runs(**args)
    raise ValueError('Unknown tool: '+name)


class Connection:
    """One stdio session: requests are read in order and answered as each completes.

    Tool calls run on a bounded thread pool; status waits have their own
    threads, so no number of waits delays a query or cancel_run sent after
    them. Each response is written as one line. MCP request cancellation ends
    the request's wait; cancel_run stops a calculation. Calculations already
    accepted continue after disconnection.
    """
    WORKERS = 16   # tool calls executing at once, waits excluded
    PENDING = 256  # requests accepted and not yet answered

    def __init__(self, outgoing):
        self.outgoing, self.lock = outgoing, threading.Lock()
        self.active, self.withdrawn, self.state = {}, set(), threading.Lock()

    def send(self, message):
        text = json.dumps(message, ensure_ascii=False, allow_nan=False) + '\n'
        with self.lock:
            try:
                self.outgoing.write(text); self.outgoing.flush()
            except (OSError, ValueError):
                pass  # The client has gone; accepted calculations continue.

    def cancel(self, request_id):
        # The host no longer expects this reply (MCP notifications/cancelled).
        if not valid_id(request_id): return
        with self.state:
            cancellation = self.active.get(key(request_id))
            if cancellation: self.withdrawn.add(key(request_id))
        if cancellation: cancellation.set()

    def accept(self, request_id):
        with self.state:
            if len(self.active) >= self.PENDING:
                raise RuntimeError(f'{self.PENDING} requests are already in progress on this connection')
            if key(request_id) in self.active:
                raise ValueError('This request ID is already in progress')
            cancellation = self.active[key(request_id)] = signals.Cancellation()
            return cancellation

    def call(self, request_id, params, cancellation):
        try:
            with self.state:
                if key(request_id) in self.withdrawn: return
            result = tool_result(params, cancellation)
            with self.state:
                withdrawn = key(request_id) in self.withdrawn
            if not withdrawn:
                self.send({'jsonrpc':'2.0','id':request_id,'result':result})
        except Exception as error:
            self.send({'jsonrpc':'2.0','id':request_id,'error':{'code':-32603,'message':str(error)}})
        finally:
            with self.state:
                self.active.pop(key(request_id), None); self.withdrawn.discard(key(request_id))

    def close(self):
        # End of input: waits return their current state; replies are still written.
        with self.state:
            pending = list(self.active.values())
        for cancellation in pending: cancellation.set()


def valid_id(request_id):
    return type(request_id) in (str, int) or type(request_id) is float and math.isfinite(request_id)


def key(request_id):
    # JSON-RPC distinguishes 1 from "1".
    return (type(request_id).__name__, request_id)


def waiting(params):
    """A run_status or submit_calculation call that waits for completion; it occupies no worker."""
    if not isinstance(params, dict) or params.get('name') not in ('run_status', 'submit_calculation'): return False
    arguments = params.get('arguments')
    return isinstance(arguments, dict) and bool(arguments.get('wait'))


def conform(value, spec, name):
    """Return an argument value that satisfies its schema, or raise ValueError naming what is expected.

    Numbers and booleans sent as text are accepted; some hosts send every argument as a string.
    """
    if 'anyOf' in spec:
        for option in spec['anyOf']:
            try: return conform(value, option, name)
            except ValueError: pass
        raise ValueError(name+' has an unsupported form')
    if 'enum' in spec:
        if value not in spec['enum']: raise ValueError(name+' must be one of: '+', '.join(map(str, spec['enum'])))
        return value
    kinds = spec.get('type')
    kinds = kinds if isinstance(kinds, list) else [kinds]
    if value is None and 'null' in kinds: return None
    kind = next((k for k in kinds if k != 'null'), None)
    if kinds == ['null']: raise ValueError(name+' must be null')
    if kind in ('integer', 'number'):
        low, high = spec.get('minimum', spec.get('exclusiveMinimum')), spec.get('maximum')
        expected = name+(' must be an integer' if kind == 'integer' else ' must be a number')+ \
            (f' from {low} to {high}' if low is not None and high is not None else f' above {low}' if 'exclusiveMinimum' in spec
             else f' of at least {low}' if low is not None else '')
        if isinstance(value, str):
            try: value = float(value) if kind == 'number' else int(value)
            except ValueError: raise ValueError(expected) from None
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value): raise ValueError(expected)
        if kind == 'integer':
            if value != int(value): raise ValueError(expected)
            value = int(value)
        if 'minimum' in spec and value < spec['minimum'] or 'exclusiveMinimum' in spec and value <= spec['exclusiveMinimum'] \
           or high is not None and value > high: raise ValueError(expected)
    elif kind == 'boolean':
        if isinstance(value, str) and value.lower() in ('true', 'false'): value = value.lower() == 'true'
        if not isinstance(value, bool): raise ValueError(name+' must be true or false')
    elif kind == 'string':
        if not isinstance(value, str): raise ValueError(name+' must be text')
    elif kind == 'array':
        if not isinstance(value, list): raise ValueError(name+' must be a list')
        if len(value) < spec.get('minItems', 0) or len(value) > spec.get('maxItems', len(value)):
            raise ValueError(f"{name} must have {spec.get('minItems', 0)} to {spec.get('maxItems', 'any number of')} items")
        if 'items' in spec: value = [conform(item, spec['items'], f'{name}[{i}]') for i, item in enumerate(value)]
    elif kind == 'object':
        if not isinstance(value, dict): raise ValueError(name+' must be an object')
        if isinstance(spec.get('additionalProperties'), dict):
            value = {key: conform(item, spec['additionalProperties'], f'{name}.{key}') for key, item in value.items()}
    return value


def arguments(name, args, spec):
    """Tool arguments matched against the tool's input schema, with messages an agent can act on."""
    if not isinstance(args, dict): raise ValueError('arguments must be an object')
    unknown, missing = sorted(set(args)-set(spec['properties'])), sorted(set(spec['required'])-set(args))
    if unknown: raise ValueError(f"{name} has no argument {', '.join(unknown)}; it takes: {', '.join(spec['properties']) or 'no arguments'}")
    if missing: raise ValueError(f"{name} needs: {', '.join(missing)}")
    return {key: conform(value, spec['properties'][key], key) for key, value in args.items()}


def tool_result(params, cancellation=None):
    try:
        name = params['name']; args = params.get('arguments') or {}
        spec = next((s for n,d,s in TOOLS if n == name), None)
        if spec is None: raise ValueError('Unknown tool: '+name+'. Tools: '+', '.join(n for n,d,s in TOOLS))
        value = invoke(name, arguments(name, args, spec), cancellation)
        if isinstance(value, str):  # Markdown guidance is returned as written
            return {'content':[{'type':'text','text':value}], 'structuredContent':{'text':value}, 'isError':False}
        picture = value.pop('_image', None) if isinstance(value, dict) else None
        content = [{'type':'text','text':json.dumps(value,ensure_ascii=False,allow_nan=False)}]
        if picture is not None:
            content.insert(0, {'type':'image','data':base64.b64encode(picture).decode('ascii'),'mimeType':'image/png'})
        return {'content':content, 'structuredContent':value, 'isError':False}
    except Exception as error:
        return {'content':[{'type':'text','text':str(error) or type(error).__name__}], 'isError':True}


def respond(method, params):
    if method == 'initialize':
        proposed = params.get('protocolVersion')
        return {'protocolVersion':proposed if proposed in SUPPORTED else '2025-11-25',
                'serverInfo':{'name':'optics-photonics','version':__version__},
                'capabilities':{'tools':{'listChanged':False},'resources':{}},
                'instructions':INSTRUCTIONS}
    if method == 'ping': return {}
    if method == 'tools/list':
        return {'tools':[{'name':n,'description':d,'inputSchema':s} for n,d,s in TOOLS]}
    if method == 'resources/list':
        return {'resources':[{'uri':'optics://guides/'+name,'name':name,'mimeType':'text/markdown'} for name in guides()]}
    if method == 'resources/read':
        uri = params.get('uri','')
        name = uri.removeprefix('optics://guides/')
        if uri != 'optics://guides/'+name or name not in guides():
            raise ValueError('Unknown optical guide')
        return {'contents':[{'uri':uri,'mimeType':'text/markdown','text':guide(name)}]}
    return None


SUPPORTED = {'2025-11-25','2025-06-18','2025-03-26','2024-11-05'}
INSTRUCTIONS = ('Optics and photonics research environment. Flow: software_search (any language, synonyms and abbreviations; it names '
                'the packaged program that fits) and software_details to choose software and see its packaged programs; materials for refractive indices; submit_calculation runs a packaged program (action) or '
                'a complete program (source receives INPUTS and OUTPUT_DIR and sets RESULT), installs the software from its recipe '
                'when needed, and with sweep or optimize runs a parameter study; its wait returns the result of a short calculation '
                'in the same call; submit_workflow chains steps; run_status with wait to follow; result_files, read_result, read_array and sweep_results to read results. Runs continue after '
                'disconnection; list_runs finds them. read_guide optical-computation explains execution, read_guide '
                'optical-research the choice of model and software. Solver installation and licenses remain those of the upstream software.')


def serve(input_stream=None, output_stream=None):
    incoming = input_stream or sys.stdin
    connection = Connection(output_stream or sys.stdout)
    with ThreadPoolExecutor(Connection.WORKERS, thread_name_prefix='optics-mcp') as pool, \
         ThreadPoolExecutor(Connection.PENDING, thread_name_prefix='optics-mcp-wait') as waits:
        try:
            for line in incoming:
                if not line.strip(): continue
                id = None
                try:
                    request = json.loads(line)
                    if not isinstance(request, dict) or request.get('jsonrpc') != '2.0':
                        raise ValueError('Expected a JSON-RPC 2.0 request')
                    method = request.get('method'); params = request.get('params') or {}
                    if 'id' not in request:
                        if method == 'notifications/cancelled' and isinstance(params, dict):
                            connection.cancel(params.get('requestId'))
                        continue
                    if not valid_id(request['id']):
                        raise ValueError('A request ID is a string or a number')
                    id = request['id']
                    if method == 'tools/call':
                        lane = waits if waiting(params) else pool
                        lane.submit(connection.call, id, params, connection.accept(id))
                        continue
                    result = respond(method, params)
                    if result is None:
                        connection.send({'jsonrpc':'2.0','id':id,'error':{'code':-32601,'message':'Method not found'}}); continue
                    connection.send({'jsonrpc':'2.0','id':id,'result':result})
                except json.JSONDecodeError:
                    connection.send({'jsonrpc':'2.0','id':None,'error':{'code':-32700,'message':'Invalid JSON'}})
                except Exception as error:
                    connection.send({'jsonrpc':'2.0','id':id,'error':{'code':-32600,'message':str(error)}})
        finally:
            # End waits promptly; submissions already accepted finish registering.
            connection.close()

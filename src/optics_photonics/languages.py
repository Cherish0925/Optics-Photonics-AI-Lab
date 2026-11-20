"""Programs in a software's own language, run by its executable.

The worker writes the program as optics_program<suffix> next to a short main
file in the same language. The main file defines INPUTS (the calculation's
inputs) and OUTPUT_DIR, runs the program and writes RESULT as JSON to
script-result.json; the executable runs in that folder. Values cross as JSON:
numbers, strings, booleans, null, lists and objects. Complex values and large
arrays belong in files under OUTPUT_DIR.
"""
import json
import math
import re
from pathlib import Path

PROGRAM, INPUT_FILE, RESULT_FILE, LOG_FILE = 'optics_program', 'script-inputs.json', 'script-result.json', 'script.log'

# How each language receives INPUTS, how its main file is run, and what the executable must support.
LANGUAGES = {
    'matlab': {'suffix': '.m', 'main': 'optics_main.m',
               'command': ['{executable}', '-sd', '{folder}', '-batch', 'optics_main'],
               'inputs': 'struct from jsondecode', 'requires': 'MATLAB R2019a or later (-batch)',
               'sources': ['https://www.mathworks.com/help/matlab/ref/matlablinux.html',
                           'https://www.mathworks.com/help/matlab/ref/jsondecode.html']},
    'octave': {'suffix': '.m', 'main': 'optics_main.m',
               'command': ['{executable}', '--no-gui', '--quiet', '--norc', '--no-window-system', '{main}'],
               'inputs': 'struct from jsondecode', 'requires': 'GNU Octave 7 or later (jsondecode, jsonencode)',
               'sources': ['https://octave.org/NEWS-7.html']},
    'julia': {'suffix': '.jl', 'main': 'optics_main.jl',
              'command': ['{executable}', '--startup-file=no', '--history-file=no', '--threads={threads}', '{project}', '{main}'],
              'inputs': 'Dict{String,Any}', 'requires': 'Julia 1.6 or later; no packages',
              'sources': ['https://docs.julialang.org/en/v1/manual/command-line-interface/']},
    'wolfram': {'suffix': '.wl', 'main': 'optics_main.wls',
                'command': ['{executable}', '-file', '{main}'],
                'inputs': 'Association from Import[..., "RawJSON"]; the output folder is OUTPUTDIR', 'requires': 'wolframscript with a local Wolfram Engine or Mathematica',
                'sources': ['https://reference.wolfram.com/language/ref/program/wolframscript.html',
                            'https://reference.wolfram.com/language/ref/format/RawJSON.html']},
    'maple': {'suffix': '.mpl', 'main': 'optics_main.mpl',
              'command': ['{executable}', '-q', '{main}'],
              'inputs': 'table from JSON:-ParseFile', 'requires': 'Maple 2015 or later (JSON package); maple, or cmaple on Windows',
              'sources': ['https://www.maplesoft.com/support/help/maple/view.aspx?path=maple',
                          'https://www.maplesoft.com/support/help/maple/view.aspx?path=JSON']},
    'lua': {'suffix': '.lua', 'main': 'optics_main.lua',
            'command': ['{executable}', '{main}'],
            'inputs': 'table; JSON.null preserves null, JSON.array{} and JSON.object{} distinguish empty containers',
            'requires': 'a Lua interpreter, such as S4',
            'sources': ['https://web.stanford.edu/group/fan/S4/tutorial.html']},
    'lsf': {'suffix': '.lsf', 'main': 'optics_main.lsf',
            'command': ['{executable}', '-nw', '-trust-script', '-exit', '-run', '{main}'],
            'inputs': 'one variable per input; RESULT is saved by jsonsave in Lumerical notation',
            'requires': 'a Lumerical design environment such as fdtd-solutions',
            'sources': ['https://optics.ansys.com/hc/en-us/articles/52492316567187-CommandLine-Win-Lin-DesignEnvironmentOptions',
                        'https://optics.ansys.com/hc/en-us/articles/360034928313']},
}

NAME = re.compile(r'[A-Za-z][A-Za-z0-9_]*\Z')
# A packaged program in one of these languages is recognized by its suffix; its leading comment declares it.
COMMENTS = {'.jl': ('julia', '#'), '.m': ('matlab', '%'), '.lua': ('lua', '--'), '.mpl': ('maple', '#'), '.lsf': ('lsf', '#'),
            '.wl': ('wolfram', '(*')}
FAMILIES = {'octave': 'matlab'}   # Octave runs programs written for the MATLAB language


def declaration(text, suffix):
    """Title, physics and PROGRAM declaration from the leading comment of a program in another language.

    The comment holds the title line, the physics, then a line PROGRAM followed by JSON:
    {"inputs": {name: [default, meaning]}, "results": "...", "checks": "..."}.
    """
    name, prefix = COMMENTS[suffix]
    lines = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith(prefix):
            break
        body = line[len(prefix):]
        lines.append((body[:-2] if name == 'wolfram' and body.endswith('*)') else body).strip())
    if 'PROGRAM' not in lines:
        raise ValueError('The leading comment of a program ends with a line PROGRAM and its JSON declaration')
    at = lines.index('PROGRAM')
    spec = json.loads('\n'.join(lines[at + 1:]))
    spec['inputs'] = {key: (default, about) for key, (default, about) in spec['inputs'].items()}
    return {'title': lines[0], 'about': ' '.join(' '.join(lines[1:at]).split()), 'language': name, **spec}


def family(name):
    return FAMILIES.get(name, name)


def described(result, folder):
    """Arrays a program returned under RESULT.save become FILE.npz and FILE.json, as data.save writes them.

    save is {"file": NAME, "arrays": {name: {"values": nested lists, "quantity", "unit", "axes", ...}}}; the reply
    keeps the file name under data. Programs in languages without an NPZ writer describe their arrays this way.
    """
    if not isinstance(result, dict) or not isinstance(result.get('save'), dict):
        return result
    from . import arrays
    spec = result['save']
    numbers, descriptions = {}, {}
    for key, item in spec.get('arrays', {}).items():
        def flatten(value):
            if not isinstance(value, list):
                return [value], []
            children = [flatten(child) for child in value]
            shape = children[0][1] if children else []
            if any(child_shape != shape for _, child_shape in children):
                raise ValueError(f'{key}: array rows must have the same shape')
            return [number for values, _ in children for number in values], [len(value), *shape]
        numbers[key] = flatten(item['values'])
        descriptions[key] = {k: v for k, v in item.items() if k != 'values'}
    written = arrays.write(Path(folder) / str(spec.get('file', 'data')), numbers, descriptions)
    return {**{key: value for key, value in result.items() if key != 'save'}, 'data': written['data']}


def language(name):
    if name not in LANGUAGES:
        raise ValueError('Script languages: ' + ', '.join(LANGUAGES))
    return LANGUAGES[name]


def quoted(text, escapes):
    return '"' + ''.join(escapes.get(c, c) for c in text) + '"'


JULIA = {'\\': '\\\\', '"': '\\"', '$': '\\$', '\n': '\\n', '\r': '\\r', '\t': '\\t'}
LUA = {'\\': '\\\\', '"': '\\"', '\n': '\\n', '\r': '\\r', '\t': '\\t', '\0': '\\000'}
WOLFRAM = {'\\': '\\\\', '"': '\\"', '\n': '\\n', '\r': '\\r', '\t': '\\t'}
MAPLE = WOLFRAM


def number(value):
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError('Inputs are finite numbers')
    return repr(value)


def julia(value):
    """A Julia expression for a JSON value; homogeneous number lists become typed vectors."""
    if value is None: return 'nothing'
    if isinstance(value, bool): return 'true' if value else 'false'
    if isinstance(value, (int, float)): return number(value)
    if isinstance(value, str): return quoted(value, JULIA)
    if isinstance(value, list):
        typed = value and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in value)
        return ('[' if typed else 'Any[') + ', '.join(julia(v) for v in value) + ']'
    if isinstance(value, dict):
        return 'Dict{String,Any}(' + ', '.join(quoted(str(k), JULIA) + ' => ' + julia(v) for k, v in value.items()) + ')'
    raise ValueError('Inputs are JSON values')


def lua(value):
    """A Lua expression retaining JSON nulls and the distinction between lists and objects."""
    if value is None: return 'JSON.null'
    if isinstance(value, bool): return 'true' if value else 'false'
    if isinstance(value, (int, float)): return number(value)
    if isinstance(value, str): return quoted(value, LUA)
    if isinstance(value, list): return 'JSON.array{' + ', '.join(lua(v) for v in value) + '}'
    if isinstance(value, dict): return 'JSON.object{' + ', '.join('[' + quoted(str(k), LUA) + '] = ' + lua(v) for k, v in value.items()) + '}'
    raise ValueError('Inputs are JSON values')


def lsf(name, value):
    """A Lumerical script assignment: numbers, booleans, strings, and numeric vectors or matrices."""
    if not NAME.match(name):
        raise ValueError(f'Input {name} is not a Lumerical variable name')
    def scalar(v):
        if isinstance(v, bool): return '1' if v else '0'
        if isinstance(v, (int, float)): return number(v)
        raise ValueError(f'Input {name} holds a value a Lumerical script cannot take; use numbers, strings, '
                         'or lists of numbers (a list of equal rows is a matrix)')
    if isinstance(value, str):
        if '"' in value or '\n' in value:
            raise ValueError(f'Input {name} holds a quotation mark or line break')
        text = '"' + value + '"'
    elif isinstance(value, list):
        rows = value if value and all(isinstance(row, list) for row in value) else [value]
        if len({len(row) for row in rows}) > 1:
            raise ValueError(f'Rows of input {name} differ in length')
        text = '[' + '; '.join(', '.join(scalar(v) for v in row) for row in rows) + ']'
    else:
        text = scalar(value)
    return f'{name} = {text};'


JULIA_WRITER = r'''
function optics_json(io, x)
    if x === nothing || x === missing
        print(io, "null")
    elseif x isa Bool
        print(io, x ? "true" : "false")
    elseif x isa Integer
        print(io, x)
    elseif x isa Real
        isfinite(x) ? print(io, repr(Float64(x))) : print(io, "null")
    elseif x isa AbstractString || x isa Symbol || x isa Char
        print(io, '"')
        for c in string(x)
            if c == '"' || c == '\\'
                print(io, '\\', c)
            elseif c < ' '
                print(io, "\\u", string(UInt16(c), base=16, pad=4))
            else
                print(io, c)
            end
        end
        print(io, '"')
    elseif x isa AbstractDict || x isa NamedTuple
        print(io, '{')
        for (i, (k, v)) in enumerate(pairs(x))
            i > 1 && print(io, ',')
            optics_json(io, string(k)); print(io, ':'); optics_json(io, v)
        end
        print(io, '}')
    elseif x isa AbstractArray && ndims(x) > 1
        optics_json(io, [selectdim(x, 1, i) for i in axes(x, 1)])
    elseif x isa AbstractArray || x isa Tuple
        print(io, '[')
        for (i, v) in enumerate(x)
            i > 1 && print(io, ',')
            optics_json(io, v)
        end
        print(io, ']')
    else
        error("RESULT holds a $(typeof(x)); return numbers, strings, arrays and dictionaries, and save other data under OUTPUT_DIR")
    end
end
'''

LUA_WRITER = r'''
JSON = {null = {}}
local optics_array, optics_object = {}, {}
function JSON.array(x) return setmetatable(x or {}, optics_array) end
function JSON.object(x) return setmetatable(x or {}, optics_object) end
local function optics_json(x)
  local kind = type(x)
  if x == nil or x == JSON.null then return "null"
  elseif kind == "boolean" then return x and "true" or "false"
  elseif kind == "number" then
    if x ~= x or x == math.huge or x == -math.huge then return "null" end
    if math.type and math.type(x) == "integer" then return string.format("%d", x) end
    return string.format("%.17g", x)
  elseif kind == "string" then
    return '"' .. (x:gsub('[%c"\\]', function(c)
      if c == '"' or c == "\\" then return "\\" .. c end
      return string.format("\\u%04x", c:byte())
    end)) .. '"'
  elseif kind == "table" then
    local parts, length = {}, 0
    local array = getmetatable(x) ~= optics_object
    for k in pairs(x) do
      if type(k) ~= "number" or k < 1 or k % 1 ~= 0 then array = false
      else length = math.max(length, k) end
    end
    if getmetatable(x) == optics_array and not array then
      error("A JSON array has only positive integer keys")
    end
    if array then
      for i = 1, length do parts[#parts + 1] = optics_json(x[i]) end
      return "[" .. table.concat(parts, ",") .. "]"
    end
    for k, v in pairs(x) do parts[#parts + 1] = optics_json(tostring(k)) .. ":" .. optics_json(v) end
    return "{" .. table.concat(parts, ",") .. "}"
  end
  error("RESULT holds a " .. kind .. "; return numbers, strings and tables, and save other data under OUTPUT_DIR")
end
'''


def main(name, folder, inputs):
    """The main file's text: INPUTS and OUTPUT_DIR, the program, then RESULT written as JSON."""
    folder = Path(folder)
    path = lambda file: (folder / file).as_posix()
    program = path(PROGRAM + LANGUAGES[name]['suffix'])
    result = path(RESULT_FILE)
    if name in ('matlab', 'octave'):
        text = lambda s: "'" + s.replace("'", "''") + "'"
        return '\n'.join([
            f"INPUTS = jsondecode(fileread({text(path(INPUT_FILE))}));",
            f"OUTPUT_DIR = {text(folder.as_posix())};",
            f"run({text(program)});",
            "if ~exist('RESULT', 'var')",
            "  error('optics:result', 'Set RESULT to the result of the calculation');",
            "end",
            f"optics_file = fopen({text(result)}, 'w');",
            "fprintf(optics_file, '%s', jsonencode(RESULT));",
            "fclose(optics_file);", ''])
    if name == 'julia':
        return '\n'.join([f'INPUTS = {julia(inputs)}', f'OUTPUT_DIR = {quoted(folder.as_posix(), JULIA)}',
                          f'include({quoted(program, JULIA)})',
                          'isdefined(Main, :RESULT) || error("Set RESULT to the result of the calculation")',
                          JULIA_WRITER, f'open(io -> optics_json(io, RESULT), {quoted(result, JULIA)}, "w")', ''])
    if name == 'wolfram':
        return '\n'.join([f'INPUTS = Import[{quoted(path(INPUT_FILE), WOLFRAM)}, "RawJSON"];',
                          f'OUTPUTDIR = {quoted(folder.as_posix(), WOLFRAM)};',
                          f'If[Get[{quoted(program, WOLFRAM)}] === $Failed, Exit[1]];',
                          'If[!ValueQ[RESULT], Print["Set RESULT to the result of the calculation"]; Exit[1]];',
                          f'Export[{quoted(result, WOLFRAM)}, RESULT, "RawJSON"];', ''])
    if name == 'maple':
        return '\n'.join([f'INPUTS := JSON:-ParseFile({quoted(path(INPUT_FILE), MAPLE)}):',
                          f'OUTPUT_DIR := {quoted(folder.as_posix(), MAPLE)}:',
                          f'read {quoted(program, MAPLE)}:',
                          'if not assigned(RESULT) then error "Set RESULT to the result of the calculation" end if:',
                          f'optics_file := fopen({quoted(result, MAPLE)}, WRITE, TEXT):',
                          'fprintf(optics_file, "%s", JSON:-ToString(RESULT)):', 'fclose(optics_file):', ''])
    if name == 'lua':
        return '\n'.join([LUA_WRITER, f'INPUTS = {lua(inputs)}', f'OUTPUT_DIR = {quoted(folder.as_posix(), LUA)}',
                          f'dofile({quoted(program, LUA)})',
                          'if RESULT == nil then error("Set RESULT to the result of the calculation") end',
                          f'local optics_file = assert(io.open({quoted(result, LUA)}, "w"))',
                          'optics_file:write(optics_json(RESULT))', 'optics_file:close()', ''])
    raise ValueError(name)


LOCAL_FUNCTION = re.compile(r'^function\b', re.MULTILINE)


def functions_first(script):
    """A MATLAB script ends with its local functions; Octave defines a function when it reads it, so they go first."""
    found = LOCAL_FUNCTION.search(script)
    return script if found is None else '1;\n' + script[found.start():].rstrip() + '\n\n' + script[:found.start()]


def prepare(name, script, inputs, folder):
    """Write the program, its inputs and the main file into folder; returns the main file."""
    spec = language(name)
    if not isinstance(script, str) or not script.strip():
        raise ValueError('script is the text of a program in ' + name)
    folder = Path(folder)
    (folder / INPUT_FILE).write_text(json.dumps(inputs, ensure_ascii=False, allow_nan=False), encoding='utf-8')
    main_file = folder / spec['main']
    if name == 'lsf':
        # A Lumerical script runs as one file: the inputs as variables, the program, then jsonsave of RESULT.
        lines = [f'OUTPUT_DIR = "{folder.as_posix()}";'] + [lsf(key, value) for key, value in inputs.items()]
        if '"' in folder.as_posix():
            raise ValueError('The output folder holds a quotation mark')
        main_file.write_text('\n'.join(lines + [script, f'jsonsave("{(folder / RESULT_FILE).as_posix()}", RESULT);', '']),
                             encoding='utf-8')
        (folder / (PROGRAM + spec['suffix'])).write_text(script, encoding='utf-8')
        return main_file
    (folder / (PROGRAM + spec['suffix'])).write_text(functions_first(script) if name == 'octave' else script, encoding='utf-8')
    main_file.write_text(main(name, folder, inputs), encoding='utf-8')
    return main_file


def command(name, executable, folder, *, project=None, threads=1, arguments=()):
    """The command that runs the main file in folder."""
    spec = language(name)
    values = {'{executable}': str(executable), '{folder}': Path(folder).as_posix(),
              '{main}': (Path(folder) / spec['main']).as_posix(), '{threads}': str(threads)}
    out = []
    for part in spec['command']:
        if part == '{project}':
            if project: out.append('--project=' + str(project))
            continue
        for key, value in values.items():
            part = part.replace(key, value)
        out.append(part)
    return out[:1] + list(arguments) + out[1:]


def result(folder, name=None):
    """RESULT of the program, written by the main file."""
    file = Path(folder) / RESULT_FILE
    if not file.is_file():
        raise RuntimeError('The program finished without RESULT; set RESULT, and read ' + LOG_FILE + ' in the output folder')
    value = json.loads(file.read_text(encoding='utf-8'))
    if name == 'lsf':
        # jsonsave writes named workspace variables, even when only RESULT is requested.
        if not isinstance(value, dict) or 'RESULT' not in value:
            raise ValueError('Lumerical jsonsave did not return the RESULT variable')
        return value['RESULT']
    return value


def guide(name):
    """What a program in this language receives and sets."""
    spec = language(name)
    output = 'OUTPUTDIR' if name == 'wolfram' else 'OUTPUT_DIR'
    received = 'one variable per input' if name == 'lsf' else 'INPUTS (' + spec['inputs'] + ')'
    return {'language': name, 'file': PROGRAM + spec['suffix'], 'receives': f'{received} and {output}',
            'sets': 'RESULT: numbers, strings, lists and objects' + ('; saved with jsonsave' if name == 'lsf' else ''),
            'requires': spec['requires'], 'sources': spec['sources']}

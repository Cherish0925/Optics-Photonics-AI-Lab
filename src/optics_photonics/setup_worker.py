"""Prepare a scientific environment as an ordinary background step."""
import json
import os
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from optics_photonics.environments import prepare, read

request=json.loads(Path(os.environ['OPTICS_REQUEST_FILE']).read_text(encoding='utf-8'))['inputs']
existing=read(request['home'])['tools'].get(request['tool'])
if request.get('if_missing') and existing:
    # Prepared or bound since this step was submitted; that environment is kept.
    result={'tool':request['tool'],**existing}
else:
    result=prepare(request['tool'],python=request.get('python'),packages=request.get('packages'),path=request['home'])
Path(os.environ['OPTICS_RESULT_FILE']).write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8')

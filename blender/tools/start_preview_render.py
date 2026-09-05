import bpy
import subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[1]
with open(root/'outputs/preview-render.log','w') as log:
    p=subprocess.Popen([bpy.app.binary_path,'-b',str(root/'outputs/everest-rongbuk-study.blend'),'--python',str(root/'tools/render_preview.py'),'--','preview'],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
print('Preview render launched through MCP. PID:',p.pid)

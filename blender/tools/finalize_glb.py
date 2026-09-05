"""Repair undefined UV tangents and optionally correct the exported sun in place."""
import argparse
import json
import math
import struct
from pathlib import Path

parser=argparse.ArgumentParser()
parser.add_argument('file',type=Path)
parser.add_argument('--sun-intensity',type=float)
args=parser.parse_args()
data=args.file.read_bytes()
json_length=struct.unpack_from('<I',data,12)[0]
asset=json.loads(data[20:20+json_length])
binary=bytearray(data[28+json_length:])
def offset(accessor,index):
    view=asset['bufferViews'][accessor['bufferView']]
    width={'VEC3':12,'VEC4':16}[accessor['type']]
    assert accessor['componentType']==5126 and 'sparse' not in accessor
    return view.get('byteOffset',0)+accessor.get('byteOffset',0)+index*view.get('byteStride',width)
fixed=0;seen=set()
for mesh in asset['meshes']:
    for primitive in mesh['primitives']:
        attrs=primitive['attributes'];index=attrs.get('TANGENT')
        if index is None or index in seen:continue
        seen.add(index)
        tangent=asset['accessors'][index];normal=asset['accessors'][attrs['NORMAL']]
        for i in range(tangent['count']):
            pos=offset(tangent,i);x,y,z,w=struct.unpack_from('<4f',binary,pos)
            length=math.sqrt(x*x+y*y+z*z)
            if length>.00001:continue
            n=struct.unpack_from('<3f',binary,offset(normal,i))
            axis=(1,0,0) if abs(n[0])<.9 else (0,1,0)
            dot=sum(a*b for a,b in zip(axis,n))
            t=[a-dot*b for a,b in zip(axis,n)];length=math.sqrt(sum(v*v for v in t))
            struct.pack_into('<4f',binary,pos,*(v/length for v in t),w)
            fixed+=1
if args.sun_intensity is not None:
    for light in asset['extensions']['KHR_lights_punctual']['lights']:
        if light['type']=='directional':light['intensity']=args.sun_intensity
chunk=json.dumps(asset,separators=(',',':'),ensure_ascii=False).encode()
chunk+=b' '*((-len(chunk))%4)
output=struct.pack('<4sII',b'glTF',2,28+len(chunk)+len(binary))+struct.pack('<II',len(chunk),0x4E4F534A)+chunk+struct.pack('<II',len(binary),0x004E4942)+binary
args.file.write_bytes(output)
report_path=args.file.with_suffix('.json')
report=json.loads(report_path.read_text());report['bytes']=len(output);report['repaired_zero_tangents']=fixed
if args.sun_intensity is not None:report['sun_intensity_lux']=args.sun_intensity
report_path.write_text(json.dumps(report,indent=2))
print(json.dumps({'bytes':len(output),'repaired_zero_tangents':fixed}))

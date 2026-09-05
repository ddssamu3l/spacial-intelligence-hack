"""Check the full export's embedded resources and source object coverage."""
import hashlib
import json
import struct
from pathlib import Path

root = Path(__file__).resolve().parents[1]
path = root / 'exports/everest-original-full.glb'
data = path.read_bytes()
magic, version, length = struct.unpack_from('<4sII', data)
assert magic == b'glTF' and version == 2 and length == len(data)
json_length, chunk_type = struct.unpack_from('<II', data, 12)
assert chunk_type == 0x4E4F534A
asset = json.loads(data[20:20+json_length])
binary_offset = 20 + json_length
binary_length, binary_type = struct.unpack_from('<II', data, binary_offset)
assert binary_type == 0x004E4942 and binary_offset + 8 + binary_length == len(data)
assert len(asset['buffers']) == 1 and 'uri' not in asset['buffers'][0]
assert asset['buffers'][0]['byteLength'] <= binary_length
for view in asset['bufferViews']:
    assert view.get('buffer', 0) == 0
    assert view.get('byteOffset', 0) + view['byteLength'] <= binary_length
for image in asset['images']:
    assert 'uri' not in image and 'bufferView' in image
    assert image['mimeType'] in {'image/png', 'image/jpeg'}
for mesh in asset['meshes']:
    for primitive in mesh['primitives']:
        assert primitive.get('mode', 4) == 4
        assert 'POSITION' in primitive['attributes'] and 'NORMAL' in primitive['attributes']
        assert asset['accessors'][primitive['indices']]['count'] % 3 == 0
report = json.loads((path.parent / 'everest-original-full.json').read_text())
expected = sum(group['instances'] for group in report['groups'])
mesh_nodes = [node for node in asset['nodes'] if 'mesh' in node]
assert len(mesh_nodes) == expected + 1, (len(mesh_nodes), expected)  # source + sky
assert len(asset['cameras']) == 1
lights = asset['extensions']['KHR_lights_punctual']['lights']
assert len(lights) == 1 and lights[0]['type'] == 'directional'
summary = {'file': path.name, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(),
           'source_mesh_objects': expected, 'exported_mesh_nodes': len(mesh_nodes),
           'shared_meshes': len(asset['meshes']), 'embedded_images': len(asset['images']),
           'materials': len(asset['materials']), 'cameras': len(asset['cameras']),
           'lights': len(lights), 'external_resources': 0}
(path.parent / 'everest-original-full.validation.json').write_text(json.dumps(summary, indent=2))
print(json.dumps(summary, indent=2))

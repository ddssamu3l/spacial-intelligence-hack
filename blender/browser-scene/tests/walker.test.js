import {test} from 'node:test';
import assert from 'node:assert/strict';
import {Walker,groundHeight} from '../src/walker.js';
import {readFileSync} from 'node:fs';
const ground={nx:241,ny:321,xmin:-60,ymin:-30,step:.5,values:new Float32Array(241*321)};
test('forward movement follows yaw and remains at eye height',()=>{const w=new Walker(ground,[]);for(let i=0;i<60;i++)w.step(1/60,1,0);assert.ok(Math.abs(w.y+4)<.001);assert.equal(w.z,1.75);w.yaw=Math.PI/2;const x=w.x;w.step(.05,1,0);assert.ok(w.x>x);});
test('diagonal movement is normalized',()=>{const a=new Walker(ground,[]),b=new Walker(ground,[]);a.step(.05,1,0);b.step(.05,1,1);assert.ok(Math.abs(a.distance-b.distance)<1e-8);});
test('large ice cylinder blocks walking through its interior',()=>{const w=new Walker(ground,[{x:-1.4,y:-8,radius:1,bottom:-1,top:8}]);for(let i=0;i<300;i++)w.step(1/60,1,0);assert.ok(w.y<=-9.29);});
test('real exported trail supports a grounded 30 metre walk',()=>{const manifest=JSON.parse(readFileSync(new URL('../public/scene/scene.json',import.meta.url)));const file=readFileSync(new URL('../public/scene/geometry.bin',import.meta.url));const {offset,count}=manifest.ground.heights;const heights=new Float32Array(file.buffer.slice(file.byteOffset+offset,file.byteOffset+offset+count*4));const g={...manifest.ground,values:heights};const w=new Walker(g,manifest.obstacles);for(let i=0;i<240;i++){const target=2.2*Math.sin(w.y*.048)+.024*w.y;w.yaw=Math.atan2((target-w.x)*.5,1);w.step(1/60,1,0);assert.ok(Number.isFinite(w.z));assert.ok(Math.abs(w.z-groundHeight(g,w.x,w.y)-1.75)<1e-6);}assert.ok(w.y>15,`Walker blocked at ${w.y}`);});
test('reset and trail limits prevent leaving the modeled foreground',()=>{const w=new Walker(ground,[]);w.y=130;w.step(.05,1,0);assert.equal(w.y,130);w.reset();assert.equal(w.y,-12);assert.equal(w.distance,0);});

test('the complete marked ascent can be walked uphill and back without gaps or blockers',()=>{
  const manifest=JSON.parse(readFileSync(new URL('../public/scene/scene.json',import.meta.url)));
  const file=readFileSync(new URL('../public/scene/geometry.bin',import.meta.url));
  const {offset,count}=manifest.ground.heights;
  const values=new Float32Array(file.buffer.slice(file.byteOffset+offset,file.byteOffset+offset+count*4));
  const g={...manifest.ground,values};
  assert.equal(values.length,g.nx*g.ny);
  const w=new Walker(g,manifest.obstacles,{spawn:manifest.spawn.slice(0,2)});
  const initialZ=w.z;
  for(const waypoints of [manifest.route,manifest.route.toReversed()]){
    for(const target of waypoints){
      let frames=0;
      while(Math.hypot(target.x-w.x,target.y-w.y)>.3 && frames++<150){
        w.yaw=Math.atan2(target.x-w.x,target.y-w.y);
        const z=w.z;w.step(Math.min(1/30,Math.hypot(target.x-w.x,target.y-w.y)/20),1,0,true);
        assert.ok(Math.abs(w.z-z)<.6,`Ground discontinuity at ${w.y}`);
        assert.ok(Number.isFinite(w.z));
      }
      assert.ok(frames<150,`Blocked near route y=${target.y}, walker=(${w.x},${w.y})`);
    }
    if(waypoints===manifest.route){
      assert.ok(w.y>700,'Must reach the extended mountain trail');
      assert.ok(w.z-initialZ>100,'Must reach the upper elevation');
    }
  }
  assert.ok(Math.abs(w.z-initialZ)<1,'Return to the original approach');
});

test('fast traversal covers 20 metres per second while retaining obstacle substeps',()=>{
  const w=new Walker(ground,[]);
  for(let i=0;i<60;i++)w.step(1/60,1,0,true);
  assert.ok(Math.abs(w.distance-20)<.001);
  const blocked=new Walker(ground,[{x:-1.4,y:-8,radius:1,bottom:-1,top:8}]);
  for(let i=0;i<60;i++)blocked.step(1/60,1,0,true);
  assert.ok(blocked.y<=-9.29);
});

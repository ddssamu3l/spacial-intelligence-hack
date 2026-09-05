import * as THREE from 'three';
import {createMaterials} from './materials.js';
import {Walker,groundHeight} from './walker.js';
import {RGBELoader} from 'three/addons/loaders/RGBELoader.js';
import './style.css';
const $=s=>document.querySelector(s),keys=new Set();
let renderer,camera,scene,walker,sun,active=false,ready=false,drag=false,lastX=0,lastY=0,frames=0;
const touch=matchMedia('(pointer:coarse)').matches;
const message=text=>{$('#notice').textContent=text;$('#notice').hidden=false;};
function pause(){active=false;keys.clear();drag=false;$('#welcome').hidden=false;$('#crosshair').hidden=true;$('#touch-controls').hidden=true;if(document.pointerLockElement)document.exitPointerLock();}
async function start(){
  if(!ready)return;active=true;$('#welcome').hidden=true;$('#crosshair').hidden=false;$('#touch-controls').hidden=!touch;$('#notice').hidden=true;
  renderer.domElement.focus();
  if(!touch){try{await renderer.domElement.requestPointerLock();}catch{message('Drag to look around. WASD still moves you.');}}
}
function applyCamera(){
  camera.position.set(walker.x,walker.y,walker.z);
  $('#viewport').dataset.position=JSON.stringify([walker.x,walker.y,walker.z]);
  camera.lookAt(walker.x+Math.sin(walker.yaw)*Math.cos(walker.pitch),walker.y+Math.cos(walker.yaw)*Math.cos(walker.pitch),walker.z+Math.sin(walker.pitch));
}
function resize(){
  if(!renderer)return;const high=$('#quality').value==='high';
  const cap=high?3840:1920;
  renderer.setPixelRatio(Math.min(devicePixelRatio,high?2:1.25,cap/innerWidth, (high?2160:1200)/innerHeight));
  renderer.setSize(innerWidth,innerHeight);camera.aspect=innerWidth/innerHeight;camera.updateProjectionMatrix();
}
async function main(){
  renderer=new THREE.WebGLRenderer({antialias:true,powerPreference:'high-performance'});
  renderer.toneMapping=THREE.AgXToneMapping;renderer.toneMappingExposure=1.12;
  renderer.shadowMap.enabled=true;renderer.shadowMap.type=THREE.PCFSoftShadowMap;renderer.shadowMap.autoUpdate=false;
  renderer.domElement.tabIndex=0;renderer.domElement.setAttribute('aria-label','Walk through Everest');$('#viewport').appendChild(renderer.domElement);
  scene=new THREE.Scene();scene.background=new THREE.Color('#244864');scene.fog=new THREE.Fog('#59788b',4500,21000);
  camera=new THREE.PerspectiveCamera(66,innerWidth/innerHeight,.08,50000);camera.up.set(0,0,1);resize();
  const hemi=new THREE.HemisphereLight(0x99c4fa,0x6c5543,.22);hemi.position.set(0,0,1);scene.add(hemi);
  sun=new THREE.DirectionalLight(0xffe6cf,4.2);sun.position.set(-100,-46,85);sun.target.position.set(0,0,0);sun.castShadow=true;
  sun.shadow.mapSize.set(4096,4096);Object.assign(sun.shadow.camera,{left:-65,right:65,top:65,bottom:-65,near:1,far:320});sun.shadow.normalBias=.045;sun.shadow.bias=-.00005;scene.add(sun,sun.target);
  const [manifest,buffer,materialFor,hdr]=await Promise.all([
    fetch('/scene/scene.json').then(r=>{if(!r.ok)throw Error('Terrain manifest unavailable');return r.json();}),
    fetch('/scene/geometry.bin').then(r=>{if(!r.ok)throw Error('Terrain geometry unavailable');return r.arrayBuffer();}),
    createMaterials(renderer,(n,total)=>{$('#loading').textContent=`Loading mountain surfaces · ${n}/${total}`;}),
    new RGBELoader().loadAsync('/lighting/alpine-daylight.hdr')
  ]);
  hdr.mapping=THREE.EquirectangularReflectionMapping;
  scene.background=new THREE.Color('#204860');
  const pmrem=new THREE.PMREMGenerator(renderer);scene.environment=pmrem.fromEquirectangular(hdr).texture;scene.environmentRotation.x=Math.PI/2;scene.environmentIntensity=.48;pmrem.dispose();
  const floats=a=>new Float32Array(buffer,a.offset,a.count),indices=a=>new Uint32Array(buffer,a.offset,a.count);
  const geometries=manifest.meshes.map(m=>{
    const g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.BufferAttribute(floats(m.attributes.position),3));g.setAttribute('normal',new THREE.BufferAttribute(floats(m.attributes.normal),3));
    if(m.attributes.uv)g.setAttribute('uv',new THREE.BufferAttribute(floats(m.attributes.uv),2));
    if(m.attributes.snow)g.setAttribute('snow',new THREE.BufferAttribute(floats(m.attributes.snow),1));
    if(m.attributes.mountainShade)g.setAttribute('mountainShade',new THREE.BufferAttribute(floats(m.attributes.mountainShade),1));
    g.setIndex(new THREE.BufferAttribute(indices(m.attributes.index),1));g.computeBoundingSphere();return g;
  });
  const matrix=new THREE.Matrix4();
  for(const group of manifest.groups){
    const desc=manifest.meshes[group.mesh];
    const parts=desc.parts??[{material:desc.material}];
    for(const part of parts){
      const geometry=part.index?geometries[group.mesh].clone():geometries[group.mesh];
      if(part.index)geometry.setIndex(new THREE.BufferAttribute(indices(part.index),1));
      const m=new THREE.InstancedMesh(geometry,materialFor(part.material,!!desc.attributes.snow,manifest.materials?.[part.material]),group.transforms.length);
      group.transforms.forEach((a,i)=>m.setMatrixAt(i,matrix.fromArray(a)));
      m.instanceMatrix.needsUpdate=true;m.computeBoundingSphere();m.name=desc.name;
      m.castShadow=!part.material.startsWith('MOUNTAIN');m.receiveShadow=true;scene.add(m);
    }
  }
  const ground={...manifest.ground,values:floats(manifest.ground.heights)};
  const spawn=manifest.spawn,direction=manifest.camera?.direction;
  walker=new Walker(ground,manifest.obstacles,direction?{spawn:spawn.slice(0,2),eyeHeight:spawn[2]-groundHeight(ground,spawn[0],spawn[1]),yaw:Math.atan2(direction[0],direction[1]),pitch:Math.asin(direction[2])}:{});
  if(manifest.camera){camera.fov=THREE.MathUtils.radToDeg(manifest.camera.fov);camera.updateProjectionMatrix();}
  applyCamera();
  $('#loading').textContent='Preparing daylight…';
  await renderer.compileAsync(scene,camera);renderer.shadowMap.needsUpdate=true;renderer.render(scene,camera);
  ready=true;$('#start').disabled=false;$('#start').textContent='Start walking →';$('#loading').textContent='At the camp trail · follow the red markers';$('#viewport').dataset.loaded='true';
  let previous=performance.now(),hud=0,shadowX=walker.x,shadowY=walker.y;
  renderer.setAnimationLoop(now=>{
    const dt=Math.min((now-previous)/1000,.05);previous=now;
    if(active){
      const forward=Number(keys.has('KeyW')||keys.has('ArrowUp'))-Number(keys.has('KeyS')||keys.has('ArrowDown'));
      const strafe=Number(keys.has('KeyD'))-Number(keys.has('KeyA'));
      if(keys.has('ArrowLeft'))walker.yaw-=dt*1.2;if(keys.has('ArrowRight'))walker.yaw+=dt*1.2;
      walker.step(dt,forward,strafe,keys.has('ShiftLeft')||keys.has('ShiftRight'));applyCamera();
      if(Math.hypot(walker.x-shadowX,walker.y-shadowY)>15){shadowX=walker.x;shadowY=walker.y;const floor=groundHeight(ground,shadowX,shadowY);sun.target.position.set(shadowX,shadowY,floor);sun.position.set(shadowX-100,shadowY-46,floor+85);renderer.shadowMap.needsUpdate=true;}
    }
    renderer.render(scene,camera);frames++;hud+=dt;
    if(hud>.25){hud=0;$('#position').textContent=`EAST RONGBUK · ${Math.round(walker.distance)} m walked`;$('#viewport').dataset.position=JSON.stringify([walker.x,walker.y,walker.z]);$('#viewport').dataset.frames=String(frames);$('#viewport').dataset.active=String(active);$('#viewport').dataset.look=JSON.stringify([walker.yaw,walker.pitch]);}
  });
  const canvas=renderer.domElement;
  canvas.addEventListener('pointerdown',e=>{if(!active)return;drag=true;lastX=e.clientX;lastY=e.clientY;canvas.setPointerCapture(e.pointerId);});
  canvas.addEventListener('pointerup',()=>{drag=false;});canvas.addEventListener('pointercancel',()=>{drag=false;});
  document.addEventListener('pointermove',e=>{
    if(!active)return;let dx,dy;
    if(document.pointerLockElement===canvas){dx=e.movementX;dy=e.movementY;}
    else if(drag){dx=e.clientX-lastX;dy=e.clientY-lastY;lastX=e.clientX;lastY=e.clientY;}
    else return;
    walker.yaw+=dx*.0022;walker.pitch=THREE.MathUtils.clamp(walker.pitch-dy*.0022,-1.45,1.45);
  });
  document.addEventListener('pointerlockchange',()=>{if(!document.pointerLockElement&&active&&!touch)pause();});
  document.addEventListener('pointerlockerror',()=>{if(active)message('Drag to look around. WASD still moves you.');});
  canvas.addEventListener('webglcontextlost',e=>{e.preventDefault();pause();message('Graphics paused. Reload this page to reconnect.');});
}
$('#start').addEventListener('click',start);$('#menu').addEventListener('click',pause);
$('#reset').addEventListener('click',()=>{if(walker){walker.reset();applyCamera();$('#position').textContent='TRAIL START · 0 m';}});
$('#quality').addEventListener('change',resize);addEventListener('resize',resize);
$('#fullscreen').addEventListener('click',async()=>{try{if(document.fullscreenElement)await document.exitFullscreen();else await document.documentElement.requestFullscreen();}catch{message('Full screen is unavailable here. You can still walk in this window.');}});
addEventListener('keydown',e=>{if(e.code==='Escape'){pause();return;}if(!active||e.target.matches('input,select,textarea'))return;if(['KeyW','KeyA','KeyS','KeyD','ArrowUp','ArrowDown','ArrowLeft','ArrowRight','ShiftLeft','ShiftRight'].includes(e.code)){e.preventDefault();keys.add(e.code);}});
addEventListener('keyup',e=>keys.delete(e.code));addEventListener('blur',pause);document.addEventListener('visibilitychange',()=>{if(document.hidden)pause();});
for(const button of document.querySelectorAll('[data-move]')){button.addEventListener('pointerdown',e=>{e.preventDefault();keys.add(button.dataset.move);button.setPointerCapture(e.pointerId);});for(const event of ['pointerup','pointercancel','lostpointercapture'])button.addEventListener(event,()=>keys.delete(button.dataset.move));}
main().catch(error=>{console.error(error);$('#loading').textContent=`Could not load the scene: ${error.message}`;$('#start').textContent='Scene unavailable';});

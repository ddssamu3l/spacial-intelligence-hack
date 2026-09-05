import * as THREE from 'three';
const noiseCode=`
float hash3(vec3 p){p=fract(p*.1031);p+=dot(p,p.yzx+33.33);return fract((p.x+p.y)*p.z);}
float noise3(vec3 p){vec3 i=floor(p),f=fract(p);f=f*f*(3.-2.*f);return mix(mix(mix(hash3(i),hash3(i+vec3(1,0,0)),f.x),mix(hash3(i+vec3(0,1,0)),hash3(i+vec3(1,1,0)),f.x),f.y),mix(mix(hash3(i+vec3(0,0,1)),hash3(i+vec3(1,0,1)),f.x),mix(hash3(i+vec3(0,1,1)),hash3(i+vec3(1,1,1)),f.x),f.y),f.z);}
float fbm(vec3 p){return noise3(p)*.57+noise3(p*2.03)*.28+noise3(p*4.11)*.15;}
vec3 tri(sampler2D tex,vec3 p,vec3 n){vec3 w=pow(abs(n),vec3(4.));w/=max(dot(w,vec3(1.)),.001);return texture2D(tex,p.yz).rgb*w.x+texture2D(tex,p.xz).rgb*w.y+texture2D(tex,p.xy).rgb*w.z;}
`;
export async function createMaterials(renderer,onProgress) {
  const loader=new THREE.TextureLoader(),maps={};let loaded=0;
  await Promise.all(['snow_02','rock_boulder_cracked','aerial_rocks_02'].map(async asset=>{
    maps[asset]={};
    await Promise.all(['diff','rough'].map(async channel=>{
      const tex=await loader.loadAsync(`/textures/${asset}_${channel}_4k.jpg`);
      tex.wrapS=tex.wrapT=THREE.RepeatWrapping;tex.anisotropy=Math.min(8,renderer.capabilities.getMaxAnisotropy());
      if(channel==='diff')tex.colorSpace=THREE.SRGBColorSpace;
      maps[asset][channel]=tex;onProgress(++loaded,6);
    }));
  }));
  const scanMaterials={};
  await Promise.all(['rock_05','rock_09'].map(async name=>{
    const base=`/scans/${name}/textures/${name}`;
    const [color,normal,rough]=await Promise.all([loader.loadAsync(base+'_diff_4k.jpg'),loader.loadAsync(base+'_nor_gl_4k.jpg'),loader.loadAsync(base+(name==='rock_09'?'_arm_4k.jpg':'_rough_4k.jpg'))]);
    color.colorSpace=THREE.SRGBColorSpace;
    for(const texture of [color,normal,rough]){texture.anisotropy=Math.min(8,renderer.capabilities.getMaxAnisotropy());texture.flipY=true;}
    const m=new THREE.MeshStandardMaterial({map:color,normalMap:normal,normalScale:new THREE.Vector2(.7,.7),roughnessMap:rough,roughness:.94});
    m.color.setRGB(.82,.84,.87);scanMaterials[name]=m;
  }));
  const cache=new Map();
  return function materialFor(name,hasSnow=false,info){
    if(name.startsWith('SCAN'))return scanMaterials[name.split('•')[1].trim()];
    if(info && /^(FABRIC|CORD|METAL)/.test(name)) {
      if(cache.has(name))return cache.get(name);
      const m=new THREE.MeshStandardMaterial({color:new THREE.Color().setRGB(...info.color),roughness:info.roughness,metalness:info.metalness,side:THREE.DoubleSide});
      cache.set(name,m);return m;
    }
    let kind=name.startsWith('SNOW')?'snow':name.startsWith('MORAINE')?'ground':name.startsWith('MOUNTAIN')?'mountain':name.startsWith('ICE')?'ice':'rock';
    if(name.startsWith('Faded red'))kind='red';if(name.includes('aluminium'))kind='metal';
    const key=kind+hasSnow;if(cache.has(key))return cache.get(key);
    const mat=new THREE.MeshStandardMaterial({roughness:kind==='ice'?.55:.88,color:kind==='red'?0xa42d1b:kind==='metal'?0x87929b:0xffffff,metalness:kind==='metal'?.65:0,side:kind==='red'?THREE.DoubleSide:THREE.FrontSide});
    mat.name=name;
    mat.defaultAttributeValues={color:[1,1,1],uv:[0,0],uv1:[0,0],mountainShade:[1]};
    if(kind==='red'||kind==='metal'){cache.set(key,mat);return mat;}
    mat.customProgramCacheKey=()=>key;
    mat.onBeforeCompile=shader=>{
      Object.assign(shader.uniforms,{snowDiffuse:{value:maps.snow_02.diff},rockDiffuse:{value:maps.rock_boulder_cracked.diff},groundDiffuse:{value:maps.aerial_rocks_02.diff},snowRough:{value:maps.snow_02.rough},rockRough:{value:maps.rock_boulder_cracked.rough}});
      shader.vertexShader=`varying vec3 vAlpinePosition;varying vec3 vAlpineNormal;varying float vSnow;varying float vMountainShade;${kind==='mountain'?'attribute float mountainShade;':''}${hasSnow?'attribute float snow;':''}\n`+shader.vertexShader;
      shader.vertexShader=shader.vertexShader.replace('#include <begin_vertex>',`#include <begin_vertex>
        vec4 alpinePos=vec4(position,1.);vec3 alpineNorm=normal;
        #ifdef USE_INSTANCING
        alpinePos=instanceMatrix*alpinePos;alpineNorm=mat3(instanceMatrix)*alpineNorm;
        #endif
        vAlpinePosition=(modelMatrix*alpinePos).xyz;vAlpineNormal=normalize(mat3(modelMatrix)*alpineNorm);vSnow=${hasSnow?'snow':'0.'};vMountainShade=${kind==='mountain'?'mountainShade':'1.'};`);
      shader.fragmentShader=`varying vec3 vAlpinePosition;varying vec3 vAlpineNormal;varying float vSnow;varying float vMountainShade;uniform sampler2D snowDiffuse,rockDiffuse,groundDiffuse,snowRough,rockRough;${noiseCode}\n`+shader.fragmentShader;
      const common=`vec3 p=vAlpinePosition;vec3 wn=normalize(vAlpineNormal);float relief=0.;vec3 alpineColor;`;
      const color={
        snow:`alpineColor=tri(snowDiffuse,p*.32,wn);relief=dot(alpineColor,vec3(.333))*.023;`,
        rock:`vec3 rc=tri(rockDiffuse,p*.55,wn);alpineColor=mix(vec3(dot(rc,vec3(.2126,.7152,.0722))),rc,.45)*.65;relief=dot(rc,vec3(.333))*.018;`,
        ground:`vec3 rc=tri(groundDiffuse,p*.23,wn);rc=mix(vec3(dot(rc,vec3(.2126,.7152,.0722))),rc,.5)*.65;vec3 sc=tri(snowDiffuse,p*.35,wn);alpineColor=mix(rc,sc,clamp(vSnow,0.,1.));relief=dot(alpineColor,vec3(.333))*.018;`,
        mountain:`float bands=fbm(p*vec3(.007,.007,.045));float crags=fbm(p*.06);float snowCover=${hasSnow?'smoothstep(.22,.80,vSnow+(crags-.5)*.5)':'smoothstep(.69,.93,wn.z)'};vec3 photo=tri(rockDiffuse,p*.045,wn);vec3 stone=mix(vec3(dot(photo,vec3(.2126,.7152,.0722))),photo,.15)*.36;vec3 snowColor=vec3(.82,.88,.95)*(.84+.16*crags);alpineColor=mix(stone,snowColor,snowCover)*vMountainShade;relief=crags*1.75+bands*.3;`,
        ice:`float n=fbm(p*vec3(1.5,1.3,9.));float crust=smoothstep(.26,.64,wn.z);alpineColor=mix(mix(vec3(.18,.38,.46),vec3(.69,.84,.88),n),vec3(.8,.87,.94),crust);relief=n*.035+noise3(p*24.)*.006;`
      }[kind];
      shader.fragmentShader=shader.fragmentShader.replace('#include <map_fragment>',common+color+'diffuseColor.rgb*=alpineColor;');
      shader.fragmentShader=shader.fragmentShader.replace('#include <normal_fragment_maps>',`vec3 dpdx=dFdx(-vViewPosition),dpdy=dFdy(-vViewPosition);vec3 r1=cross(dpdy,normal),r2=cross(normal,dpdx);float determinant=dot(dpdx,r1);vec3 gradient=sign(determinant)*(dFdx(relief)*r1+dFdy(relief)*r2);normal=normalize(abs(determinant)*normal-gradient);`);
    };
    cache.set(key,mat);return mat;
  };
}

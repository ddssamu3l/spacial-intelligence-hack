"""Measure a downloaded Marble world: floor area/reach, heights, top-down floor map, depth pano from the camera vs the RGB pano."""
import json, sys, numpy as np, trimesh, cv2, open3d as o3d, pathlib
d=pathlib.Path(sys.argv[1]); w=json.load(open(d/'world.json')); sem=w['assets']['splats']['semantics_metadata']; s=sem['metric_scale_factor']; g=sem['ground_plane_offset']
m=trimesh.load(d/'collider_mesh_url.glb', force='mesh'); V=(m.vertices*s).astype(np.float32); V[:,1]-=g; F=m.faces.astype(np.uint32)
up=-V[:,1]; tri=V[F]; tri_up=-tri[:,:,1]; fl=(np.abs(tri_up).max(1)<0.15)
e1=tri[:,1]-tri[:,0]; e2=tri[:,2]-tri[:,0]; area=0.5*np.linalg.norm(np.cross(e1,e2),axis=1)
c=tri[fl].mean(1); dist=np.linalg.norm(c[:,[0,2]],axis=1)
print('scale %.4f camera_height %.2f | tris %d watertight %s'%(s,g,len(F),m.is_watertight))
print('floor area %.1f m2 | reach median %.1f m, 95%% %.1f, max %.1f | top %.2f m (99th %.2f) | bbox extent %s'%(area[fl].sum(),*np.percentile(dist,[50,95,100]),up.max(),np.percentile(up,99),(V.max(0)-V.min(0)).round(1)))
res=0.05; lo=V[:,[0,2]].min(0); n2=np.ceil((V[:,[0,2]].max(0)-lo)/res).astype(int)+1; img=np.zeros((n2[1],n2[0],3),np.uint8)
def paint(mask,color):
    ij=((V[mask][:,[0,2]]-lo)/res).astype(int); img[ij[:,1],ij[:,0]]=color
paint(up>2.5,(160,60,60)); paint(np.abs(up)<0.15,(60,160,60)); paint((up>0.3)&(up<2.5),(255,255,255))
o=((np.array([0,0])-lo)/res).astype(int); cv2.circle(img,(int(o[0]),int(o[1])),6,(0,0,255),-1)
for r in (5,10,15): cv2.circle(img,(int(o[0]),int(o[1])),int(r/res),(0,0,255),1)
cv2.imwrite(str(d/'topdown_floor.png'), cv2.resize(img,(0,0),fx=2,fy=2,interpolation=cv2.INTER_NEAREST))
scene=o3d.t.geometry.RaycastingScene(); scene.add_triangles(o3d.core.Tensor(V), o3d.core.Tensor(F)); W,H=1024,512
u=(np.arange(W)+0.5)/W*2*np.pi-np.pi; v=np.pi/2-(np.arange(H)+0.5)/H*np.pi; az,el=np.meshgrid(u,v)
dirs=np.stack([np.sin(az)*np.cos(el), -np.sin(el), np.cos(az)*np.cos(el)],-1).astype(np.float32); origin=np.array([0,-g,0],np.float32)
rays=np.concatenate([np.broadcast_to(origin,dirs.shape),dirs],-1).reshape(-1,6); D=scene.cast_rays(o3d.core.Tensor(rays))['t_hit'].numpy().reshape(H,W); D[~np.isfinite(D)]=np.nan
print('depth pano: hit %.3f median %.2f 95th %.2f max %.2f | straight down %.2f'%(np.isfinite(D).mean(),np.nanmedian(D),np.nanpercentile(D,95),np.nanmax(D),D[-1,W//2]))
row=D[H//2]; print('horizon deg:m', {int(np.degrees(u[i])):round(float(row[i]),1) for i in range(0,W,W//12)})
vis=np.nan_to_num(D,nan=0); vis=(255*np.clip(vis/15,0,1)).astype(np.uint8); cm=cv2.applyColorMap(vis,cv2.COLORMAP_TURBO); cm[np.isnan(D)]=0
p=cv2.resize(cv2.imread(str(d/'pano_url.png')),(W,H)); cv2.imwrite(str(d/'pano_vs_depth.jpg'), np.vstack([p,cm])); np.save(d/'depth_pano_origin.npy',D)

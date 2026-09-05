export function groundHeight(ground, x, y) {
  const u=Math.max(0,Math.min(ground.nx-1.001,(x-ground.xmin)/ground.step));
  const v=Math.max(0,Math.min(ground.ny-1.001,(y-ground.ymin)/ground.step));
  const i=Math.floor(u),j=Math.floor(v),a=u-i,b=v-j,n=ground.nx,h=ground.values;
  return (h[j*n+i]*(1-a)+h[j*n+i+1]*a)*(1-b)+(h[(j+1)*n+i]*(1-a)+h[(j+1)*n+i+1]*a)*b;
}
export class Walker {
  constructor(ground, obstacles, {spawn=[-1.4,-12],eyeHeight=1.75,yaw=0,pitch=.07}={}) { this.ground=ground;this.obstacles=obstacles;this.spawn=spawn;this.eyeHeight=eyeHeight;this.startYaw=yaw;this.startPitch=pitch;this.reset(); }
  reset(){[this.x,this.y]=this.spawn;this.z=groundHeight(this.ground,this.x,this.y)+this.eyeHeight;this.yaw=this.startYaw;this.pitch=this.startPitch;this.distance=0;}
  step(dt, forward, strafe, fast=false) {
    dt=Math.min(dt,.05);
    const magnitude=Math.hypot(forward,strafe);if(!magnitude)return;
    const speed=fast?4.4:2.2;
    const dx=(Math.sin(this.yaw)*forward+Math.cos(this.yaw)*strafe)/magnitude*speed*dt;
    const dy=(Math.cos(this.yaw)*forward-Math.sin(this.yaw)*strafe)/magnitude*speed*dt;
    const steps=Math.max(1,Math.ceil(Math.hypot(dx,dy)/.07));
    for(let i=0;i<steps;i++) {
      let x=Math.max(-54,Math.min(54,this.x+dx/steps)),y=Math.max(-24,Math.min(130,this.y+dy/steps));
      const floor=groundHeight(this.ground,this.x,this.y);
      for(const o of this.obstacles){
        if(o.top<floor+.48||o.bottom>floor+this.eyeHeight)continue;
        const ax=x-o.x,ay=y-o.y,r=o.radius+.3,d=Math.hypot(ax,ay);
        if(d<r){const angle=d>1e-5?Math.atan2(ay,ax):this.yaw+Math.PI;x=o.x+Math.cos(angle)*r;y=o.y+Math.sin(angle)*r;}
      }
      x=Math.max(-54,Math.min(54,x));y=Math.max(-24,Math.min(130,y));
      const h=groundHeight(this.ground,x,y);
      if(h-floor>.5)continue;
      this.distance+=Math.hypot(x-this.x,y-this.y);this.x=x;this.y=y;
    }
    this.z=groundHeight(this.ground,this.x,this.y)+this.eyeHeight;
  }
}

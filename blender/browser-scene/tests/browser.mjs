import {chromium,expect} from '@playwright/test';
import {mkdir,writeFile} from 'node:fs/promises';
await mkdir('artifacts',{recursive:true});
const browser=await chromium.launch({headless:true,args:['--use-angle=metal']});
const page=await browser.newPage({viewport:{width:1440,height:900},deviceScaleFactor:1});
const errors=[];page.on('pageerror',e=>errors.push(String(e)));page.on('console',e=>{if(e.type()==='error')errors.push(e.text().slice(0,1800));});
try{
 await page.goto('http://127.0.0.1:4174/');
 await expect(page.locator('#viewport')).toHaveAttribute('data-loaded','true',{timeout:120000});
 await page.waitForTimeout(500);await page.screenshot({path:'artifacts/first-person-start.png'});
 await page.getByRole('button',{name:'Start walking →'}).click();
 await expect(page.locator('#welcome')).toBeHidden();
 const initial=await page.locator('#viewport').getAttribute('data-position');
 await page.keyboard.down('w');await page.waitForTimeout(1800);await page.keyboard.up('w');await page.waitForTimeout(350);
 const after=await page.locator('#viewport').getAttribute('data-position');
 if(JSON.parse(after)[1]<=JSON.parse(initial)[1]+.2)throw Error(`Forward movement failed: ${initial} => ${after}`);
 const lookBefore=await page.locator('#viewport').getAttribute('data-look');
 await page.mouse.move(700,450);await page.mouse.down();await page.mouse.move(760,430,{steps:8});await page.mouse.up();await page.waitForTimeout(350);
 const lookAfter=await page.locator('#viewport').getAttribute('data-look');if(lookAfter===lookBefore)throw Error('Mouse look did not rotate the camera');
 await page.screenshot({path:'artifacts/first-person-walking.png'});
 await page.keyboard.press('Escape');await expect(page.locator('#welcome')).toBeVisible();await page.waitForTimeout(350);
 const paused=await page.locator('#viewport').getAttribute('data-position');await page.keyboard.press('w');await page.waitForTimeout(350);if(paused!==await page.locator('#viewport').getAttribute('data-position'))throw Error('Camera moved while paused');
 await page.getByRole('button',{name:'Back to trail start'}).click();
 await page.waitForTimeout(350);const reset=JSON.parse(await page.locator('#viewport').getAttribute('data-position'));if(Math.abs(reset[1]+12)>.001)throw Error('Reset failed');
 await page.getByLabel('Display').selectOption('high');await page.waitForTimeout(250);
 if(errors.length)throw Error(errors.join('\n'));
 await writeFile('artifacts/browser-check.json',JSON.stringify({initial,after,reset,errors},null,2));
 console.log(JSON.stringify({initial,after,reset,errors}));
}finally{await browser.close();}

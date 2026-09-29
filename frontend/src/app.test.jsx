// @vitest-environment jsdom
import React from 'react';
import {it,expect,vi,afterEach,beforeEach} from 'vitest';
import {render,screen,waitFor,cleanup,fireEvent} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {App} from './main.jsx';
let current, calls;
const file={path:'AUDIO_001.wav',size:16000,modified_ns:1e18,format:'.wav',state:'En riesgo',sha256:null,copies:{},history:[]};
beforeEach(()=>{
 current={paths:['','',''],session:null,busy:false,operation:null,error:null,historical:false};calls=[];
 vi.stubGlobal('fetch',vi.fn(async(url,options={})=>{
  const route=url.replace('/api/','');calls.push({route,options});
  if(route==='bootstrap')return {ok:true,json:async()=>({token:'test-token',...structuredClone(current)})};
  if(route==='upload-start')return {ok:true,json:async()=>({id:'batch'})};
  if(route==='upload-finish')current={...current,paths:['C:/archivos_subidos/batch','',''],session:null};
  if(route==='demo')current={...current,paths:['C:/source','C:/a','C:/b'],session:null};
  if(route==='inventory')current={...current,session:{id:'test',files:[structuredClone(file)],state:'En riesgo',issues:[]}};
  if(route==='transfer'||route==='retry')current={...current,session:{...current.session,state:'Protegido',card_safe:true,checked:'2026-09-28T12:00:00Z',files:[{...file,state:'Protegido',sha256:'abc',copies:{A:{path:'C:/a/AUDIO_001.wav'},B:{path:'C:/b/AUDIO_001.wav'}},history:[{event:'Copias verificadas',time:'2026-09-23T12:00:00Z'}]}]}};
  if(route.startsWith('folders'))return {ok:true,json:async()=>({path:'C:/source',parent:'C:/',home:'C:/FrameVault',folders:[]})};
  return {ok:true,json:async()=>structuredClone(current)};
 }));
});
afterEach(()=>{cleanup();vi.unstubAllGlobals()});
async function demo(user){await waitFor(()=>expect(screen.getByRole('button',{name:'Probar con una demo'}).disabled).toBe(false));await user.click(screen.getByRole('button',{name:'Probar con una demo'}));}
it('prevents inventory without three folders and allows demo inventory',async()=>{
 const user=userEvent.setup();render(<App/>);
 expect(screen.getByRole('button',{name:'Crear inventario'}).disabled).toBe(true);
 await demo(user);await user.click(screen.getByRole('button',{name:'Crear inventario'}));
 expect(await screen.findByText('AUDIO_001.wav')).toBeTruthy();
 expect(calls.find(c=>c.route==='inventory').options.headers['X-FrameVault-Token']).toBe('test-token');
});
it('runs protection and opens a real passport view',async()=>{
 const user=userEvent.setup();render(<App/>);await demo(user);await user.click(screen.getByRole('button',{name:'Crear inventario'}));
 const buttons=await screen.findAllByRole('button',{name:'Proteger material',exact:true});
 await user.click(buttons.find(b=>b.classList.contains('primary')));
 expect(await screen.findByText('Tu material está a salvo.')).toBeTruthy();
 await user.click(screen.getByRole('button',{name:'Ver pasaporte de AUDIO_001.wav'}));
 expect(screen.getByRole('dialog',{name:'Pasaporte del archivo'})).toBeTruthy();
 expect(screen.getByText('Copias verificadas')).toBeTruthy();
 await user.keyboard('{Escape}');expect(screen.queryByRole('dialog')).toBeNull();
});
it('changing a folder invalidates the current inventory before copying',async()=>{
 const user=userEvent.setup();render(<App/>);await demo(user);await user.click(screen.getByRole('button',{name:'Crear inventario'}));
 await user.click(screen.getByRole('button',{name:/Material de origen/}));
 await user.click(await screen.findByRole('button',{name:'Usar esta carpeta'}));
 expect(screen.getByText('Actualiza el inventario')).toBeTruthy();
 expect(screen.getByRole('button',{name:'Crear inventario'})).toBeTruthy();
 expect(screen.queryAllByRole('button',{name:'Proteger material',exact:true}).some(b=>b.classList.contains('primary'))).toBe(false);
});
it('search filters files without changing the session inventory',async()=>{
 const user=userEvent.setup();render(<App/>);await demo(user);await user.click(screen.getByRole('button',{name:'Crear inventario'}));
 await user.type(await screen.findByRole('textbox',{name:'Buscar archivo'}),'not-present');
 expect(screen.getByText('No hay archivos que coincidan con tu búsqueda.')).toBeTruthy();
 await user.clear(screen.getByRole('textbox',{name:'Buscar archivo'}));expect(screen.getByText('AUDIO_001.wav')).toBeTruthy();
});

it('uploads personal files and requires backup destinations afterwards',async()=>{
 const user=userEvent.setup();render(<App/>);
 await waitFor(()=>expect(screen.getByRole('button',{name:'Subir archivos'}).disabled).toBe(false));
 const files=[new File(['personal'],'documento.pdf',{type:'application/pdf'}),new File(['photo'],'foto.jpg',{type:'image/jpeg'})];
 await user.upload(screen.getByLabelText('Seleccionar archivos para subir'),files);
 await waitFor(()=>expect(calls.some(c=>c.route==='upload-finish')).toBe(true));
 expect(calls.filter(c=>c.route.startsWith('upload-file')).map(c=>c.options.body)).toEqual(files);
 expect(screen.getByRole('button',{name:'Crear inventario'}).disabled).toBe(true);
 expect(screen.getByText('batch')).toBeTruthy();
});

it('only shows card clearance after verification and hides it after configuration changes',async()=>{
 const user=userEvent.setup();render(<App/>);await demo(user);
 expect(screen.getByText(/No reutilizar la tarjeta todavía/)).toBeTruthy();
 await user.click(screen.getByRole('button',{name:'Crear inventario'}));
 await user.click((await screen.findAllByRole('button',{name:'Proteger material',exact:true})).find(b=>b.classList.contains('primary')));
 expect(await screen.findByText(/La tarjeta puede liberarse/)).toBeTruthy();
 expect(screen.getByText('1 de 1 archivos protegidos — 100 %')).toBeTruthy();
 await user.click(screen.getByRole('checkbox',{name:'Organizar automáticamente los respaldos'}));
 expect(screen.queryByText(/La tarjeta puede liberarse/)).toBeNull();
 expect(screen.getByText(/No reutilizar la tarjeta todavía/)).toBeTruthy();
});
it('retries failed copies and sends organization with the inventory',async()=>{
 const user=userEvent.setup();render(<App/>);await demo(user);
 await user.click(screen.getByRole('checkbox',{name:'Organizar automáticamente los respaldos'}));
 await user.type(screen.getByLabelText('Proyecto'),'Rodaje');
 await user.click(screen.getByRole('button',{name:'Crear inventario'}));
 expect(JSON.parse(calls.find(c=>c.route==='inventory').options.body).organization.project).toBe('Rodaje');
 current.session.issues=['Copia incompleta'];
 await waitFor(()=>expect(screen.getByRole('button',{name:'Reintentar copia'})).toBeTruthy(),{timeout:2000});
 await user.click(screen.getByRole('button',{name:'Reintentar copia'}));
 expect(await screen.findByText(/La tarjeta puede liberarse/)).toBeTruthy();
 expect(calls.some(c=>c.route==='retry')).toBe(true);
});

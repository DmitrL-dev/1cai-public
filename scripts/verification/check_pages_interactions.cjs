const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
// Isolated controller tests with a minimal DOM stub; not rendering or browser QA.
const root = require('node:path').resolve(__dirname, '../..');
class FakeElement {
  constructor(id, attrs = {}) { this.id = id; this.attrs = attrs; this.events = {}; this.classes = new Set(); this.classList = { toggle: (name, state) => state ? this.classes.add(name) : this.classes.delete(name) }; this.hidden = false; this.focused = false; }
  setAttribute(k, v) { this.attrs[k] = v; }
  getAttribute(k) { return this.attrs[k]; }
  addEventListener(k, fn) { this.events[k] = fn; }
  focus() { this.focused = true; }
}
const names = ['source','evidence','draft'];
const tabs = names.map(name => new FakeElement(`tab-${name}`, {'aria-controls':`panel-${name}`}));
const panels = names.map(name => new FakeElement(`panel-${name}`));
const tablist = new FakeElement('tabs');
const media = {matches:false, addEventListener:(k,fn) => media.change = fn};
const document = {querySelectorAll: selector => selector.startsWith('[role') ? tabs : panels, querySelector: () => tablist};
vm.runInNewContext(fs.readFileSync(`${root}/site/site.js`,'utf8'), {document,window:{matchMedia:() => media}});
assert.equal(tablist.attrs['aria-orientation'],'vertical');
const selected = n => { assert.equal(tabs.filter(x => x.attrs['aria-selected'] === 'true').length,1); assert.equal(tabs[n].attrs['aria-selected'],'true'); assert.equal(tabs[n].tabIndex,0); assert.equal(panels.filter(x => !x.hidden).length,1); assert.equal(panels[n].hidden,false); };
for(let repeat=0;repeat<3;repeat++) for(let i=0;i<3;i++) { tabs[i].events.click(); selected(i); }
const key = (i,k,modifiers={}) => { let prevented=false; tabs[i].events.keydown({key:k,...modifiers,preventDefault:()=>prevented=true}); return prevented; };
assert.ok(key(2,'ArrowDown'));selected(0);assert.ok(tabs[0].focused);
assert.ok(key(0,'ArrowUp'));selected(2);
assert.ok(key(2,'Home'));selected(0);
assert.ok(key(0,'End'));selected(2);
assert.ok(key(2,'ArrowRight'));selected(0);
assert.ok(key(0,'ArrowLeft'));selected(2);
assert.equal(key(2,'Escape'),false);selected(2);
for (const modifiers of [{ctrlKey:true},{metaKey:true},{altKey:true}]) {
  assert.equal(key(2,'Home',modifiers),false);selected(2);
  assert.equal(key(2,'ArrowLeft',modifiers),false);selected(2);
}
media.matches=true;media.change();assert.equal(tablist.attrs['aria-orientation'],'horizontal');
media.matches=false;media.change();assert.equal(tablist.attrs['aria-orientation'],'vertical');
console.log('PASS: isolated JS unit tests: repeated clicks, one selected panel, keyboard wrap, Home/End, ignored Escape and browser shortcut modifiers, responsive orientation. This does not constitute browser QA.');

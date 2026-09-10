'use strict';
const { randomUUID } = require('node:crypto');

// Each async request belongs to a generation. Reset never adopts an old reply.
class Page {
  constructor(limit = 5000) { this.limit = limit; this.generation = 0; this.reset(); }
  reset() {
    this.generation++; this.items = []; this.next = null; this.loaded = false;
    this.loading = null; this.cursors = new Set();
  }
  async load(fetch, more = false) {
    if (this.loading) return this.loading;
    if (this.loaded && (!more || this.next === null)) return;
    const generation = this.generation, cursor = this.next;
    const loading = Promise.resolve().then(() => fetch(cursor)).then(result => {
      if (generation !== this.generation) return;
      if (this.items.length + result.items.length > this.limit) throw new Error('VIEW_ROW_LIMIT');
      if (result.next !== null && (result.next === cursor || this.cursors.has(result.next))) throw new Error('INVALID_PAGE_CURSOR');
      if (result.next !== null) this.cursors.add(result.next);
      this.items = this.items.concat(result.items); this.next = result.next; this.loaded = true;
    }).finally(() => { if (generation === this.generation) this.loading = null; });
    this.loading = loading;
    return loading;
  }
}
class Handles {
  constructor(limit = 12000) { this.limit = limit; this.records = new Map(); }
  add(value) {
    if (this.records.size >= this.limit) throw new Error('VIEW_HANDLE_LIMIT');
    const id = randomUUID(); this.records.set(id, Object.freeze(value)); return id;
  }
  get(id) {
    if (typeof id !== 'string' || !this.records.has(id)) throw new Error('UNKNOWN_VIEW_HANDLE');
    return this.records.get(id);
  }
  delete(id) { this.records.delete(id); }
  clear() { this.records.clear(); }
}
module.exports = { Page, Handles };

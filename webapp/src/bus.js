const emitter = { on(ev, fn){ (this._m ||= {})[ev] ||= []; this._m[ev].push(fn) }, emit(ev, ...a){ (this._m?.[ev] || []).forEach(f => f(...a)) } }
export default emitter

'use strict';
// Reduced diagnostics only: never copy exception messages, stacks or object data.
const assert = require('node:assert/strict');
const {createHash} = require('node:crypto');
const CHECKPOINTS = Object.freeze(['environment', 'activation', 'initial-inventories',
  'first.snapshot', 'first.metadata', 'first.forged-handle', 'first.manual-draft',
  'first.bsl', 'first.concurrent-edit', 'first.revocation', 'first.unobserved-commit',
  'first.advance-head', 'first.persist-selection', 'first.handoff',
  'restart.handoff', 'restart.process', 'restart.snapshot', 'restart.selection',
  'restart.current-head', 'restart.historical-draft', 'restart.intent-recovery',
  'restart.receipt-replay', 'restart.historical-bsl', 'restart.source',
  'final-inventories', 'complete']);
const CODES = new Set(['ERR_ASSERTION', 'ETIMEDOUT', 'PROJECT_FORBIDDEN', 'DRAFT_CONFLICT',
  'WORKBENCH_STATE_INVALID', 'WORKBENCH_PROFILE_MISMATCH', 'UNKNOWN_VIEW_HANDLE',
  'TRUST_REQUIRED', 'EDITOR_PROFILE_REQUIRED', 'WINDOWS_PROFILE_REQUIRED']);
const OPERATORS = new Set(['strictEqual', 'notStrictEqual', 'deepStrictEqual',
  'notDeepStrictEqual', '==', 'rejects', 'match', 'doesNotReject']);

function checkpoint(report, value) {
  if (!CHECKPOINTS.includes(value)) throw new Error('INVALID_EDITOR_CHECKPOINT');
  report.checkpoint = value;
}

function summary(value) {
  if (value === null) return {type: 'null'};
  if (typeof value === 'boolean') return {type: 'boolean', value};
  if (typeof value === 'number') return Number.isSafeInteger(value)
    ? {type: 'integer', value} : {type: 'number'};
  if (typeof value === 'string') {
    const size_bytes = Buffer.byteLength(value, 'utf8');
    return {type: 'string', size_bytes, sha256: size_bytes <= 1048576
      ? createHash('sha256').update(value).digest('hex') : null};
  }
  if (Array.isArray(value)) return {type: 'array', length: value.length};
  return {type: ['undefined', 'object'].includes(typeof value) ? typeof value : 'other'};
}

function failure(error) {
  try {
    const assertion = error instanceof assert.AssertionError;
    return {category: assertion ? 'assertion' : error?.code === 'ETIMEDOUT' ? 'timeout' : 'error',
      code: CODES.has(error?.code) ? error.code : null,
      operator: assertion && OPERATORS.has(error.operator) ? error.operator : null,
      actual: summary(assertion ? error.actual : undefined),
      expected: summary(assertion ? error.expected : undefined)};
  } catch {
    return {category: 'error', code: null, operator: null,
      actual: {type: 'other'}, expected: {type: 'other'}};
  }
}
module.exports = {CHECKPOINTS, checkpoint, failure};

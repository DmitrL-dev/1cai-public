'use strict';
// Fresh host: inspect durable IDs only; no repairSource or testDraft invocation.
exports.run=require('./daily.cjs').recover;

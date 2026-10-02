'use strict';
// Dedicated observation route. It cannot fall through to the repair attempt.
exports.run=require('./daily.cjs').readyIntentOnly;
